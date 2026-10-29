#!/usr/bin/env python3
"""Focused offline validation for universal lighting recovery."""

from __future__ import annotations

import fcntl
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True

loader = importlib.machinery.SourceFileLoader(
    "lighting_recovery_runtime", str(ROOT / "lighting-recovery")
)
runtime_spec = importlib.util.spec_from_loader(loader.name, loader)
assert runtime_spec
recovery = importlib.util.module_from_spec(runtime_spec)
sys.modules[runtime_spec.name] = recovery
loader.exec_module(recovery)


class LightingRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_home = self.root / "state"
        self.runtime = self.root / "runtime"
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.environment = {
            "XDG_STATE_HOME": str(self.state_home),
            "OPENRGB_RUNTIME_DIR": str(self.runtime),
        }
        self.failure = (
            self.state_home / "omarchy-plus/openrgb-presets/ram-tetris-failure.json"
        )
        self.lifecycle_state = self.failure.parent / "lifecycle-service-state.json"
        self.openrgb_config = self.root / "OpenRGB.json"
        self.config_raw = b'{"Detectors":{"detectors":{}}}\n'
        self.openrgb_config.write_bytes(self.config_raw)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_failure(self, message: str, timestamp: float = 1_792_000_000.0) -> bytes:
        self.failure.parent.mkdir(parents=True, exist_ok=True)
        self.failure.parent.chmod(0o700)
        raw = (
            json.dumps(
                {
                    "message": message,
                    "pid": 77,
                    "state": "failed",
                    "time": timestamp,
                },
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        self.failure.write_bytes(raw)
        return raw

    def patched_environment(self):
        return mock.patch.dict(os.environ, self.environment, clear=False)

    def write_lifecycle_state(
        self,
        *,
        timestamp: float = 1_792_000_000.0,
        state: str = "stopping",
        reason: str = "deliberate",
        include_server: bool = True,
    ) -> bytes:
        self.lifecycle_state.parent.mkdir(parents=True, exist_ok=True)
        value = {
            "boot_id": "boot-a",
            "lifecycle_pid": 41,
            "lifecycle_start": "4100",
            "reason": reason,
            "state": state,
            "time": timestamp,
        }
        if include_server:
            value.update({"server_pid": 42, "server_start": "4200"})
        raw = (json.dumps(value, sort_keys=True) + "\n").encode()
        self.lifecycle_state.write_bytes(raw)
        return raw

    def write_historical_clearance_records(
        self,
    ) -> tuple[bytes, bytes, bytes, bytes]:
        failure_raw = (
            b'{"message": "writer termination was not preceded by an authenticated '
            b'lifecycle stop request", "pid": 5919, "state": "failed", '
            b'"time": 1792308226.2688146}\n'
        )
        boundary_raw = (
            json.dumps(
                {
                    "boot_id": "boot-a",
                    "lifecycle_pid": 41,
                    "lifecycle_start": "4100",
                    "reason": "deliberate",
                    "server_pid": 42,
                    "server_start": "4200",
                    "state": "stopping",
                    "time": 1_792_308_226.2024546,
                },
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        current_raw = (
            json.dumps(
                {
                    "boot_id": "boot-a",
                    "lifecycle_pid": 51,
                    "lifecycle_start": "5100",
                    "reason": recovery.HISTORICAL_READY_REASON,
                    "server_pid": 52,
                    "server_start": "5200",
                    "state": "ready",
                    "time": 1_792_343_227.7618039,
                },
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        root = self.failure.parent
        evidence = root / "recovery-evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        root.chmod(0o700)
        evidence.chmod(0o700)
        files = {
            self.failure: failure_raw,
            evidence
            / f"{recovery.HISTORICAL_CLEARANCE_REFERENCE}.failure.json": failure_raw,
            evidence
            / f"{recovery.HISTORICAL_CLEARANCE_REFERENCE}.lifecycle-state.json": boundary_raw,
            evidence
            / f"{recovery.HISTORICAL_CLEARANCE_REFERENCE}.openrgb-config.json": self.config_raw,
            self.lifecycle_state: current_raw,
            root / "ram-tetris-enabled": b"off\n",
        }
        for path, raw in files.items():
            path.write_bytes(raw)
            path.chmod(0o600)
        return failure_raw, boundary_raw, self.config_raw, current_raw

    def write_reviewed_software_race_records(self) -> tuple[bytes, bytes]:
        failure_raw = (
            b'{"message": "RAM Tetris writer exited unexpectedly; static restoration '
            b'was not attempted", "pid": 1174336, "state": "failed", '
            b'"time": 1792561532.70337}\n'
        )
        current_raw = (
            json.dumps(
                {
                    "boot_id": "boot-a",
                    "lifecycle_pid": 51,
                    "lifecycle_start": "5100",
                    "reason": recovery.HISTORICAL_READY_REASON,
                    "server_pid": 52,
                    "server_start": "5200",
                    "state": "ready",
                    "time": 1_792_580_872.6454194,
                },
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        self.failure.parent.mkdir(parents=True, exist_ok=True)
        self.failure.parent.chmod(0o700)
        for path, raw in (
            (self.failure, failure_raw),
            (self.lifecycle_state, current_raw),
            (self.failure.parent / "ram-tetris-enabled", b"off\n"),
        ):
            path.write_bytes(raw)
            path.chmod(0o600)
        self.assertEqual(
            hashlib.sha256(failure_raw).hexdigest(),
            recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST[
                "LR-3903E50F10DAA4FD"
            ].latch_sha256,
        )
        return failure_raw, current_raw

    def write_corrected_software_interruption_records(
        self,
        *,
        pid: int = 1227358,
        detail_overrides: dict[str, object] | None = None,
        source_overrides: dict[str, object] | None = None,
    ) -> tuple[bytes, bytes]:
        details: dict[str, object] = {
            "checkpoint_age_ms": 250.017,
            "checkpoint_deadline_ms": 2000.0,
            "checkpoint_elapsed_ms": 304.78,
            "checkpoint_interval_ms": 250.0,
            "checkpoint_started_unix": 1_792_864_340.3312109,
            "failure_kind": "checkpoint-expired",
            "kernel_evidence_status": "captured",
            "kernel_messages": [],
            "last_checkpoint_age_ms": 250.039,
            "last_checkpoint_completed_unix": 1_792_864_340.3859522,
            "last_checkpoint_duration_ms": 54.741,
            "last_temperatures_mc": {
                "10-0050": 44250,
                "10-0051": 44500,
                "10-0052": 43000,
                "10-0053": 38500,
            },
            "writer_progress_count": 867,
        }
        details.update(detail_overrides or {})
        source: dict[str, object] = {
            "component": "ram-tetris",
            "path": recovery.CORRECTED_CHECKPOINT_SOURCE_PATH,
            "revision": recovery.CORRECTED_CHECKPOINT_SOURCE_REVISION,
            "sha256": recovery.CORRECTED_CHECKPOINT_SOURCE_SHA256,
            "version": "0.4.30",
        }
        source.update(source_overrides or {})
        failure_raw = (
            json.dumps(
                {
                    "details": details,
                    "evidence_version": 1,
                    "message": recovery.CORRECTED_CHECKPOINT_REASON,
                    "pid": pid,
                    "source": source,
                    "state": "failed",
                    "time": 1_792_864_340.6402085,
                },
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        current_raw = (
            json.dumps(
                {
                    "boot_id": "boot-a",
                    "lifecycle_pid": 51,
                    "lifecycle_start": "5100",
                    "reason": recovery.HISTORICAL_READY_REASON,
                    "server_pid": 52,
                    "server_start": "5200",
                    "state": "ready",
                    "time": 1_792_868_400.0,
                },
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        self.failure.parent.mkdir(parents=True, exist_ok=True)
        self.failure.parent.chmod(0o700)
        for path, raw in (
            (self.failure, failure_raw),
            (self.lifecycle_state, current_raw),
            (self.failure.parent / "ram-tetris-enabled", b"off\n"),
        ):
            path.write_bytes(raw)
            path.chmod(0o600)
        return failure_raw, current_raw

    def write_reviewed_hardware_health_records(
        self,
    ) -> tuple[
        object,
        bytes,
        bytes,
        object,
    ]:
        base = recovery.REVIEWED_HARDWARE_HEALTH_ALLOWLIST["LR-E8FE394802531DE7"]
        failure_raw = (
            b'{"message": "10-0053 temperature is unreadable", "pid": 2295616, '
            b'"state": "failed", "time": 1792651066.1584392}\n'
        )
        self.assertEqual(hashlib.sha256(failure_raw).hexdigest(), base.latch_sha256)
        now = time.time()
        started = now - 120
        ended = started + 61
        started_text = recovery.datetime.fromtimestamp(started, recovery.UTC).isoformat(
            timespec="microseconds"
        )
        ended_text = recovery.datetime.fromtimestamp(ended, recovery.UTC).isoformat(
            timespec="microseconds"
        )
        boot_id = "a" * 32
        cursor = f"s=test;i=1;b={boot_id};m=1;t=1;x=1"
        metadata = "\n".join(
            (
                f"incident={base.incident_reference}",
                "plugin_version=0.4.26",
                f"plugin_revision={base.observed_source_revision}",
                f"latch_sha256_before={base.latch_sha256}",
                f"kernel_cursor={cursor}",
                f"started={started_text}",
                f"ended={ended_text}",
                "samples_completed=60",
                "stop_reason=complete",
                f"latch_sha256_after={base.latch_sha256}",
                "",
            )
        ).encode()
        endpoints = ("10-0050", "10-0051", "10-0052", "10-0053")
        sample_lines = [
            "sample\twall_time\tmonotonic_s\tendpoint\tstatus\ttemp_mc\tdetail"
        ]
        for sample in range(1, 61):
            wall = recovery.datetime.fromtimestamp(
                started + sample, recovery.UTC
            ).isoformat(timespec="microseconds")
            for offset, endpoint in enumerate(endpoints):
                sample_lines.append(
                    f"{sample}\t{wall}\t{1000 + sample:.2f}\t{endpoint}"
                    f"\tok\t{36000 + offset * 1000}\t-"
                )
        samples = ("\n".join(sample_lines) + "\n").encode()
        summary_lines = [
            (
                "endpoint\tsamples\tok\tfailures\tmissing\tmalformed"
                "\tmin_mc\tmax_mc\tfinal_mc"
            )
        ]
        for offset, endpoint in enumerate(endpoints):
            value = 36000 + offset * 1000
            summary_lines.append(
                f"{endpoint}\t60\t60\t0\t0\t0\t{value}\t{value}\t{value}"
            )
        summary = ("\n".join(summary_lines) + "\n").encode()
        evidence_files = {
            "metadata.txt": metadata,
            "samples.tsv": samples,
            "kernel-all.log": b"",
            "kernel-reader.stderr": b"",
            "kernel-relevant.log": b"",
            "summary.tsv": summary,
        }
        manifest = b"".join(
            f"{hashlib.sha256(evidence_files[name]).hexdigest()}  {name}\n".encode()
            for name in sorted(evidence_files)
        )
        reviewed = recovery.ReviewedHardwareHealth(
            code=base.code,
            incident_reference=base.incident_reference,
            latch_sha256=base.latch_sha256,
            original_reason=base.original_reason,
            stability_directory=base.stability_directory,
            stability_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
            observed_source_revision=base.observed_source_revision,
        )
        evidence_files["manifest.sha256"] = manifest
        evidence = (
            self.failure.parent / "recovery-evidence" / reviewed.stability_directory
        )
        evidence.mkdir(parents=True)
        self.failure.parent.chmod(0o700)
        evidence.parent.chmod(0o700)
        evidence.chmod(0o700)
        for name, raw in evidence_files.items():
            path = evidence / name
            path.write_bytes(raw)
            path.chmod(0o600)
        current_raw = (
            json.dumps(
                {
                    "boot_id": boot_id,
                    "lifecycle_pid": 51,
                    "lifecycle_start": "5100",
                    "reason": recovery.HISTORICAL_READY_REASON,
                    "server_pid": 52,
                    "server_start": "5200",
                    "state": "ready",
                    "time": ended + 1,
                },
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        for path, raw in (
            (self.failure, failure_raw),
            (self.lifecycle_state, current_raw),
            (self.failure.parent / "ram-tetris-enabled", b"off\n"),
        ):
            path.write_bytes(raw)
            path.chmod(0o600)
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value=boot_id),
        ):
            stability = recovery._verify_stability_evidence(reviewed)
        return reviewed, failure_raw, current_raw, stability

    def write_transient_spd_records(self):
        failure_time = time.time() - 120
        failure_raw = (
            json.dumps(
                {
                    "message": "10-0053 temperature is unreadable",
                    "pid": 77,
                    "state": "failed",
                    "time": failure_time,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        incident = recovery.TransientSpdIncident(
            failure_raw=failure_raw,
            incident_reference=recovery._incident_reference(failure_raw),
            latch_sha256=hashlib.sha256(failure_raw).hexdigest(),
            original_reason="10-0053 temperature is unreadable",
            endpoint="10-0053",
            failure_time=failure_time,
            classification="legacy-read-or-parse-error",
            source_revision=recovery.LEGACY_TRANSIENT_SPD_REVISION,
            source_path=recovery.LEGACY_TRANSIENT_SPD_SOURCE_PATH,
            source_sha256=recovery.LEGACY_TRANSIENT_SPD_SOURCE_SHA256,
        )
        boot_id = "a" * 32
        cursor_start = f"s=start;i=1;b={boot_id};m=1;t=1;x=1"
        cursor_end = f"s=end;i=2;b={boot_id};m=2;t=2;x=2"
        started = time.time() - 70
        ended = started + 59
        current_raw = (
            json.dumps(
                {
                    "boot_id": boot_id,
                    "lifecycle_pid": 51,
                    "lifecycle_start": "5100",
                    "reason": recovery.HISTORICAL_READY_REASON,
                    "server_pid": 52,
                    "server_start": "5200",
                    "state": "ready",
                    "time": failure_time + 1,
                },
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        sample_lines = [
            "sample\twall_time\tmonotonic_s\tendpoint\tstatus\ttemp_mc\tdetail"
        ]
        for sample in range(1, 61):
            wall = recovery.datetime.fromtimestamp(
                started + sample - 1, recovery.UTC
            ).isoformat(timespec="microseconds")
            for offset, endpoint in enumerate(recovery.TRANSIENT_SPD_ENDPOINTS):
                sample_lines.append(
                    f"{sample}\t{wall}\t{1000 + sample - 1:.6f}\t{endpoint}"
                    f"\tok\t{36000 + offset * 1000}\t-"
                )
        metadata = {
            "schema_version": 1,
            "category": "reviewed-transient-spd",
            "plugin_version": "0.4.30",
            "incident": {
                "reference": incident.incident_reference,
                "latch_sha256": incident.latch_sha256,
                "reason": incident.original_reason,
                "endpoint": incident.endpoint,
                "classification": incident.classification,
                "source_revision": incident.source_revision,
                "source_path": incident.source_path,
                "source_sha256": incident.source_sha256,
            },
            "environment": {
                "boot_id": boot_id,
                "suspend_count": 11,
                "lifecycle_pid": 51,
                "lifecycle_start": "5100",
                "server_pid": 52,
                "server_start": "5200",
                "kernel_cursor_start": cursor_start,
                "kernel_cursor_end": cursor_end,
            },
            "observation": {
                "started": recovery.datetime.fromtimestamp(
                    started, recovery.UTC
                ).isoformat(timespec="microseconds"),
                "ended": recovery.datetime.fromtimestamp(ended, recovery.UTC).isoformat(
                    timespec="microseconds"
                ),
                "samples_completed": 60,
                "readings_completed": 240,
                "status": "complete",
            },
        }
        payloads = {
            "failure-latch.json": failure_raw,
            "kernel-relevant.log": b"",
            "metadata.json": (json.dumps(metadata, sort_keys=True) + "\n").encode(),
            "samples.tsv": ("\n".join(sample_lines) + "\n").encode(),
        }
        manifest = b"".join(
            f"{hashlib.sha256(payloads[name]).hexdigest()}  {name}\n".encode()
            for name in sorted(payloads)
        )
        manifest_sha256 = hashlib.sha256(manifest).hexdigest()
        directory_name = (
            f"{incident.incident_reference}-transient-spd-20261024T100000+0200"
        )
        directory = self.failure.parent / "recovery-evidence" / directory_name
        directory.mkdir(parents=True)
        self.failure.parent.chmod(0o700)
        directory.parent.chmod(0o700)
        directory.chmod(0o700)
        for name, raw in (payloads | {"manifest.sha256": manifest}).items():
            path = directory / name
            path.write_bytes(raw)
            path.chmod(0o600)
        for path, raw in (
            (self.failure, failure_raw),
            (self.lifecycle_state, current_raw),
            (self.failure.parent / "ram-tetris-enabled", b"off\n"),
        ):
            path.write_bytes(raw)
            path.chmod(0o600)
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value=boot_id),
            mock.patch.object(recovery, "_current_suspend_count", return_value=11),
        ):
            observation = recovery._verify_transient_spd_observation(
                incident, directory_name, manifest_sha256
            )
        return incident, current_raw, observation

    def test_stable_code_mapping_and_subsystems(self):
        cases = {
            "writer termination was not preceded by an authenticated lifecycle stop request": (
                "LGT-LIF-002",
                "lifecycle",
            ),
            "OpenRGB SDK process identity changed": ("LGT-SDK-001", "sdk"),
            "OpenRGB returned an invalid SDK packet": ("LGT-SDK-001", "sdk"),
            "Effects profile has no effects": ("LGT-EFX-001", "effects"),
            "RAM Tetris preference changed": ("LGT-TET-001", "tetris"),
            "RAM Tetris writer refused the singleton lock (exit status 75); static restoration was not attempted": (
                "LGT-TET-002",
                "tetris",
            ),
            "RAM Tetris writer terminated by signal 15 (wait status 143); static restoration was not attempted": (
                "LGT-TET-002",
                "tetris",
            ),
            "RAM Tetris writer exited unexpectedly with status 1; static restoration was not attempted": (
                "LGT-TET-002",
                "tetris",
            ),
            "lifecycle stop request identity does not match writer": (
                "LGT-LIF-003",
                "lifecycle",
            ),
            "OpenRGB lifecycle explicitly refused SDK shutdown authentication before clean shutdown": (
                "LGT-LIF-001",
                "lifecycle",
            ),
            "expected seven controllers, found 6": ("LGT-CTL-001", "controller"),
            "DIMM state changed outside the Tetris writer: address 0x18": (
                "LGT-CTL-001",
                "controller",
            ),
            "10-0050 temperature is unreadable": ("LGT-CTL-002", "controller"),
            "kernel journal baseline is missing": ("LGT-KRN-001", "kernel"),
            "new relevant kernel error: i2c timeout": ("LGT-KRN-001", "kernel"),
        }
        for message, expected in cases.items():
            result = recovery.classify_reason(message)
            self.assertEqual((result.code, result.subsystem), expected, message)

    def test_unknown_error_is_explicit_and_nonrecoverable(self):
        result = recovery.classify_reason("a future failure not yet reviewed")
        self.assertEqual(result.code, "LGT-UNK-000")
        self.assertEqual(result.subsystem, "unknown")
        self.assertFalse(result.reviewed_recovery)

    def test_incident_references_are_stable_and_distinct(self):
        first = b'{"message":"first"}\n'
        second = b'{"message":"second"}\n'
        self.assertEqual(
            recovery._incident_reference(first), recovery._incident_reference(first)
        )
        self.assertNotEqual(
            recovery._incident_reference(first), recovery._incident_reference(second)
        )

    def test_current_incident_is_full_lighting_failure_and_blocked(self):
        raw = self.write_failure(
            "writer termination was not preceded by an authenticated lifecycle stop request"
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery, "_run_ram_tetris_status", return_value={"preference": True}
            ),
        ):
            value = recovery.status_document()
            self.assertTrue(value["failure"])
            self.assertEqual(value["scope"], "lighting")
            self.assertEqual(value["subsystem"], "lifecycle")
            self.assertEqual(value["code"], "LGT-LIF-002")
            self.assertFalse(value["recovery_available"])
            with self.assertRaises(recovery.RecoveryBlocked):
                recovery.prepare_document()
        self.assertEqual(self.failure.read_bytes(), raw)

    def test_exact_deliberate_lifecycle_boundary_is_confirmation_gated(self):
        failure_raw = self.write_failure(
            "writer termination was not preceded by an authenticated lifecycle stop request"
        )
        lifecycle_raw = self.write_lifecycle_state()
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value="boot-a"),
            mock.patch.object(recovery, "_process_start", return_value=None),
            mock.patch.object(
                recovery,
                "_verify_lifecycle_environment",
                return_value=self.config_raw,
            ) as verify,
            mock.patch.object(recovery, "OPENRGB_CONFIG", self.openrgb_config),
        ):
            value = recovery.prepare_document()
        verify.assert_called_once_with(1_792_000_000.0)
        self.assertEqual(value["state"], "confirmation-required")
        self.assertEqual(
            value["confirmation_token"],
            recovery._lifecycle_confirmation_token(
                failure_raw, lifecycle_raw, self.config_raw
            ),
        )

    def test_non_deliberate_or_uncorrelated_lifecycle_boundary_is_blocked(self):
        for reason, timestamp in (("handoff", 1_792_000_000.0), ("deliberate", 1.0)):
            with self.subTest(reason=reason, timestamp=timestamp):
                raw = self.write_failure(
                    "OpenRGB lifecycle service required manager escalation before clean shutdown"
                )
                self.write_lifecycle_state(reason=reason, timestamp=timestamp)
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery, "_current_boot_id", return_value="boot-a"
                    ),
                    mock.patch.object(recovery, "_process_start", return_value=None),
                    self.assertRaises(recovery.RecoveryBlocked),
                ):
                    recovery.prepare_document()
                self.assertEqual(self.failure.read_bytes(), raw)

    def test_missing_lifecycle_ownership_evidence_blocks_boundary_recovery(self):
        raw = self.write_failure(
            "OpenRGB lifecycle service did not complete its previous bounded shutdown"
        )
        self.write_lifecycle_state(include_server=False)
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value="boot-a"),
            mock.patch.object(recovery, "_process_start", return_value=None),
            self.assertRaises(recovery.RecoveryBlocked),
        ):
            recovery.prepare_document()
        self.assertEqual(self.failure.read_bytes(), raw)

    def test_live_lifecycle_owner_blocks_boundary_recovery(self):
        self.write_failure(
            "writer termination was not preceded by an authenticated lifecycle stop request"
        )
        self.write_lifecycle_state()
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value="boot-a"),
            mock.patch.object(
                recovery,
                "_process_start",
                side_effect=lambda pid: "4100" if pid == 41 else None,
            ),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "still active"),
        ):
            recovery.prepare_document()

    def test_lifecycle_start_failure_preserves_both_historical_records(self):
        failure_raw = self.write_failure(
            "writer termination was not preceded by an authenticated lifecycle stop request"
        )
        lifecycle_raw = self.write_lifecycle_state()
        token = recovery._lifecycle_confirmation_token(
            failure_raw, lifecycle_raw, self.config_raw
        )
        commands = [
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 1, "", "start failed"),
        ]
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_verify_lifecycle_recovery_preflight",
                return_value=(lifecycle_raw, self.config_raw),
            ),
            mock.patch.object(recovery, "OPENRGB_CONFIG", self.openrgb_config),
            mock.patch.object(recovery.subprocess, "run", side_effect=commands) as run,
            self.assertRaisesRegex(
                recovery.RecoveryBlocked, "single service start failed"
            ),
        ):
            recovery.recover(token)
        self.assertEqual(self.failure.read_bytes(), failure_raw)
        self.assertEqual(self.lifecycle_state.read_bytes(), lifecycle_raw)
        self.assertEqual(
            (self.failure.parent / "ram-tetris-enabled").read_bytes(), b"off\n"
        )
        reference = recovery._incident_reference(failure_raw)
        evidence = self.failure.parent / "recovery-evidence"
        self.assertEqual(
            (evidence / f"{reference}.failure.json").read_bytes(), failure_raw
        )
        self.assertEqual(
            (evidence / f"{reference}.lifecycle-state.json").read_bytes(),
            lifecycle_raw,
        )
        self.assertEqual(
            (evidence / f"{reference}.openrgb-config.json").read_bytes(),
            self.config_raw,
        )
        starts = [
            call
            for call in run.call_args_list
            if call.args[0][:3] == [recovery.SYSTEMCTL, "--user", "start"]
        ]
        self.assertEqual(len(starts), 1)

    def test_successful_lifecycle_recovery_starts_once_and_clears_after_acceptance(
        self,
    ):
        failure_raw = self.write_failure(
            "writer termination was not preceded by an authenticated lifecycle stop request"
        )
        lifecycle_raw = self.write_lifecycle_state()
        token = recovery._lifecycle_confirmation_token(
            failure_raw, lifecycle_raw, self.config_raw
        )
        completed = subprocess.CompletedProcess([], 0, "", "")
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_verify_lifecycle_recovery_preflight",
                return_value=(lifecycle_raw, self.config_raw),
            ),
            mock.patch.object(recovery, "OPENRGB_CONFIG", self.openrgb_config),
            mock.patch.object(
                recovery.subprocess, "run", return_value=completed
            ) as run,
            mock.patch.object(
                recovery, "_wait_for_authoritative_lifecycle_ready"
            ) as wait,
            mock.patch.object(recovery, "_verify_service_and_hardware") as verify,
        ):
            value = recovery.recover(token)
        self.assertEqual(value["state"], "recovered")
        wait.assert_called_once()
        verify.assert_called_once_with(1_792_000_000.0)
        self.assertFalse(self.failure.exists())
        self.assertEqual(
            (self.failure.parent / "ram-tetris-enabled").read_bytes(), b"off\n"
        )
        starts = [
            call
            for call in run.call_args_list
            if call.args[0][:3] == [recovery.SYSTEMCTL, "--user", "start"]
        ]
        self.assertEqual(len(starts), 1)

    def test_lifecycle_wait_uses_authoritative_ready_record(self):
        states = ({"state": "stopping"}, {"state": "starting"}, {"state": "ready"})
        with (
            mock.patch.object(recovery, "_read_service_state", side_effect=states),
            mock.patch.object(recovery.time, "sleep") as sleep,
        ):
            recovery._wait_for_authoritative_lifecycle_ready(time.monotonic() + 10)
        self.assertEqual(sleep.call_count, 2)

    def test_post_start_acceptance_failure_preserves_latch_and_evidence(self):
        failure_raw = self.write_failure(
            "writer termination was not preceded by an authenticated lifecycle stop request"
        )
        lifecycle_raw = self.write_lifecycle_state()
        token = recovery._lifecycle_confirmation_token(
            failure_raw, lifecycle_raw, self.config_raw
        )
        completed = subprocess.CompletedProcess([], 0, "", "")
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_verify_lifecycle_recovery_preflight",
                return_value=(lifecycle_raw, self.config_raw),
            ),
            mock.patch.object(recovery, "OPENRGB_CONFIG", self.openrgb_config),
            mock.patch.object(
                recovery.subprocess, "run", return_value=completed
            ) as run,
            mock.patch.object(
                recovery, "_wait_for_authoritative_lifecycle_ready"
            ) as wait,
            mock.patch.object(
                recovery,
                "_verify_service_and_hardware",
                side_effect=recovery.RecoveryBlocked(
                    "Recovery blocked: post-start acceptance failed."
                ),
            ),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "acceptance failed"),
        ):
            recovery.recover(token)
        wait.assert_called_once()
        self.assertEqual(self.failure.read_bytes(), failure_raw)
        self.assertEqual(self.lifecycle_state.read_bytes(), lifecycle_raw)
        self.assertEqual(
            (self.failure.parent / "ram-tetris-enabled").read_bytes(), b"off\n"
        )
        reference = recovery._incident_reference(failure_raw)
        evidence = self.failure.parent / "recovery-evidence"
        self.assertEqual(
            (evidence / f"{reference}.failure.json").read_bytes(), failure_raw
        )
        self.assertEqual(
            (evidence / f"{reference}.lifecycle-state.json").read_bytes(),
            lifecycle_raw,
        )
        starts = [
            call
            for call in run.call_args_list
            if call.args[0][:3] == [recovery.SYSTEMCTL, "--user", "start"]
        ]
        self.assertEqual(len(starts), 1)

    def test_display_code_alone_never_grants_eligibility(self):
        raw = self.write_failure("unreviewed failure")
        value = json.loads(raw)
        value["code"] = "LGT-TET-101"
        self.failure.write_text(json.dumps(value) + "\n", encoding="utf-8")
        with self.patched_environment(), self.assertRaises(recovery.RecoveryBlocked):
            recovery.prepare_document()

    def test_prepare_requires_exact_reviewed_reason_and_live_gates(self):
        raw = self.write_failure("expected one OpenRGB lifecycle, found 3")
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_verify_service_and_hardware") as verify,
        ):
            value = recovery.prepare_document()
        verify.assert_called_once()
        self.assertEqual(value["state"], "confirmation-required")
        self.assertEqual(value["confirmation_token"], hashlib.sha256(raw).hexdigest())

    def test_success_preserves_exact_evidence_and_leaves_preference_off(self):
        raw = self.write_failure("expected one OpenRGB lifecycle, found 3")
        preference = self.failure.parent / "ram-tetris-enabled"
        preference.write_text("on\n", encoding="utf-8")
        token = hashlib.sha256(raw).hexdigest()
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_verify_service_and_hardware") as verify,
        ):
            result = recovery.recover(token)
        verify.assert_called_once()
        self.assertEqual(result["state"], "recovered")
        self.assertEqual(preference.read_bytes(), b"off\n")
        self.assertFalse(self.failure.exists())
        evidence = (
            self.failure.parent
            / "recovery-evidence"
            / (recovery._incident_reference(raw) + ".failure.json")
        )
        self.assertEqual(evidence.read_bytes(), raw)
        self.assertEqual(evidence.stat().st_mode & 0o777, 0o600)

    def test_confirmation_is_required_and_wrong_token_preserves_latch(self):
        raw = self.write_failure("expected one OpenRGB lifecycle, found 3")
        with self.patched_environment(), self.assertRaises(recovery.RecoveryBlocked):
            recovery.recover("wrong")
        self.assertEqual(self.failure.read_bytes(), raw)

    def test_repeated_and_concurrent_recovery_attempts_fail_closed(self):
        raw = self.write_failure("expected one OpenRGB lifecycle, found 3")
        token = hashlib.sha256(raw).hexdigest()
        self.runtime.mkdir(parents=True)
        self.runtime.chmod(0o700)
        descriptor = os.open(
            self.runtime / "lighting-recovery.lock", os.O_WRONLY | os.O_CREAT, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (
                self.patched_environment(),
                self.assertRaises(recovery.RecoveryBlocked),
            ):
                recovery.recover(token)
        finally:
            os.close(descriptor)
        self.assertEqual(self.failure.read_bytes(), raw)

        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_verify_service_and_hardware"),
        ):
            recovery.recover(token)
            with self.assertRaises(recovery.RecoveryBlocked):
                recovery.recover(token)

    def test_hardware_and_unknown_failures_remain_blocked(self):
        for message in (
            "expected seven controllers, found 6",
            "new relevant kernel error: i2c timeout",
            "future unknown failure",
        ):
            with self.subTest(message=message):
                if self.failure.exists():
                    self.failure.unlink()
                raw = self.write_failure(message)
                with (
                    self.patched_environment(),
                    self.assertRaises(recovery.RecoveryBlocked),
                ):
                    recovery.prepare_document()
                self.assertEqual(self.failure.read_bytes(), raw)

    def healthy_verification_patches(self, *, health=None, journal=""):
        state = {
            "state": "ready",
            "boot_id": "boot-a",
            "lifecycle_pid": 41,
            "lifecycle_start": "4100",
            "server_pid": 42,
            "server_start": "4200",
        }
        health_value = health or {
            "controller_count": 7,
            "dimm_count": 4,
            "temperatures_mc": {
                "10-0050": 40_000,
                "10-0051": 40_000,
                "10-0052": 40_000,
                "10-0053": 40_000,
            },
        }
        completed = [
            subprocess.CompletedProcess([], 0, b"", b""),
            subprocess.CompletedProcess([], 0, json.dumps(health_value), ""),
            subprocess.CompletedProcess([], 0, journal, ""),
        ]

        def argv(pid):
            return recovery.LIFECYCLE_ARGV if pid == 41 else recovery.SERVER_ARGV

        def matches(expected):
            return (41,) if expected == recovery.LIFECYCLE_ARGV else (42,)

        patches = (
            mock.patch.object(recovery, "_read_service_state", return_value=state),
            mock.patch.object(recovery, "_current_boot_id", return_value="boot-a"),
            mock.patch.object(
                recovery, "_process_start", side_effect=lambda pid: f"{pid}00"
            ),
            mock.patch.object(recovery, "_process_argv", side_effect=argv),
            mock.patch.object(recovery, "_matching_processes", side_effect=matches),
            mock.patch.object(recovery, "_is_descendant", return_value=False),
            mock.patch.object(
                recovery,
                "_lock_is_owned",
                side_effect=lambda path: path.name == "lifecycle.lock",
            ),
            mock.patch.object(recovery.subprocess, "run", side_effect=completed),
            mock.patch.object(recovery, "PROC_ROOT", self.proc),
        )
        return patches

    def test_live_preflight_never_starts_a_tetris_writer(self):
        patches = self.healthy_verification_patches()
        with (
            self.patched_environment(),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patches[7] as run,
            patches[8],
        ):
            result = recovery._verify_service_and_hardware(1_792_000_000.0)
        self.assertEqual(result["controller_count"], 7)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn("validate-health", commands[1])
        self.assertNotIn("run", commands[1])

    def test_missing_lifecycle_or_sdk_blocks_recovery(self):
        for failed_pid in (41, 42):
            with self.subTest(pid=failed_pid):
                patches = self.healthy_verification_patches()
                with (
                    self.patched_environment(),
                    patches[0],
                    patches[1],
                    mock.patch.object(
                        recovery,
                        "_process_start",
                        side_effect=lambda pid, failed=failed_pid: (
                            None if pid == failed else f"{pid}00"
                        ),
                    ),
                    self.assertRaises(recovery.RecoveryBlocked),
                ):
                    recovery._verify_service_and_hardware(1_792_000_000.0)

    def test_service_unavailable_blocks_recovery(self):
        patches = self.healthy_verification_patches()
        unavailable = subprocess.CompletedProcess([], 3, b"", b"")
        with (
            self.patched_environment(),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            mock.patch.object(recovery.subprocess, "run", return_value=unavailable),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "service is unavailable"),
        ):
            recovery._verify_service_and_hardware(1_792_000_000.0)

    def test_active_writer_or_write_lock_blocks_recovery(self):
        for owned_name in ("ram-tetris.lock", "ram-tetris-write.lock"):
            patches = self.healthy_verification_patches()
            with (
                self.patched_environment(),
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                patches[4],
                patches[5],
                mock.patch.object(
                    recovery,
                    "_lock_is_owned",
                    side_effect=lambda path, owned=owned_name: (
                        path.name in {"lifecycle.lock", owned}
                    ),
                ),
                mock.patch.object(
                    recovery.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, b"", b""),
                ),
                self.assertRaises(recovery.RecoveryBlocked),
            ):
                recovery._verify_service_and_hardware(1_792_000_000.0)

    def test_missing_controller_or_spd_blocks_recovery(self):
        cases = (
            {"controller_count": 6, "dimm_count": 4, "temperatures_mc": {}},
            {
                "controller_count": 7,
                "dimm_count": 4,
                "temperatures_mc": {"10-0050": 40_000},
            },
        )
        for health in cases:
            patches = self.healthy_verification_patches(health=health)
            with (
                self.patched_environment(),
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                patches[4],
                patches[5],
                patches[6],
                patches[7],
                patches[8],
                self.assertRaises(recovery.RecoveryBlocked),
            ):
                recovery._verify_service_and_hardware(1_792_000_000.0)

    def test_kernel_communication_errors_block_recovery(self):
        patches = self.healthy_verification_patches(
            journal="kernel: i2c_designware controller timed out\n"
        )
        with (
            self.patched_environment(),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patches[7],
            patches[8],
            self.assertRaisesRegex(
                recovery.RecoveryBlocked, "kernel communication errors"
            ),
        ):
            recovery._verify_service_and_hardware(1_792_000_000.0)

    def test_historical_clearance_accepts_only_exact_incident_arguments(self):
        recovery._verify_historical_authorization(
            recovery.HISTORICAL_CLEARANCE_REFERENCE,
            recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
            recovery.HISTORICAL_CLEARANCE_REASON,
        )
        cases = (
            (
                "LR-WRONG",
                recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                recovery.HISTORICAL_CLEARANCE_REASON,
            ),
            (
                recovery.HISTORICAL_CLEARANCE_REFERENCE,
                "0" * 64,
                recovery.HISTORICAL_CLEARANCE_REASON,
            ),
            (
                recovery.HISTORICAL_CLEARANCE_REFERENCE,
                recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                "different reason",
            ),
        )
        for reference, checksum, reason in cases:
            with (
                self.subTest(reference=reference, checksum=checksum, reason=reason),
                self.assertRaisesRegex(
                    recovery.RecoveryBlocked, "authorization does not match"
                ),
            ):
                recovery._verify_historical_authorization(reference, checksum, reason)

    def test_historical_clearance_cli_requires_explicit_acknowledgement(self):
        arguments = [
            "clear-resolved-lifecycle",
            "--incident-reference",
            recovery.HISTORICAL_CLEARANCE_REFERENCE,
            "--latch-sha256",
            recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
            "--original-reason",
            recovery.HISTORICAL_CLEARANCE_REASON,
        ]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            recovery.build_parser().parse_args(arguments)
        parsed = recovery.build_parser().parse_args(
            arguments + ["--acknowledge-historical-clearance"]
        )
        self.assertEqual(parsed.action, "clear-resolved-lifecycle")
        self.assertTrue(parsed.acknowledge_historical_clearance)

    def test_historical_clearance_preflight_binds_preserved_records(self):
        failure_raw, boundary_raw, config_raw, current_raw = (
            self.write_historical_clearance_records()
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "HISTORICAL_CLEARANCE_BOUNDARY_SHA256",
                hashlib.sha256(boundary_raw).hexdigest(),
            ),
            mock.patch.object(
                recovery,
                "HISTORICAL_CLEARANCE_CONFIG_SHA256",
                hashlib.sha256(config_raw).hexdigest(),
            ),
            mock.patch.object(recovery, "_current_boot_id", return_value="boot-a"),
            mock.patch.object(recovery, "_process_start", return_value=None),
            mock.patch.object(
                recovery, "_verify_historical_running_environment"
            ) as runtime_verify,
            mock.patch.object(recovery, "_verify_service_and_hardware") as health,
        ):
            binding = recovery._historical_clearance_preflight(
                recovery.HISTORICAL_CLEARANCE_REFERENCE,
                recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                recovery.HISTORICAL_CLEARANCE_REASON,
            )
        self.assertEqual(
            binding,
            recovery.HistoricalClearanceBinding(
                failure_raw, boundary_raw, config_raw, current_raw
            ),
        )
        runtime_verify.assert_called_once()
        health.assert_called_once_with(1_792_308_226.2688146)

    def test_historical_running_environment_is_read_only_and_fully_owned(self):
        _, _, config_raw, current_raw = self.write_historical_clearance_records()
        current = json.loads(current_raw)
        unit = self.root / "reviewed.service"
        unit.write_text("reviewed\n", encoding="utf-8")
        service = {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running",
            "Result": "success",
            "MainPID": "51",
            "ControlPID": "0",
            "ControlGroup": "/user.slice/openrgb.service",
            "FragmentPath": str(unit),
            "UnitFileState": "enabled",
            "WantedBy": recovery.GRAPHICAL_TARGET,
            "PartOf": recovery.GRAPHICAL_TARGET,
            "DropInPaths": "",
            "NeedDaemonReload": "no",
            "Type": "notify",
            "Restart": "no",
            "KillMode": "mixed",
            "TimeoutStartUSec": "2min",
            "TimeoutStopUSec": "20s",
        }
        target = {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "active",
        }

        def argv(pid):
            return {
                51: recovery.LIFECYCLE_ARGV,
                52: recovery.SERVER_ARGV,
                53: recovery.INHIBITOR_ARGV,
                54: recovery.MONITOR_ARGV,
            }[pid]

        def matches(expected):
            return {
                recovery.LIFECYCLE_ARGV: (51,),
                recovery.SERVER_ARGV: (52,),
                recovery.INHIBITOR_ARGV: (53,),
                recovery.MONITOR_ARGV: (54,),
            }[expected]

        commands = (
            subprocess.CompletedProcess(
                [], 0, recovery.EXPECTED_OPENRGB_PACKAGE + "\n", ""
            ),
            subprocess.CompletedProcess(
                [],
                0,
                'LISTEN 0 4096 127.0.0.1:6742 users:(("openrgb",pid=52,fd=4))\n',
                "",
            ),
        )
        executable = self.root / "openrgb"
        executable.write_bytes(b"reviewed executable")
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "INSTALLED_UNIT", unit),
            mock.patch.object(recovery, "_unit_is_reviewed"),
            mock.patch.object(
                recovery,
                "_service_properties",
                side_effect=lambda name, _properties: (
                    service if name == recovery.SERVICE_NAME else target
                ),
            ),
            mock.patch.object(
                recovery, "_process_start", side_effect=lambda pid: f"{pid}00"
            ),
            mock.patch.object(recovery, "_process_argv", side_effect=argv),
            mock.patch.object(recovery, "_matching_processes", side_effect=matches),
            mock.patch.object(recovery, "_is_descendant", return_value=True),
            mock.patch.object(
                recovery,
                "_process_cgroup",
                return_value="/user.slice/openrgb.service",
            ),
            mock.patch.object(
                recovery,
                "_lock_is_owned",
                side_effect=lambda path: path.name == "lifecycle.lock",
            ),
            mock.patch.object(
                recovery, "_detector_policy_is_reviewed", return_value=config_raw
            ),
            mock.patch.object(recovery, "PROC_ROOT", self.proc),
            mock.patch.object(recovery, "OPENRGB_EXECUTABLE", executable),
            mock.patch.object(
                recovery,
                "EXPECTED_OPENRGB_EXECUTABLE_SHA256",
                hashlib.sha256(executable.read_bytes()).hexdigest(),
            ),
            mock.patch.object(recovery.subprocess, "run", side_effect=commands) as run,
        ):
            recovery._verify_historical_running_environment(current, config_raw)
        invoked = [call.args[0] for call in run.call_args_list]
        self.assertEqual(invoked[0], [recovery.PACMAN, "-Q", "openrgb-hugin"])
        self.assertEqual(invoked[1][0], recovery.SS)
        self.assertFalse(
            any(
                isinstance(command, list)
                and any(action in command for action in ("start", "stop", "restart"))
                for command in invoked
            )
        )

    def test_reviewed_openrgb_package_requires_exact_package_and_executable(self):
        executable = self.root / "openrgb"
        executable.write_bytes(b"approved executable")
        approved_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
        package = subprocess.CompletedProcess(
            [], 0, recovery.EXPECTED_OPENRGB_PACKAGE + "\n", ""
        )
        with (
            mock.patch.object(recovery, "OPENRGB_EXECUTABLE", executable),
            mock.patch.object(
                recovery, "EXPECTED_OPENRGB_EXECUTABLE_SHA256", approved_sha256
            ),
            mock.patch.object(recovery.subprocess, "run", return_value=package) as run,
        ):
            recovery._reviewed_openrgb_package_is_installed()
        run.assert_called_once_with(
            [recovery.PACMAN, "-Q", "openrgb-hugin"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        cases = (
            (
                "wrong package",
                subprocess.CompletedProcess([], 0, "openrgb 1.0rc3-3\n", ""),
                approved_sha256,
            ),
            ("wrong executable", package, "0" * 64),
        )
        for label, result, expected_sha256 in cases:
            with (
                self.subTest(label=label),
                mock.patch.object(recovery, "OPENRGB_EXECUTABLE", executable),
                mock.patch.object(
                    recovery,
                    "EXPECTED_OPENRGB_EXECUTABLE_SHA256",
                    expected_sha256,
                ),
                mock.patch.object(recovery.subprocess, "run", return_value=result),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "not reviewed"),
            ):
                recovery._reviewed_openrgb_package_is_installed()

    def test_historical_clearance_rejects_changed_latch_or_evidence(self):
        for changed in ("latch", "failure-evidence", "boundary", "config"):
            with self.subTest(changed=changed):
                failure_raw, boundary_raw, config_raw, _ = (
                    self.write_historical_clearance_records()
                )
                evidence = self.failure.parent / "recovery-evidence"
                target = {
                    "latch": self.failure,
                    "failure-evidence": evidence
                    / f"{recovery.HISTORICAL_CLEARANCE_REFERENCE}.failure.json",
                    "boundary": evidence
                    / f"{recovery.HISTORICAL_CLEARANCE_REFERENCE}.lifecycle-state.json",
                    "config": evidence
                    / f"{recovery.HISTORICAL_CLEARANCE_REFERENCE}.openrgb-config.json",
                }[changed]
                target.write_bytes(target.read_bytes() + b"changed")
                target.chmod(0o600)
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery,
                        "HISTORICAL_CLEARANCE_BOUNDARY_SHA256",
                        hashlib.sha256(boundary_raw).hexdigest(),
                    ),
                    mock.patch.object(
                        recovery,
                        "HISTORICAL_CLEARANCE_CONFIG_SHA256",
                        hashlib.sha256(config_raw).hexdigest(),
                    ),
                    self.assertRaises(recovery.RecoveryBlocked),
                ):
                    recovery._historical_clearance_preflight(
                        recovery.HISTORICAL_CLEARANCE_REFERENCE,
                        recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                        recovery.HISTORICAL_CLEARANCE_REASON,
                    )
                if changed != "latch":
                    self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_historical_clearance_blocks_unhealthy_lifecycle_or_sdk(self):
        failure_raw, boundary_raw, config_raw, _ = (
            self.write_historical_clearance_records()
        )
        for verifier, message in (
            ("_verify_historical_acknowledgement", "lifecycle is not ready"),
            ("_verify_historical_running_environment", "SDK identity is not healthy"),
        ):
            with self.subTest(verifier=verifier):
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery,
                        "HISTORICAL_CLEARANCE_BOUNDARY_SHA256",
                        hashlib.sha256(boundary_raw).hexdigest(),
                    ),
                    mock.patch.object(
                        recovery,
                        "HISTORICAL_CLEARANCE_CONFIG_SHA256",
                        hashlib.sha256(config_raw).hexdigest(),
                    ),
                    mock.patch.object(
                        recovery,
                        verifier,
                        side_effect=recovery.RecoveryBlocked(message),
                    ),
                    self.assertRaises(recovery.RecoveryBlocked),
                ):
                    recovery._historical_clearance_preflight(
                        recovery.HISTORICAL_CLEARANCE_REFERENCE,
                        recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                        recovery.HISTORICAL_CLEARANCE_REASON,
                    )
                self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_historical_clearance_blocks_health_inventory_and_kernel_failures(self):
        failure_raw, boundary_raw, config_raw, _ = (
            self.write_historical_clearance_records()
        )
        for message in (
            "accepted controller inventory is incomplete",
            "four SPD5118 endpoints were not verified",
            "relevant kernel communication errors exist",
        ):
            with self.subTest(message=message):
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery,
                        "HISTORICAL_CLEARANCE_BOUNDARY_SHA256",
                        hashlib.sha256(boundary_raw).hexdigest(),
                    ),
                    mock.patch.object(
                        recovery,
                        "HISTORICAL_CLEARANCE_CONFIG_SHA256",
                        hashlib.sha256(config_raw).hexdigest(),
                    ),
                    mock.patch.object(
                        recovery,
                        "_verify_historical_acknowledgement",
                        return_value=1_792_308_226.2688146,
                    ),
                    mock.patch.object(
                        recovery, "_verify_historical_running_environment"
                    ),
                    mock.patch.object(
                        recovery,
                        "_verify_service_and_hardware",
                        side_effect=recovery.RecoveryBlocked(message),
                    ),
                    self.assertRaises(recovery.RecoveryBlocked),
                ):
                    recovery._historical_clearance_preflight(
                        recovery.HISTORICAL_CLEARANCE_REFERENCE,
                        recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                        recovery.HISTORICAL_CLEARANCE_REASON,
                    )
                self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_historical_clearance_blocks_writer_or_ownership_conflict(self):
        failure_raw, boundary_raw, config_raw, _ = (
            self.write_historical_clearance_records()
        )
        for message in (
            "a RAM Tetris writer is active",
            "lifecycle or SDK ownership is ambiguous",
        ):
            with self.subTest(message=message):
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery,
                        "HISTORICAL_CLEARANCE_BOUNDARY_SHA256",
                        hashlib.sha256(boundary_raw).hexdigest(),
                    ),
                    mock.patch.object(
                        recovery,
                        "HISTORICAL_CLEARANCE_CONFIG_SHA256",
                        hashlib.sha256(config_raw).hexdigest(),
                    ),
                    mock.patch.object(
                        recovery,
                        "_verify_historical_acknowledgement",
                        return_value=1_792_308_226.2688146,
                    ),
                    mock.patch.object(
                        recovery,
                        "_verify_historical_running_environment",
                        side_effect=recovery.RecoveryBlocked(message),
                    ),
                    self.assertRaises(recovery.RecoveryBlocked),
                ):
                    recovery._historical_clearance_preflight(
                        recovery.HISTORICAL_CLEARANCE_REFERENCE,
                        recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                        recovery.HISTORICAL_CLEARANCE_REASON,
                    )
                self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_historical_clearance_revalidates_and_retains_protected_evidence(self):
        failure_raw, boundary_raw, config_raw, current_raw = (
            self.write_historical_clearance_records()
        )
        binding = recovery.HistoricalClearanceBinding(
            failure_raw, boundary_raw, config_raw, current_raw
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery, "_historical_clearance_preflight", return_value=binding
            ) as preflight,
            mock.patch.object(
                recovery.subprocess,
                "run",
                side_effect=AssertionError("no service or RGB operation is permitted"),
            ),
        ):
            result = recovery.clear_resolved_lifecycle(
                recovery.HISTORICAL_CLEARANCE_REFERENCE,
                recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                recovery.HISTORICAL_CLEARANCE_REASON,
            )
        self.assertEqual(result["state"], "cleared")
        self.assertEqual(preflight.call_count, 2)
        self.assertFalse(self.failure.exists())
        self.assertEqual(
            (self.failure.parent / "ram-tetris-enabled").read_bytes(), b"off\n"
        )
        evidence = (
            self.failure.parent
            / "recovery-evidence"
            / f"{recovery.HISTORICAL_CLEARANCE_REFERENCE}.historical-clearance.json"
        )
        self.assertEqual(evidence.read_bytes(), failure_raw)
        self.assertEqual(evidence.stat().st_mode & 0o777, 0o600)

    def test_historical_clearance_binding_change_preserves_latch(self):
        failure_raw, boundary_raw, config_raw, current_raw = (
            self.write_historical_clearance_records()
        )
        first = recovery.HistoricalClearanceBinding(
            failure_raw, boundary_raw, config_raw, current_raw
        )
        second = recovery.HistoricalClearanceBinding(
            failure_raw, boundary_raw, config_raw, current_raw + b"changed"
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_historical_clearance_preflight",
                side_effect=(first, second),
            ),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "bindings changed"),
        ):
            recovery.clear_resolved_lifecycle(
                recovery.HISTORICAL_CLEARANCE_REFERENCE,
                recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                recovery.HISTORICAL_CLEARANCE_REASON,
            )
        self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_concurrent_historical_clearance_is_blocked(self):
        failure_raw, _, _, _ = self.write_historical_clearance_records()
        self.runtime.mkdir(parents=True)
        self.runtime.chmod(0o700)
        descriptor = os.open(
            self.runtime / "lighting-recovery.lock", os.O_WRONLY | os.O_CREAT, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (
                self.patched_environment(),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "another recovery"),
            ):
                recovery.clear_resolved_lifecycle(
                    recovery.HISTORICAL_CLEARANCE_REFERENCE,
                    recovery.HISTORICAL_CLEARANCE_LATCH_SHA256,
                    recovery.HISTORICAL_CLEARANCE_REASON,
                )
        finally:
            os.close(descriptor)
        self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_reviewed_software_race_cli_requires_explicit_acknowledgement(self):
        reviewed = recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST["LR-3903E50F10DAA4FD"]
        arguments = [
            "clear-reviewed-software-race",
            "--incident-reference",
            reviewed.incident_reference,
            "--latch-sha256",
            reviewed.latch_sha256,
            "--error-code",
            reviewed.code,
            "--original-reason",
            reviewed.original_reason,
        ]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            recovery.build_parser().parse_args(arguments)
        parsed = recovery.build_parser().parse_args(
            arguments + ["--acknowledge-reviewed-software-race"]
        )
        self.assertEqual(parsed.action, "clear-reviewed-software-race")
        self.assertTrue(parsed.acknowledge_reviewed_software_race)

    def test_reviewed_software_race_accepts_only_exact_allowlisted_binding(self):
        reviewed = recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST["LR-3903E50F10DAA4FD"]
        self.assertEqual(
            recovery._reviewed_software_race_authorization(
                reviewed.incident_reference,
                reviewed.latch_sha256,
                reviewed.code,
                reviewed.original_reason,
            ),
            reviewed,
        )
        cases = (
            (
                "LR-WRONG",
                reviewed.latch_sha256,
                reviewed.code,
                reviewed.original_reason,
            ),
            (
                reviewed.incident_reference,
                "0" * 64,
                reviewed.code,
                reviewed.original_reason,
            ),
            (
                reviewed.incident_reference,
                reviewed.latch_sha256,
                "LGT-TET-001",
                reviewed.original_reason,
            ),
            (
                reviewed.incident_reference,
                reviewed.latch_sha256,
                reviewed.code,
                "different reason",
            ),
        )
        for reference, checksum, code, reason in cases:
            with (
                self.subTest(reference=reference, checksum=checksum, code=code),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "allowlisted"),
            ):
                recovery._reviewed_software_race_authorization(
                    reference, checksum, code, reason
                )
        self.assertFalse(
            recovery.classify_reason(reviewed.original_reason).reviewed_recovery
        )
        self.assertNotIn(reviewed.original_reason, recovery.ELIGIBLE_REASONS)

    def test_reviewed_software_race_requires_corrected_source_ancestry(self):
        reviewed = recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST["LR-3903E50F10DAA4FD"]
        commands = (
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "a" * 40 + "\n", ""),
            subprocess.CompletedProcess([], 1, "", "not an ancestor"),
        )
        with (
            mock.patch.object(recovery.subprocess, "run", side_effect=commands),
            self.assertRaisesRegex(
                recovery.RecoveryBlocked, "does not contain the reviewed"
            ),
        ):
            recovery._verify_corrected_source_revision(
                reviewed.minimum_corrected_source
            )

    def test_reviewed_software_race_preflight_binds_runtime_and_evidence(self):
        failure_raw, current_raw = self.write_reviewed_software_race_records()
        reviewed = recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST["LR-3903E50F10DAA4FD"]
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery, "_verify_corrected_source_revision", return_value="a" * 40
            ),
            mock.patch.object(
                recovery, "_detector_policy_is_reviewed", return_value=self.config_raw
            ),
            mock.patch.object(
                recovery, "_verify_historical_running_environment"
            ) as runtime_verify,
            mock.patch.object(recovery, "_verify_service_and_hardware") as health,
        ):
            binding = recovery._software_race_clearance_preflight(
                reviewed.incident_reference,
                reviewed.latch_sha256,
                reviewed.code,
                reviewed.original_reason,
            )
        self.assertEqual(
            binding,
            recovery.SoftwareRaceClearanceBinding(
                failure_raw,
                current_raw,
                self.config_raw,
                1_792_561_532.70337,
                "a" * 40,
            ),
        )
        runtime_verify.assert_called_once()
        health.assert_called_once_with(1_792_561_532.70337)

    def test_reviewed_software_race_propagates_runtime_health_failures(self):
        reviewed = recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST["LR-3903E50F10DAA4FD"]
        cases = (
            ("runtime", "a RAM Tetris writer is active"),
            ("runtime", "lifecycle or SDK ownership is ambiguous"),
            ("health", "accepted controller inventory is incomplete"),
            ("health", "four SPD5118 endpoints were not verified"),
            ("health", "relevant kernel communication errors exist"),
        )
        for verifier, message in cases:
            with self.subTest(verifier=verifier, message=message):
                failure_raw, _ = self.write_reviewed_software_race_records()
                runtime_effect = (
                    recovery.RecoveryBlocked(message) if verifier == "runtime" else None
                )
                health_effect = (
                    recovery.RecoveryBlocked(message) if verifier == "health" else None
                )
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery,
                        "_verify_corrected_source_revision",
                        return_value="a" * 40,
                    ),
                    mock.patch.object(
                        recovery,
                        "_detector_policy_is_reviewed",
                        return_value=self.config_raw,
                    ),
                    mock.patch.object(
                        recovery,
                        "_verify_historical_running_environment",
                        side_effect=runtime_effect,
                    ),
                    mock.patch.object(
                        recovery,
                        "_verify_service_and_hardware",
                        side_effect=health_effect,
                    ),
                    self.assertRaisesRegex(recovery.RecoveryBlocked, message),
                ):
                    recovery._software_race_clearance_preflight(
                        reviewed.incident_reference,
                        reviewed.latch_sha256,
                        reviewed.code,
                        reviewed.original_reason,
                    )
                self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_reviewed_software_race_clearance_is_read_only_except_evidence_and_latch(
        self,
    ):
        failure_raw, current_raw = self.write_reviewed_software_race_records()
        reviewed = recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST["LR-3903E50F10DAA4FD"]
        binding = recovery.SoftwareRaceClearanceBinding(
            failure_raw,
            current_raw,
            self.config_raw,
            1_792_561_532.70337,
            "a" * 40,
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_software_race_clearance_preflight",
                return_value=binding,
            ) as preflight,
            mock.patch.object(
                recovery, "_verify_software_race_continuity"
            ) as continuity,
            mock.patch.object(
                recovery.subprocess,
                "run",
                side_effect=AssertionError("no service or RGB operation is permitted"),
            ),
        ):
            result = recovery.clear_reviewed_software_race(
                reviewed.incident_reference,
                reviewed.latch_sha256,
                reviewed.code,
                reviewed.original_reason,
            )
        self.assertEqual(
            result,
            {
                "failure": False,
                "incident_reference": reviewed.incident_reference,
                "message": (
                    "Reviewed software-race latch cleared. RAM Tetris remains OFF."
                ),
                "preference": False,
                "state": "off",
            },
        )
        self.assertEqual(preflight.call_count, 2)
        continuity.assert_called_once_with(reviewed, binding)
        self.assertFalse(self.failure.exists())
        self.assertEqual(
            (self.failure.parent / "ram-tetris-enabled").read_bytes(), b"off\n"
        )
        evidence = self.failure.parent / "recovery-evidence"
        for kind, raw in (
            ("failure", failure_raw),
            ("lifecycle-state", current_raw),
            ("openrgb-config", self.config_raw),
        ):
            path = evidence / f"{reviewed.incident_reference}.{kind}.json"
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_reviewed_software_race_rejects_altered_or_unwritable_evidence(self):
        for case in ("altered", "changed-after-review", "write-failure"):
            with self.subTest(case=case):
                failure_raw, current_raw = self.write_reviewed_software_race_records()
                reviewed = recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST[
                    "LR-3903E50F10DAA4FD"
                ]
                binding = recovery.SoftwareRaceClearanceBinding(
                    failure_raw,
                    current_raw,
                    self.config_raw,
                    1_792_561_532.70337,
                    "a" * 40,
                )
                evidence = self.failure.parent / "recovery-evidence"
                evidence.mkdir(exist_ok=True)
                evidence.chmod(0o700)
                preflight = mock.patch.object(
                    recovery,
                    "_software_race_clearance_preflight",
                    return_value=binding,
                )
                if case == "altered":
                    target = evidence / f"{reviewed.incident_reference}.failure.json"
                    target.write_bytes(b"altered\n")
                    target.chmod(0o600)
                    preserve = mock.patch.object(
                        recovery,
                        "_preserve_evidence",
                        wraps=recovery._preserve_evidence,
                    )
                elif case == "changed-after-review":
                    calls = 0

                    def review(
                        *_args,
                        evidence=evidence,
                        reviewed=reviewed,
                        binding=binding,
                    ):
                        nonlocal calls
                        calls += 1
                        if calls == 2:
                            target = (
                                evidence / f"{reviewed.incident_reference}.failure.json"
                            )
                            target.write_bytes(b"altered after review\n")
                        return binding

                    preflight = mock.patch.object(
                        recovery,
                        "_software_race_clearance_preflight",
                        side_effect=review,
                    )
                    preserve = mock.patch.object(
                        recovery,
                        "_preserve_evidence",
                        wraps=recovery._preserve_evidence,
                    )
                else:
                    preserve = mock.patch.object(
                        recovery,
                        "_preserve_evidence",
                        side_effect=OSError("evidence write failed"),
                    )
                with (
                    self.patched_environment(),
                    preflight,
                    preserve,
                    self.assertRaises((recovery.RecoveryBlocked, OSError)),
                ):
                    recovery.clear_reviewed_software_race(
                        reviewed.incident_reference,
                        reviewed.latch_sha256,
                        reviewed.code,
                        reviewed.original_reason,
                    )
                self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_reviewed_software_race_detects_latch_change_before_unlink(self):
        failure_raw, current_raw = self.write_reviewed_software_race_records()
        reviewed = recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST["LR-3903E50F10DAA4FD"]
        binding = recovery.SoftwareRaceClearanceBinding(
            failure_raw,
            current_raw,
            self.config_raw,
            1_792_561_532.70337,
            "a" * 40,
        )
        calls = 0

        def preflight(*_args):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.failure.write_bytes(failure_raw + b"changed")
            return binding

        with (
            self.patched_environment(),
            mock.patch.object(
                recovery, "_software_race_clearance_preflight", side_effect=preflight
            ),
            self.assertRaisesRegex(
                recovery.RecoveryBlocked, "changed before clearance"
            ),
        ):
            recovery.clear_reviewed_software_race(
                reviewed.incident_reference,
                reviewed.latch_sha256,
                reviewed.code,
                reviewed.original_reason,
            )
        self.assertTrue(self.failure.exists())

    def test_concurrent_reviewed_software_race_clearance_is_blocked(self):
        failure_raw, _ = self.write_reviewed_software_race_records()
        reviewed = recovery.REVIEWED_SOFTWARE_RACE_ALLOWLIST["LR-3903E50F10DAA4FD"]
        self.runtime.mkdir(parents=True)
        self.runtime.chmod(0o700)
        descriptor = os.open(
            self.runtime / "lighting-recovery.lock", os.O_WRONLY | os.O_CREAT, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (
                self.patched_environment(),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "another recovery"),
            ):
                recovery.clear_reviewed_software_race(
                    reviewed.incident_reference,
                    reviewed.latch_sha256,
                    reviewed.code,
                    reviewed.original_reason,
                )
        finally:
            os.close(descriptor)
        self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_corrected_software_interruption_cli_requires_acknowledgement(self):
        arguments = [
            "clear-reviewed-software-interruption",
            "--incident-reference",
            "LR-0123456789ABCDEF",
            "--latch-sha256",
            "0" * 64,
            "--error-code",
            "LGT-TET-001",
            "--original-reason",
            recovery.CORRECTED_CHECKPOINT_REASON,
        ]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            recovery.build_parser().parse_args(arguments)
        parsed = recovery.build_parser().parse_args(
            arguments + ["--acknowledge-reviewed-software-interruption"]
        )
        self.assertEqual(parsed.action, "clear-reviewed-software-interruption")
        self.assertTrue(parsed.acknowledge_reviewed_software_interruption)

    def test_corrected_software_interruption_accepts_multiple_derived_references(self):
        references = set()
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_verify_corrected_source_revision",
                return_value=recovery.CORRECTED_CHECKPOINT_MINIMUM_REVISION,
            ),
            mock.patch.object(
                recovery,
                "_source_blob_sha256",
                return_value=recovery.CORRECTED_CHECKPOINT_SOURCE_SHA256,
            ) as source_blob,
        ):
            for pid in (1227358, 1227359):
                raw, _ = self.write_corrected_software_interruption_records(pid=pid)
                incident = recovery._classify_corrected_software_interruption()
                self.assertEqual(
                    incident.incident_reference, recovery._incident_reference(raw)
                )
                self.assertEqual(incident.latch_sha256, hashlib.sha256(raw).hexdigest())
                references.add(incident.incident_reference)
        self.assertEqual(len(references), 2)
        source_blob.assert_called_with(
            recovery.CORRECTED_CHECKPOINT_SOURCE_REVISION,
            recovery.CORRECTED_CHECKPOINT_SOURCE_PATH,
        )

    def test_corrected_software_interruption_rejects_wrong_evidence_and_failures(self):
        cases = (
            ({"failure_kind": "spd5118-temperature"}, None, "reviewed corrected"),
            ({"checkpoint_interval_ms": 251.0}, None, "reviewed corrected"),
            ({"checkpoint_deadline_ms": 1999.0}, None, "reviewed corrected"),
            ({"kernel_messages": ["i2c error"]}, None, "reviewed corrected"),
            (None, {"revision": "0" * 40}, "not an eligible"),
            (None, {"sha256": "0" * 64}, "not an eligible"),
        )
        for details, source, message in cases:
            with self.subTest(details=details, source=source):
                self.write_corrected_software_interruption_records(
                    detail_overrides=details, source_overrides=source
                )
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery,
                        "_verify_corrected_source_revision",
                        return_value=recovery.CORRECTED_CHECKPOINT_MINIMUM_REVISION,
                    ),
                    mock.patch.object(
                        recovery,
                        "_source_blob_sha256",
                        return_value=recovery.CORRECTED_CHECKPOINT_SOURCE_SHA256,
                    ),
                    self.assertRaisesRegex(recovery.RecoveryBlocked, message),
                ):
                    recovery._classify_corrected_software_interruption()

        for reason in ("10-0053 temperature is unreadable", "unknown failure"):
            with self.subTest(reason=reason):
                self.write_failure(reason)
                with (
                    self.patched_environment(),
                    self.assertRaisesRegex(recovery.RecoveryBlocked, "not an eligible"),
                ):
                    recovery._classify_corrected_software_interruption()

    def test_corrected_software_interruption_requires_clean_corrected_source(self):
        self.write_corrected_software_interruption_records()
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_source_blob_sha256",
                return_value=recovery.CORRECTED_CHECKPOINT_SOURCE_SHA256,
            ),
            mock.patch.object(
                recovery,
                "_verify_corrected_source_revision",
                side_effect=recovery.RecoveryBlocked("installed source is not clean"),
            ),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "not clean"),
        ):
            recovery._classify_corrected_software_interruption()

        self.write_corrected_software_interruption_records()
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_source_blob_sha256", return_value="0" * 64),
            mock.patch.object(
                recovery,
                "_verify_corrected_source_revision",
                return_value=recovery.CORRECTED_CHECKPOINT_MINIMUM_REVISION,
            ),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "provenance changed"),
        ):
            recovery._classify_corrected_software_interruption()

    def test_corrected_software_authorization_is_derived_from_raw_latch(self):
        raw, _ = self.write_corrected_software_interruption_records()
        reference = recovery._incident_reference(raw)
        checksum = hashlib.sha256(raw).hexdigest()
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_verify_corrected_source_revision",
                return_value=recovery.CORRECTED_CHECKPOINT_MINIMUM_REVISION,
            ),
            mock.patch.object(
                recovery,
                "_source_blob_sha256",
                return_value=recovery.CORRECTED_CHECKPOINT_SOURCE_SHA256,
            ),
        ):
            accepted = recovery._corrected_software_interruption_authorization(
                reference,
                checksum,
                "LGT-TET-001",
                recovery.CORRECTED_CHECKPOINT_REASON,
            )
            self.assertEqual(accepted.incident_reference, reference)
            for arguments in (
                ("LR-0000000000000000", checksum, "LGT-TET-001"),
                (reference, "0" * 64, "LGT-TET-001"),
                (reference, checksum, "LGT-CTL-002"),
            ):
                with self.assertRaisesRegex(
                    recovery.RecoveryBlocked, "raw failure latch"
                ):
                    recovery._corrected_software_interruption_authorization(
                        *arguments, recovery.CORRECTED_CHECKPOINT_REASON
                    )

    def test_corrected_software_journal_retains_history_and_rejects_new_events(self):
        completed = lambda output="": subprocess.CompletedProcess([], 0, output, "")
        retained_kernel = "spd5118 10-0053: PM: failed to resume: error -6\n"
        retained_service = "Main process exited before authoritative readiness\n"
        with mock.patch.object(
            recovery.subprocess,
            "run",
            side_effect=(
                completed(retained_kernel),
                completed(retained_service),
                completed(),
                completed(),
            ),
        ):
            raw = recovery._software_interruption_journal_evidence(10.0, 20.0)
        document = json.loads(raw)
        self.assertEqual(document["historical_kernel"], retained_kernel)
        self.assertEqual(document["historical_service"], retained_service)

        post_cases = (
            ("spd5118 10-0053: read failed: error -6\n", "", "kernel"),
            ("PM: suspend entry (deep)\n", "", "kernel"),
            ("", "Main process exited, code=exited, status=1\n", "service"),
        )
        for post_kernel, post_service, message in post_cases:
            with (
                self.subTest(post_kernel=post_kernel, post_service=post_service),
                mock.patch.object(
                    recovery.subprocess,
                    "run",
                    side_effect=(
                        completed(retained_kernel),
                        completed(retained_service),
                        completed(post_kernel),
                        completed(post_service),
                    ),
                ),
                self.assertRaisesRegex(recovery.RecoveryBlocked, message),
            ):
                recovery._software_interruption_journal_evidence(10.0, 20.0)

    def test_corrected_software_interruption_preflight_binds_all_evidence(self):
        failure_raw, current_raw = self.write_corrected_software_interruption_records()
        incident = recovery.CorrectedSoftwareInterruption(
            failure_raw=failure_raw,
            incident_reference=recovery._incident_reference(failure_raw),
            latch_sha256=hashlib.sha256(failure_raw).hexdigest(),
            original_reason=recovery.CORRECTED_CHECKPOINT_REASON,
            failure_time=1_792_864_340.6402085,
            source_revision=recovery.CORRECTED_CHECKPOINT_SOURCE_REVISION,
            source_path=recovery.CORRECTED_CHECKPOINT_SOURCE_PATH,
            source_sha256=recovery.CORRECTED_CHECKPOINT_SOURCE_SHA256,
        )
        journal_raw = b'{"category":"corrected-software-interruption"}\n'
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_corrected_software_interruption_authorization",
                return_value=incident,
            ),
            mock.patch.object(
                recovery,
                "_verify_corrected_source_revision",
                return_value=recovery.CORRECTED_CHECKPOINT_MINIMUM_REVISION,
            ),
            mock.patch.object(
                recovery, "_detector_policy_is_reviewed", return_value=self.config_raw
            ),
            mock.patch.object(
                recovery, "_verify_historical_running_environment"
            ) as runtime_verify,
            mock.patch.object(recovery, "_verify_service_and_hardware") as health,
            mock.patch.object(
                recovery,
                "_software_interruption_journal_evidence",
                return_value=journal_raw,
            ),
        ):
            binding = recovery._corrected_software_interruption_preflight(
                incident.incident_reference,
                incident.latch_sha256,
                "LGT-TET-001",
                incident.original_reason,
            )
        self.assertEqual(binding.incident, incident)
        self.assertEqual(binding.current_state_raw, current_raw)
        self.assertEqual(binding.journal_evidence_raw, journal_raw)
        runtime_verify.assert_called_once()
        health.assert_called_once_with(None)

    def test_corrected_software_interruption_propagates_runtime_blockers(self):
        failure_raw, _ = self.write_corrected_software_interruption_records()
        incident = recovery.CorrectedSoftwareInterruption(
            failure_raw,
            recovery._incident_reference(failure_raw),
            hashlib.sha256(failure_raw).hexdigest(),
            recovery.CORRECTED_CHECKPOINT_REASON,
            1_792_864_340.6402085,
            recovery.CORRECTED_CHECKPOINT_SOURCE_REVISION,
            recovery.CORRECTED_CHECKPOINT_SOURCE_PATH,
            recovery.CORRECTED_CHECKPOINT_SOURCE_SHA256,
        )
        cases = (
            ("runtime", "a RAM Tetris writer owns its lock"),
            ("runtime", "lifecycle or SDK ownership is ambiguous"),
            ("health", "accepted controller inventory is incomplete"),
            ("health", "four SPD5118 endpoints were not verified"),
            ("journal", "kernel communication after authoritative readiness"),
        )
        for verifier, message in cases:
            with self.subTest(verifier=verifier):
                runtime_effect = (
                    recovery.RecoveryBlocked(message) if verifier == "runtime" else None
                )
                health_effect = (
                    recovery.RecoveryBlocked(message) if verifier == "health" else None
                )
                journal_effect = (
                    recovery.RecoveryBlocked(message) if verifier == "journal" else None
                )
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery,
                        "_corrected_software_interruption_authorization",
                        return_value=incident,
                    ),
                    mock.patch.object(
                        recovery,
                        "_verify_corrected_source_revision",
                        return_value=recovery.CORRECTED_CHECKPOINT_MINIMUM_REVISION,
                    ),
                    mock.patch.object(
                        recovery,
                        "_detector_policy_is_reviewed",
                        return_value=self.config_raw,
                    ),
                    mock.patch.object(
                        recovery,
                        "_verify_historical_running_environment",
                        side_effect=runtime_effect,
                    ),
                    mock.patch.object(
                        recovery,
                        "_verify_service_and_hardware",
                        side_effect=health_effect,
                    ),
                    mock.patch.object(
                        recovery,
                        "_software_interruption_journal_evidence",
                        side_effect=journal_effect,
                    ),
                    self.assertRaisesRegex(recovery.RecoveryBlocked, message),
                ):
                    recovery._corrected_software_interruption_preflight(
                        incident.incident_reference,
                        incident.latch_sha256,
                        "LGT-TET-001",
                        incident.original_reason,
                    )

    def test_corrected_software_interruption_clearance_preserves_evidence_only(self):
        failure_raw, current_raw = self.write_corrected_software_interruption_records()
        incident = recovery.CorrectedSoftwareInterruption(
            failure_raw,
            recovery._incident_reference(failure_raw),
            hashlib.sha256(failure_raw).hexdigest(),
            recovery.CORRECTED_CHECKPOINT_REASON,
            1_792_864_340.6402085,
            recovery.CORRECTED_CHECKPOINT_SOURCE_REVISION,
            recovery.CORRECTED_CHECKPOINT_SOURCE_PATH,
            recovery.CORRECTED_CHECKPOINT_SOURCE_SHA256,
        )
        journal_raw = b'{"category":"corrected-software-interruption"}\n'
        binding = recovery.SoftwareInterruptionClearanceBinding(
            incident,
            current_raw,
            self.config_raw,
            journal_raw,
            1_792_868_400.0,
            recovery.CORRECTED_CHECKPOINT_MINIMUM_REVISION,
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_corrected_software_interruption_preflight",
                return_value=binding,
            ) as preflight,
            mock.patch.object(
                recovery, "_verify_corrected_software_interruption_continuity"
            ) as continuity,
            mock.patch.object(
                recovery.subprocess,
                "run",
                side_effect=AssertionError("no service or RGB operation is permitted"),
            ),
        ):
            result = recovery.clear_reviewed_software_interruption(
                incident.incident_reference,
                incident.latch_sha256,
                "LGT-TET-001",
                incident.original_reason,
            )
        self.assertEqual(result["state"], "off")
        self.assertFalse(self.failure.exists())
        self.assertEqual(preflight.call_count, 2)
        continuity.assert_called_once_with(binding)
        evidence = self.failure.parent / "recovery-evidence"
        for kind, raw in (
            ("failure", failure_raw),
            ("lifecycle-state", current_raw),
            ("openrgb-config", self.config_raw),
            ("software-interruption-journal", journal_raw),
        ):
            path = evidence / f"{incident.incident_reference}.{kind}.json"
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_corrected_software_interruption_rejects_change_and_concurrency(self):
        failure_raw, current_raw = self.write_corrected_software_interruption_records()
        incident = recovery.CorrectedSoftwareInterruption(
            failure_raw,
            recovery._incident_reference(failure_raw),
            hashlib.sha256(failure_raw).hexdigest(),
            recovery.CORRECTED_CHECKPOINT_REASON,
            1_792_864_340.6402085,
            recovery.CORRECTED_CHECKPOINT_SOURCE_REVISION,
            recovery.CORRECTED_CHECKPOINT_SOURCE_PATH,
            recovery.CORRECTED_CHECKPOINT_SOURCE_SHA256,
        )
        binding = recovery.SoftwareInterruptionClearanceBinding(
            incident,
            current_raw,
            self.config_raw,
            b"{}\n",
            1_792_868_400.0,
            recovery.CORRECTED_CHECKPOINT_MINIMUM_REVISION,
        )
        calls = 0

        def changed_preflight(*_args):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.failure.write_bytes(failure_raw + b"changed")
            return binding

        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_corrected_software_interruption_preflight",
                side_effect=changed_preflight,
            ),
            self.assertRaisesRegex(
                recovery.RecoveryBlocked, "changed before clearance"
            ),
        ):
            recovery.clear_reviewed_software_interruption(
                incident.incident_reference,
                incident.latch_sha256,
                "LGT-TET-001",
                incident.original_reason,
            )

        self.failure.write_bytes(failure_raw)
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.runtime.chmod(0o700)
        descriptor = os.open(
            self.runtime / "lighting-recovery.lock", os.O_WRONLY | os.O_CREAT, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (
                self.patched_environment(),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "another recovery"),
            ):
                recovery.clear_reviewed_software_interruption(
                    incident.incident_reference,
                    incident.latch_sha256,
                    "LGT-TET-001",
                    incident.original_reason,
                )
        finally:
            os.close(descriptor)
        self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_reviewed_hardware_health_cli_requires_explicit_acknowledgement(self):
        reviewed = recovery.REVIEWED_HARDWARE_HEALTH_ALLOWLIST["LR-E8FE394802531DE7"]
        arguments = [
            "clear-reviewed-hardware-health",
            "--incident-reference",
            reviewed.incident_reference,
            "--latch-sha256",
            reviewed.latch_sha256,
            "--error-code",
            reviewed.code,
            "--original-reason",
            reviewed.original_reason,
            "--stability-manifest-sha256",
            reviewed.stability_manifest_sha256,
        ]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            recovery.build_parser().parse_args(arguments)
        parsed = recovery.build_parser().parse_args(
            arguments + ["--acknowledge-reviewed-hardware-health"]
        )
        self.assertEqual(parsed.action, "clear-reviewed-hardware-health")
        self.assertTrue(parsed.acknowledge_reviewed_hardware_health)

    def test_reviewed_hardware_health_accepts_only_exact_binding(self):
        reviewed = recovery.REVIEWED_HARDWARE_HEALTH_ALLOWLIST["LR-E8FE394802531DE7"]
        self.assertEqual(
            recovery._reviewed_hardware_health_authorization(
                reviewed.incident_reference,
                reviewed.latch_sha256,
                reviewed.code,
                reviewed.original_reason,
                reviewed.stability_manifest_sha256,
            ),
            reviewed,
        )
        values = [
            reviewed.incident_reference,
            reviewed.latch_sha256,
            reviewed.code,
            reviewed.original_reason,
            reviewed.stability_manifest_sha256,
        ]
        replacements = (
            "LR-WRONG",
            "0" * 64,
            "LGT-CTL-001",
            "different reason",
            "1" * 64,
        )
        for index, replacement in enumerate(replacements):
            changed = values.copy()
            changed[index] = replacement
            with (
                self.subTest(index=index),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "allowlisted"),
            ):
                recovery._reviewed_hardware_health_authorization(*changed)
        self.assertFalse(
            recovery.classify_reason(reviewed.original_reason).reviewed_recovery
        )

    def test_reviewed_hardware_health_verifies_complete_stability_evidence(self):
        reviewed, _, _, expected = self.write_reviewed_hardware_health_records()
        with (
            self.patched_environment(),
            mock.patch.dict(
                recovery.REVIEWED_HARDWARE_HEALTH_ALLOWLIST,
                {reviewed.incident_reference: reviewed},
            ),
            mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
        ):
            actual = recovery._verify_stability_evidence(reviewed)
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual.files), 7)

    def test_reviewed_hardware_health_rejects_changed_or_incomplete_evidence(self):
        for case in ("changed", "incomplete"):
            with self.subTest(case=case):
                reviewed, failure_raw, _, _ = (
                    self.write_reviewed_hardware_health_records()
                )
                evidence = (
                    self.failure.parent
                    / "recovery-evidence"
                    / reviewed.stability_directory
                )
                if case == "changed":
                    (evidence / "samples.tsv").write_bytes(b"changed\n")
                else:
                    (evidence / "summary.tsv").unlink()
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery, "_current_boot_id", return_value="a" * 32
                    ),
                    self.assertRaises(recovery.RecoveryBlocked),
                ):
                    recovery._verify_stability_evidence(reviewed)
                self.assertEqual(self.failure.read_bytes(), failure_raw)
                self.tearDown()
                self.setUp()

    def test_reviewed_hardware_health_rejects_boot_or_post_observation_event(self):
        reviewed, _, _, _ = self.write_reviewed_hardware_health_records()
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value="b" * 32),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "another boot"),
        ):
            recovery._verify_stability_evidence(reviewed)

        events = (
            "kernel: spd5118 10-0053: failed to read: error -6",
            "kernel: PM: suspend entry (deep)",
        )
        for event in events:
            result = subprocess.CompletedProcess(
                [], 0, f"{event}\n-- cursor: current\n", ""
            )
            with (
                self.subTest(event=event),
                mock.patch.object(recovery.subprocess, "run", return_value=result),
                self.assertRaises(recovery.RecoveryBlocked),
            ):
                recovery._kernel_history_after_observation("test-cursor")

    def test_reviewed_hardware_health_preflight_binds_all_evidence(self):
        reviewed, failure_raw, current_raw, stability = (
            self.write_reviewed_hardware_health_records()
        )
        historical = b'{"retained_lines":["spd5118 error -6"]}\n'
        with (
            self.patched_environment(),
            mock.patch.dict(
                recovery.REVIEWED_HARDWARE_HEALTH_ALLOWLIST,
                {reviewed.incident_reference: reviewed},
            ),
            mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
            mock.patch.object(
                recovery, "_verify_corrected_source_revision", return_value="c" * 40
            ),
            mock.patch.object(
                recovery, "_detector_policy_is_reviewed", return_value=self.config_raw
            ),
            mock.patch.object(
                recovery, "_verify_historical_running_environment"
            ) as runtime_verify,
            mock.patch.object(
                recovery, "_verify_service_and_hardware", return_value={}
            ) as health,
            mock.patch.object(recovery, "_kernel_history_after_observation") as kernel,
            mock.patch.object(
                recovery, "_historical_kernel_evidence", return_value=historical
            ),
        ):
            binding = recovery._hardware_health_clearance_preflight(
                reviewed.incident_reference,
                reviewed.latch_sha256,
                reviewed.code,
                reviewed.original_reason,
                reviewed.stability_manifest_sha256,
            )
        self.assertEqual(binding.failure_raw, failure_raw)
        self.assertEqual(binding.current_state_raw, current_raw)
        self.assertEqual(binding.config_raw, self.config_raw)
        self.assertEqual(binding.stability, stability)
        self.assertEqual(binding.historical_kernel_raw, historical)
        runtime_verify.assert_called_once()
        health.assert_called_once_with(None)
        kernel.assert_called_once_with(stability.journal_cursor)

    def test_reviewed_hardware_health_propagates_runtime_and_hardware_failures(self):
        reviewed, failure_raw, _, _ = self.write_reviewed_hardware_health_records()
        cases = (
            ("runtime", "RAM Tetris preference is not OFF"),
            ("runtime", "SDK identity is not healthy"),
            ("health", "accepted controller inventory is incomplete"),
            ("health", "10-0053 temperature is unreadable"),
        )
        for verifier, message in cases:
            runtime_effect = (
                recovery.RecoveryBlocked(message) if verifier == "runtime" else None
            )
            health_effect = (
                recovery.RecoveryBlocked(message) if verifier == "health" else None
            )
            with (
                self.subTest(verifier=verifier, message=message),
                self.patched_environment(),
                mock.patch.dict(
                    recovery.REVIEWED_HARDWARE_HEALTH_ALLOWLIST,
                    {reviewed.incident_reference: reviewed},
                ),
                mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
                mock.patch.object(
                    recovery,
                    "_verify_corrected_source_revision",
                    return_value="c" * 40,
                ),
                mock.patch.object(
                    recovery,
                    "_detector_policy_is_reviewed",
                    return_value=self.config_raw,
                ),
                mock.patch.object(
                    recovery,
                    "_verify_historical_running_environment",
                    side_effect=runtime_effect,
                ),
                mock.patch.object(
                    recovery,
                    "_verify_service_and_hardware",
                    side_effect=health_effect,
                ),
                mock.patch.object(recovery, "_kernel_history_after_observation"),
                mock.patch.object(
                    recovery, "_historical_kernel_evidence", return_value=b"{}\n"
                ),
                self.assertRaisesRegex(recovery.RecoveryBlocked, message),
            ):
                recovery._hardware_health_clearance_preflight(
                    reviewed.incident_reference,
                    reviewed.latch_sha256,
                    reviewed.code,
                    reviewed.original_reason,
                    reviewed.stability_manifest_sha256,
                )
        self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_reviewed_hardware_health_clearance_preserves_evidence_without_operations(
        self,
    ):
        reviewed, failure_raw, current_raw, stability = (
            self.write_reviewed_hardware_health_records()
        )
        historical = b'{"retained_lines":["spd5118 error -6"]}\n'
        binding = recovery.HardwareHealthClearanceBinding(
            failure_raw,
            current_raw,
            self.config_raw,
            stability,
            historical,
            1_792_651_066.1584392,
            "c" * 40,
        )
        with (
            self.patched_environment(),
            mock.patch.dict(
                recovery.REVIEWED_HARDWARE_HEALTH_ALLOWLIST,
                {reviewed.incident_reference: reviewed},
            ),
            mock.patch.object(
                recovery,
                "_hardware_health_clearance_preflight",
                return_value=binding,
            ) as preflight,
            mock.patch.object(
                recovery, "_verify_hardware_health_continuity"
            ) as continuity,
            mock.patch.object(
                recovery.subprocess,
                "run",
                side_effect=AssertionError("no service or RGB operation is permitted"),
            ),
        ):
            result = recovery.clear_reviewed_hardware_health(
                reviewed.incident_reference,
                reviewed.latch_sha256,
                reviewed.code,
                reviewed.original_reason,
                reviewed.stability_manifest_sha256,
            )
        self.assertFalse(result["failure"])
        self.assertEqual(result["state"], "off")
        self.assertEqual(preflight.call_count, 2)
        continuity.assert_called_once_with(reviewed, binding)
        self.assertFalse(self.failure.exists())
        self.assertEqual(
            (self.failure.parent / "ram-tetris-enabled").read_bytes(), b"off\n"
        )
        evidence = self.failure.parent / "recovery-evidence"
        for kind, raw in (
            ("failure", failure_raw),
            ("lifecycle-state", current_raw),
            ("openrgb-config", self.config_raw),
            ("hardware-kernel-history", historical),
        ):
            self.assertEqual(
                (evidence / f"{reviewed.incident_reference}.{kind}.json").read_bytes(),
                raw,
            )
        retained = evidence / (
            f"{reviewed.incident_reference}.hardware-health-observation"
        )
        self.assertEqual(
            {path.name for path in retained.iterdir()},
            {name for name, _raw in stability.files},
        )

    def test_reviewed_hardware_health_rejects_preservation_or_latch_change(self):
        for case in ("preservation", "latch-change"):
            with self.subTest(case=case):
                reviewed, failure_raw, current_raw, stability = (
                    self.write_reviewed_hardware_health_records()
                )
                binding = recovery.HardwareHealthClearanceBinding(
                    failure_raw,
                    current_raw,
                    self.config_raw,
                    stability,
                    b"{}\n",
                    1_792_651_066.1584392,
                    "c" * 40,
                )
                calls = 0

                def preflight(
                    *_args,
                    case=case,
                    failure_raw=failure_raw,
                    binding=binding,
                ):
                    nonlocal calls
                    calls += 1
                    if case == "latch-change" and calls == 2:
                        self.failure.write_bytes(failure_raw + b"changed")
                    return binding

                preservation = (
                    mock.patch.object(
                        recovery,
                        "_preserve_evidence",
                        side_effect=OSError("evidence write failed"),
                    )
                    if case == "preservation"
                    else mock.patch.object(
                        recovery,
                        "_preserve_evidence",
                        wraps=recovery._preserve_evidence,
                    )
                )
                with (
                    self.patched_environment(),
                    mock.patch.dict(
                        recovery.REVIEWED_HARDWARE_HEALTH_ALLOWLIST,
                        {reviewed.incident_reference: reviewed},
                    ),
                    mock.patch.object(
                        recovery,
                        "_hardware_health_clearance_preflight",
                        side_effect=preflight,
                    ),
                    preservation,
                    self.assertRaises((recovery.RecoveryBlocked, OSError)),
                ):
                    recovery.clear_reviewed_hardware_health(
                        reviewed.incident_reference,
                        reviewed.latch_sha256,
                        reviewed.code,
                        reviewed.original_reason,
                        reviewed.stability_manifest_sha256,
                    )
                self.assertTrue(self.failure.exists())
                self.tearDown()
                self.setUp()

    def test_concurrent_reviewed_hardware_health_clearance_is_blocked(self):
        reviewed, failure_raw, _, _ = self.write_reviewed_hardware_health_records()
        self.runtime.mkdir(parents=True)
        self.runtime.chmod(0o700)
        descriptor = os.open(
            self.runtime / "lighting-recovery.lock", os.O_WRONLY | os.O_CREAT, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (
                self.patched_environment(),
                mock.patch.dict(
                    recovery.REVIEWED_HARDWARE_HEALTH_ALLOWLIST,
                    {reviewed.incident_reference: reviewed},
                ),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "another recovery"),
            ):
                recovery.clear_reviewed_hardware_health(
                    reviewed.incident_reference,
                    reviewed.latch_sha256,
                    reviewed.code,
                    reviewed.original_reason,
                    reviewed.stability_manifest_sha256,
                )
        finally:
            os.close(descriptor)
        self.assertEqual(self.failure.read_bytes(), failure_raw)

    def test_transient_spd_classifies_legacy_and_structured_evidence(self):
        incident, _, _ = self.write_transient_spd_records()
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_verify_corrected_source_revision",
                return_value="f" * 40,
            ),
            mock.patch.object(
                recovery,
                "_source_blob_sha256",
                return_value=recovery.LEGACY_TRANSIENT_SPD_SOURCE_SHA256,
            ),
        ):
            actual = recovery._classify_transient_spd_incident()
        self.assertEqual(actual, incident)
        self.assertEqual(actual.classification, "legacy-read-or-parse-error")

        structured = json.loads(incident.failure_raw)
        structured["evidence_version"] = 1
        structured["details"] = {
            "failure_kind": "spd5118-temperature",
            "endpoint": "10-0053",
            "sensor": "10-0053/hwmon/temp1_input",
            "read_state": "kernel-read-error",
            "exception_type": "OSError",
            "errno": 5,
        }
        structured["source"] = {
            "component": "ram-tetris",
            "version": "0.4.30",
            "revision": "a" * 40,
            "path": "ram-tetris",
            "sha256": "b" * 64,
        }
        self.failure.write_bytes(
            (json.dumps(structured, sort_keys=True) + "\n").encode()
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_verify_corrected_source_revision",
                return_value="a" * 40,
            ),
            mock.patch.object(recovery, "_source_blob_sha256", return_value="b" * 64),
        ):
            actual = recovery._classify_transient_spd_incident()
        self.assertEqual(actual.classification, "structured-kernel-read-error")
        self.assertEqual(actual.endpoint, "10-0053")

    def test_all_four_structured_transient_spd_endpoints_are_eligible(self):
        for endpoint in recovery.TRANSIENT_SPD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                value = {
                    "details": {
                        "endpoint": endpoint,
                        "exception_type": "OSError",
                        "failure_kind": "spd5118-temperature",
                        "read_state": "kernel-read-error",
                        "sensor": f"{endpoint}/hwmon/temp1_input",
                    },
                    "evidence_version": 1,
                    "message": f"{endpoint} temperature is unreadable",
                    "pid": 77,
                    "source": {
                        "component": "ram-tetris",
                        "path": "ram-tetris",
                        "revision": "a" * 40,
                        "sha256": "b" * 64,
                        "version": "0.4.31",
                    },
                    "state": "failed",
                    "time": time.time() - 120,
                }
                self.failure.parent.mkdir(parents=True, exist_ok=True)
                self.failure.parent.chmod(0o700)
                self.failure.write_text(
                    json.dumps(value, sort_keys=True) + "\n", encoding="utf-8"
                )
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery,
                        "_verify_corrected_source_revision",
                        return_value="a" * 40,
                    ),
                    mock.patch.object(
                        recovery, "_source_blob_sha256", return_value="b" * 64
                    ),
                ):
                    incident = recovery._classify_transient_spd_incident()
                self.assertEqual(incident.endpoint, endpoint)
                self.assertEqual(
                    incident.classification, "structured-kernel-read-error"
                )

    def test_transient_spd_status_prepare_and_recover_use_reviewed_path(self):
        incident, current_raw, _ = self.write_transient_spd_records()
        self.failure.parent.joinpath("ram-tetris-enabled").write_bytes(b"on\n")
        token = recovery._transient_spd_confirmation_token(incident.failure_raw)
        observed = {
            "observation_directory": "LR-0123456789ABCDEF-transient-spd-20261024T100000+0200",
            "stability_manifest_sha256": "a" * 64,
        }
        cleared = {
            "failure": False,
            "incident_reference": incident.incident_reference,
            "preference": False,
            "state": "off",
        }
        qualification = b'{"category":"transient-spd-post-incident"}\n'
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery, "_classify_transient_spd_incident", return_value=incident
            ),
            mock.patch.object(
                recovery,
                "_transient_spd_environment_preflight",
                return_value=(current_raw, self.config_raw, {}, qualification),
            ) as preflight,
            mock.patch.object(
                recovery,
                "_run_ram_tetris_status",
                return_value={"preference": True, "state": "failed"},
            ),
            mock.patch.object(recovery, "_service_quick_health", return_value=True),
            mock.patch.object(recovery, "observe_transient_spd", return_value=observed),
            mock.patch.object(
                recovery, "clear_reviewed_transient_spd", return_value=cleared
            ) as clear,
            mock.patch.object(
                recovery.subprocess,
                "run",
                side_effect=AssertionError("no service, preset, or RGB command"),
            ),
        ):
            status = recovery.status_document()
            prepared = recovery.prepare_document()
            result = recovery.recover(token)
        self.assertTrue(status["recovery_available"])
        self.assertEqual(prepared["recovery_kind"], "transient-spd")
        self.assertEqual(prepared["confirmation_token"], token)
        self.assertEqual(result["state"], "off")
        self.assertIn("Transient SPD recovery complete", result["message"])
        self.assertEqual(
            self.failure.parent.joinpath("ram-tetris-enabled").read_bytes(), b"off\n"
        )
        self.assertEqual(preflight.call_count, 2)
        self.assertFalse(preflight.call_args_list[0].kwargs["require_preference_off"])
        self.assertFalse(preflight.call_args_list[1].kwargs["require_preference_off"])
        clear.assert_called_once_with(
            observed["observation_directory"],
            observed["stability_manifest_sha256"],
        )

    def test_transient_spd_recover_refuses_concurrent_attempt(self):
        incident, _, _ = self.write_transient_spd_records()
        token = recovery._transient_spd_confirmation_token(incident.failure_raw)
        self.runtime.mkdir(parents=True)
        self.runtime.chmod(0o700)
        descriptor = os.open(
            self.runtime / "lighting-recovery.lock", os.O_WRONLY | os.O_CREAT, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (
                self.patched_environment(),
                mock.patch.object(
                    recovery,
                    "_classify_transient_spd_incident",
                    return_value=incident,
                ),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "another recovery"),
            ):
                recovery.recover(token)
        finally:
            os.close(descriptor)
        self.assertEqual(self.failure.read_bytes(), incident.failure_raw)

    def test_transient_spd_rejects_wrong_classification_and_provenance(self):
        incident, _, _ = self.write_transient_spd_records()
        wrong_endpoint = json.loads(incident.failure_raw)
        wrong_endpoint["message"] = "10-0054 temperature is unreadable"
        self.failure.write_bytes(
            (json.dumps(wrong_endpoint, sort_keys=True) + "\n").encode()
        )
        with (
            self.patched_environment(),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "not an eligible"),
        ):
            recovery._classify_transient_spd_incident()

        value = json.loads(incident.failure_raw)
        value["evidence_version"] = 1
        value["details"] = {
            "failure_kind": "spd5118-temperature",
            "endpoint": "10-0053",
            "sensor": "10-0053/hwmon/temp1_input",
            "read_state": "malformed",
            "exception_type": "ValueError",
        }
        value["source"] = {
            "component": "ram-tetris",
            "version": "0.4.30",
            "revision": "a" * 40,
            "path": "ram-tetris",
            "sha256": "b" * 64,
        }
        self.failure.write_bytes((json.dumps(value, sort_keys=True) + "\n").encode())
        with (
            self.patched_environment(),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "not an approved"),
        ):
            recovery._classify_transient_spd_incident()

        self.failure.write_bytes(incident.failure_raw)
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_verify_corrected_source_revision"),
            mock.patch.object(recovery, "_source_blob_sha256", return_value="0" * 64),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "provenance changed"),
        ):
            recovery._classify_transient_spd_incident()

    def test_transient_spd_preflight_rejects_writer_and_incomplete_inventory(self):
        incident, current_raw, _ = self.write_transient_spd_records()
        cases = (
            ("runtime", "a RAM Tetris writer owns its lock"),
            ("runtime", "RAM Tetris preference is not OFF"),
            ("health", "accepted controller inventory is incomplete"),
            ("health", "DIMM state changed outside the Tetris writer"),
        )
        for boundary, message in cases:
            with (
                self.subTest(boundary=boundary),
                self.patched_environment(),
                mock.patch.object(
                    recovery, "_read_protected_bytes", return_value=current_raw
                ),
                mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
                mock.patch.object(
                    recovery,
                    "_detector_policy_is_reviewed",
                    return_value=self.config_raw,
                ),
                mock.patch.object(
                    recovery,
                    "_verify_historical_running_environment",
                    side_effect=(
                        recovery.RecoveryBlocked(message)
                        if boundary == "runtime"
                        else None
                    ),
                ),
                mock.patch.object(
                    recovery,
                    "_verify_service_and_hardware",
                    side_effect=(
                        recovery.RecoveryBlocked(message)
                        if boundary == "health"
                        else None
                    ),
                ),
                self.assertRaisesRegex(recovery.RecoveryBlocked, message),
            ):
                recovery._transient_spd_environment_preflight(incident)

    def test_transient_spd_qualifies_unchanged_ready_lifecycle_before_incident(self):
        incident, _, _ = self.write_transient_spd_records()
        current = json.loads(self.lifecycle_state.read_text(encoding="utf-8"))
        current["time"] = incident.failure_time - 30
        current_raw = (json.dumps(current, sort_keys=True) + "\n").encode()
        self.lifecycle_state.write_bytes(current_raw)
        qualification = b'{"category":"transient-spd-post-incident"}\n'
        health = {"controller_count": 7, "dimm_count": 4}
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery, "_current_boot_id", return_value=current["boot_id"]
            ),
            mock.patch.object(
                recovery,
                "_detector_policy_is_reviewed",
                return_value=self.config_raw,
            ),
            mock.patch.object(
                recovery, "_verify_historical_running_environment"
            ) as runtime,
            mock.patch.object(
                recovery,
                "_verify_service_and_hardware",
                return_value=health,
            ),
            mock.patch.object(
                recovery,
                "_transient_spd_post_incident_evidence",
                return_value=qualification,
            ) as journal,
        ):
            actual = recovery._transient_spd_environment_preflight(incident)
        self.assertEqual(actual, (current_raw, self.config_raw, health, qualification))
        runtime.assert_called_once_with(
            current, self.config_raw, require_preference_off=True
        )
        journal.assert_called_once_with(incident, incident.failure_time - 30)

    def test_transient_spd_post_incident_history_rejects_new_unsafe_events(self):
        incident, _, _ = self.write_transient_spd_records()
        cases = (
            ("kernel", "kernel: i801 SMBus timeout\n", "", "kernel communication"),
            ("suspend", "kernel: PM: suspend exit\n", "", "suspend event"),
            (
                "service",
                "",
                "Main process exited, status=1/FAILURE\n",
                "service failure",
            ),
        )
        for label, kernel, service, message in cases:
            with (
                self.subTest(label=label),
                mock.patch.object(
                    recovery,
                    "_software_interruption_journal_slice",
                    side_effect=[kernel, service],
                ),
                self.assertRaisesRegex(recovery.RecoveryBlocked, message),
            ):
                recovery._transient_spd_post_incident_evidence(
                    incident, incident.failure_time - 30
                )

    def test_transient_spd_clearance_rejects_changed_lifecycle_identity(self):
        incident, current_raw, observation = self.write_transient_spd_records()
        changed = recovery.TransientSpdObservation(
            directory_name=observation.directory_name,
            manifest_sha256=observation.manifest_sha256,
            files=observation.files,
            metadata_raw=observation.metadata_raw,
            journal_cursor=observation.journal_cursor,
            observation_start=observation.observation_start,
            observation_end=observation.observation_end,
            boot_id=observation.boot_id,
            suspend_count=observation.suspend_count,
            lifecycle_pid=999,
            lifecycle_start=observation.lifecycle_start,
            server_pid=observation.server_pid,
            server_start=observation.server_start,
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery, "_classify_transient_spd_incident", return_value=incident
            ),
            mock.patch.object(
                recovery, "_verify_transient_spd_observation", return_value=changed
            ),
            mock.patch.object(
                recovery,
                "_transient_spd_environment_preflight",
                return_value=(current_raw, self.config_raw, {}, b"{}\n"),
            ),
            mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
            mock.patch.object(recovery, "_current_suspend_count", return_value=11),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "identity changed"),
        ):
            recovery._transient_spd_clearance_preflight(
                observation.directory_name, observation.manifest_sha256
            )

    def test_transient_spd_observation_must_follow_incident(self):
        incident, _, observation = self.write_transient_spd_records()
        stale = recovery.TransientSpdObservation(
            directory_name=observation.directory_name,
            manifest_sha256=observation.manifest_sha256,
            files=observation.files,
            metadata_raw=observation.metadata_raw,
            journal_cursor=observation.journal_cursor,
            observation_start=incident.failure_time - 1,
            observation_end=incident.failure_time + 58,
            boot_id=observation.boot_id,
            suspend_count=observation.suspend_count,
            lifecycle_pid=observation.lifecycle_pid,
            lifecycle_start=observation.lifecycle_start,
            server_pid=observation.server_pid,
            server_start=observation.server_start,
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery, "_classify_transient_spd_incident", return_value=incident
            ),
            mock.patch.object(
                recovery, "_verify_transient_spd_observation", return_value=stale
            ),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "predates the incident"),
        ):
            recovery._transient_spd_clearance_preflight(
                observation.directory_name, observation.manifest_sha256
            )

    def test_transient_spd_observation_verifies_integrity_boot_and_suspend(self):
        incident, _, observation = self.write_transient_spd_records()
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
            mock.patch.object(recovery, "_current_suspend_count", return_value=11),
        ):
            actual = recovery._verify_transient_spd_observation(
                incident,
                observation.directory_name,
                observation.manifest_sha256,
            )
        self.assertEqual(actual, observation)

        for name, patcher, message in (
            (
                "boot",
                mock.patch.object(recovery, "_current_boot_id", return_value="b" * 32),
                "environment no longer matches",
            ),
            (
                "suspend",
                mock.patch.object(recovery, "_current_suspend_count", return_value=12),
                "environment no longer matches",
            ),
        ):
            with (
                self.subTest(name=name),
                self.patched_environment(),
                patcher,
                mock.patch.object(
                    recovery,
                    "_current_boot_id",
                    return_value="b" * 32 if name == "boot" else "a" * 32,
                )
                if name == "suspend"
                else mock.patch.object(
                    recovery, "_current_suspend_count", return_value=11
                ),
                self.assertRaisesRegex(recovery.RecoveryBlocked, message),
            ):
                recovery._verify_transient_spd_observation(
                    incident,
                    observation.directory_name,
                    observation.manifest_sha256,
                )

    def test_transient_spd_observation_preserves_post_incident_qualification(self):
        incident, _, observation = self.write_transient_spd_records()
        evidence = (
            self.failure.parent / "recovery-evidence" / observation.directory_name
        )
        metadata_path = evidence / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        started = recovery._parse_observation_time(
            metadata["observation"]["started"], "start time"
        )
        metadata["plugin_version"] = "0.4.33"
        metadata["qualification"] = {
            "schema_version": 1,
            "category": "transient-spd-post-incident",
            "failure_time": incident.failure_time,
            "lifecycle_ready_time": incident.failure_time - 30,
            "qualified_at": started - 1,
            "kernel": "historical kernel evidence\n",
            "service": "historical service evidence\n",
        }
        metadata_path.write_text(
            json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8"
        )

        def refresh_manifest() -> str:
            payloads = {
                name: (evidence / name).read_bytes()
                for name in recovery.TRANSIENT_SPD_EVIDENCE_FILES
            }
            manifest = b"".join(
                f"{hashlib.sha256(payloads[name]).hexdigest()}  {name}\n".encode()
                for name in sorted(payloads)
            )
            evidence.joinpath("manifest.sha256").write_bytes(manifest)
            return hashlib.sha256(manifest).hexdigest()

        manifest_sha256 = refresh_manifest()
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
            mock.patch.object(recovery, "_current_suspend_count", return_value=11),
        ):
            verified = recovery._verify_transient_spd_observation(
                incident, observation.directory_name, manifest_sha256
            )
        self.assertEqual(
            json.loads(verified.metadata_raw)["qualification"],
            metadata["qualification"],
        )

        metadata["qualification"]["kernel"] = "kernel: spd5118 read failed\n"
        metadata_path.write_text(
            json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8"
        )
        manifest_sha256 = refresh_manifest()
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
            mock.patch.object(recovery, "_current_suspend_count", return_value=11),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "qualification evidence"),
        ):
            recovery._verify_transient_spd_observation(
                incident, observation.directory_name, manifest_sha256
            )

    def test_transient_spd_rejects_changed_evidence_or_kernel_event(self):
        incident, _, observation = self.write_transient_spd_records()
        evidence = (
            self.failure.parent / "recovery-evidence" / observation.directory_name
        )
        (evidence / "samples.tsv").write_bytes(b"changed\n")
        with (
            self.patched_environment(),
            mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
            mock.patch.object(recovery, "_current_suspend_count", return_value=11),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "checksum failed"),
        ):
            recovery._verify_transient_spd_observation(
                incident,
                observation.directory_name,
                observation.manifest_sha256,
            )

        event = subprocess.CompletedProcess(
            [], 0, "kernel: i801 SMBus timeout\n-- cursor: current\n", ""
        )
        with (
            mock.patch.object(recovery.subprocess, "run", return_value=event),
            self.assertRaisesRegex(recovery.RecoveryBlocked, "communication error"),
        ):
            recovery._kernel_history_after_observation("cursor")

    def test_transient_spd_rejects_mismatched_incomplete_or_unprotected_evidence(self):
        for case in ("mismatched-latch", "incomplete", "unprotected"):
            with self.subTest(case=case):
                incident, _, observation = self.write_transient_spd_records()
                evidence = (
                    self.failure.parent
                    / "recovery-evidence"
                    / observation.directory_name
                )
                manifest_sha256 = observation.manifest_sha256
                if case == "mismatched-latch":
                    (evidence / "failure-latch.json").write_bytes(b"{}\n")
                    payloads = {
                        name: (evidence / name).read_bytes()
                        for name in recovery.TRANSIENT_SPD_EVIDENCE_FILES
                    }
                    manifest = b"".join(
                        f"{hashlib.sha256(payloads[name]).hexdigest()}  {name}\n".encode()
                        for name in sorted(payloads)
                    )
                    (evidence / "manifest.sha256").write_bytes(manifest)
                    manifest_sha256 = hashlib.sha256(manifest).hexdigest()
                elif case == "incomplete":
                    (evidence / "kernel-relevant.log").unlink()
                else:
                    (evidence / "samples.tsv").chmod(0o644)
                with (
                    self.patched_environment(),
                    mock.patch.object(
                        recovery, "_current_boot_id", return_value="a" * 32
                    ),
                    mock.patch.object(
                        recovery, "_current_suspend_count", return_value=11
                    ),
                    self.assertRaises(recovery.RecoveryBlocked),
                ):
                    recovery._verify_transient_spd_observation(
                        incident,
                        observation.directory_name,
                        manifest_sha256,
                    )
                self.tearDown()
                self.setUp()

    def test_transient_spd_rejects_wrong_sensor_driver_or_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / "10-0053"
            wrong_driver = root / "other-driver"
            wrong_driver.mkdir()
            device.mkdir()
            device.joinpath("driver").symlink_to(wrong_driver, target_is_directory=True)
            with (
                mock.patch.object(recovery, "SPD_SYSFS_ROOT", root),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "not bound"),
            ):
                recovery._spd_temperature_path("10-0053")

            device.joinpath("driver").unlink()
            spd_driver = root / "spd5118"
            spd_driver.mkdir()
            device.joinpath("driver").symlink_to(spd_driver, target_is_directory=True)
            with (
                mock.patch.object(recovery, "SPD_SYSFS_ROOT", root),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "invalid temperature"),
            ):
                recovery._spd_temperature_path("10-0053")

    def test_transient_spd_incomplete_observation_never_publishes_evidence(self):
        incident, current_raw, _ = self.write_transient_spd_records()
        evidence_root = self.failure.parent / "recovery-evidence"
        before = {path.name for path in evidence_root.iterdir()}
        cursor = f"s=start;i=1;b={'a' * 32};m=1;t=1;x=1"
        for interruption in (
            recovery.RecoveryBlocked("10-0053 read failed"),
            KeyboardInterrupt(),
        ):
            with (
                self.subTest(interruption=type(interruption).__name__),
                self.patched_environment(),
                mock.patch.object(
                    recovery, "_classify_transient_spd_incident", return_value=incident
                ),
                mock.patch.object(
                    recovery,
                    "_transient_spd_environment_preflight",
                    return_value=(current_raw, self.config_raw, {}, b"{}\n"),
                ),
                mock.patch.object(recovery, "_current_boot_id", return_value="a" * 32),
                mock.patch.object(recovery, "_current_suspend_count", return_value=11),
                mock.patch.object(
                    recovery, "_spd_temperature_path", return_value=self.root
                ),
                mock.patch.object(
                    recovery, "_capture_kernel_cursor", return_value=cursor
                ),
                mock.patch.object(
                    recovery,
                    "_process_start",
                    side_effect=lambda pid: "5100" if pid == 51 else "5200",
                ),
                mock.patch.object(
                    recovery, "_read_spd_temperature", side_effect=interruption
                ),
                self.assertRaises(type(interruption)),
            ):
                recovery.observe_transient_spd()
        self.assertEqual({path.name for path in evidence_root.iterdir()}, before)

    def test_transient_spd_clearance_preserves_evidence_without_operations(self):
        incident, current_raw, observation = self.write_transient_spd_records()
        binding = recovery.TransientSpdClearanceBinding(
            incident,
            current_raw,
            self.config_raw,
            observation,
            "c" * 40,
        )
        with (
            self.patched_environment(),
            mock.patch.object(
                recovery,
                "_transient_spd_clearance_preflight",
                return_value=binding,
            ) as preflight,
            mock.patch.object(
                recovery, "_verify_transient_spd_continuity"
            ) as continuity,
            mock.patch.object(
                recovery.subprocess,
                "run",
                side_effect=AssertionError("no service or RGB operation is permitted"),
            ),
        ):
            result = recovery.clear_reviewed_transient_spd(
                observation.directory_name, observation.manifest_sha256
            )
        self.assertEqual(preflight.call_count, 2)
        continuity.assert_called_once_with(binding)
        self.assertEqual(result["state"], "off")
        self.assertFalse(self.failure.exists())
        retained = (
            self.failure.parent
            / "recovery-evidence"
            / f"{incident.incident_reference}.transient-spd-observation"
        )
        self.assertEqual(
            {path.name for path in retained.iterdir()},
            {name for name, _ in observation.files},
        )
        self.assertEqual(
            {path.name: path.read_bytes() for path in retained.iterdir()},
            dict(observation.files),
        )

    def test_concurrent_transient_spd_clearance_is_blocked(self):
        incident, _, observation = self.write_transient_spd_records()
        self.runtime.mkdir(parents=True)
        self.runtime.chmod(0o700)
        descriptor = os.open(
            self.runtime / "lighting-recovery.lock", os.O_WRONLY | os.O_CREAT, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (
                self.patched_environment(),
                self.assertRaisesRegex(recovery.RecoveryBlocked, "another recovery"),
            ):
                recovery.clear_reviewed_transient_spd(
                    observation.directory_name, observation.manifest_sha256
                )
        finally:
            os.close(descriptor)
        self.assertEqual(self.failure.read_bytes(), incident.failure_raw)

    def test_transient_spd_cli_requires_explicit_acknowledgements(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            recovery.build_parser().parse_args(["observe-transient-spd"])
        observed = recovery.build_parser().parse_args(
            ["observe-transient-spd", "--acknowledge-read-only-observation"]
        )
        self.assertEqual(observed.action, "observe-transient-spd")
        arguments = [
            "clear-reviewed-transient-spd",
            "--observation-directory",
            "LR-0123456789ABCDEF-transient-spd-20261024T100000+0200",
            "--stability-manifest-sha256",
            "a" * 64,
        ]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            recovery.build_parser().parse_args(arguments)
        cleared = recovery.build_parser().parse_args(
            arguments + ["--acknowledge-reviewed-transient-spd"]
        )
        self.assertEqual(cleared.action, "clear-reviewed-transient-spd")

    def test_copy_diagnostics_is_sanitized_and_truncates_long_reason(self):
        long_reason = "/home/private/secret/config token=actual-secret " + "x" * 700
        value = {
            "failure": True,
            "code": "LGT-UNK-000",
            "incident_reference": "LR-ABC",
            "first_detected": "2026-10-18T07:23:46Z",
            "subsystem": "unknown",
            "recovery_status": "manual-review",
            "description": "Manual review required.",
            "message": long_reason,
        }
        with mock.patch.object(recovery, "status_document", return_value=value):
            text = recovery.diagnostics_text()
        reason = text.split("Backend reason: ", 1)[1].splitlines()[0]
        self.assertLessEqual(len(reason), recovery.MAX_COPY_REASON)
        self.assertTrue(reason.endswith("…"))
        self.assertIn("[private-path]", reason)
        self.assertIn("token=[redacted]", reason)
        self.assertNotIn("/home/private", text)
        self.assertNotIn("actual-secret", text)
        self.assertNotIn("pid", text.lower())
        self.assertNotIn("temperature", text.lower())

    def test_copy_diagnostics_sends_exact_sanitized_output(self):
        expected = "OpenRGB Lighting Recovery\nStatus: test\n"
        completed = subprocess.CompletedProcess([], 0)
        output = io.StringIO()
        with (
            mock.patch.object(recovery, "diagnostics_text", return_value=expected),
            mock.patch.object(
                recovery.subprocess, "run", return_value=completed
            ) as run,
            redirect_stdout(output),
        ):
            self.assertEqual(recovery.copy_diagnostics(False), 0)
        self.assertEqual(run.call_args.kwargs["input"], expected)
        self.assertIn('"state": "copied"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
