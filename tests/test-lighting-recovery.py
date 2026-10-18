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
from contextlib import redirect_stdout
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
            "lifecycle stop request identity does not match writer": (
                "LGT-LIF-003",
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
