#!/usr/bin/env python3
"""Offline validation for the v0.4.19 systemd service-state guard."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "openrgb-service-guard"


class ServiceGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.state_home = root / "state"
        self.runtime = root / "runtime"
        self.proc = root / "proc"
        self.proc.mkdir()
        self.boot_id = root / "boot-id"
        self.boot_id.write_text("boot-a\n", encoding="utf-8")
        self.environment = os.environ | {
            "XDG_STATE_HOME": str(self.state_home),
            "OPENRGB_RUNTIME_DIR": str(self.runtime),
            "PROC_ROOT": str(self.proc),
            "BOOT_ID_PATH": str(self.boot_id),
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @property
    def service_state(self) -> Path:
        return (
            self.state_home
            / "omarchy-plus/openrgb-presets/lifecycle-service-state.json"
        )

    @property
    def failure(self) -> Path:
        return self.state_home / "omarchy-plus/openrgb-presets/ram-tetris-failure.json"

    def run_guard(self, *arguments: str, check: bool = True):
        return subprocess.run(
            [GUARD, *arguments],
            check=check,
            capture_output=True,
            env=self.environment,
            text=True,
        )

    def mark(self, state: str, pid: int = 41, start: str = "9001") -> None:
        self.run_guard(
            "mark",
            state,
            "--lifecycle-pid",
            str(pid),
            "--lifecycle-start",
            start,
        )

    def write_process(self, pid: int, start: str) -> None:
        process = self.proc / str(pid)
        process.mkdir()
        fields = [str(pid), "(lifecycle)", "S", "1", *("0" for _ in range(17)), start]
        process.joinpath("stat").write_text(" ".join(fields) + "\n")

    def test_clean_stop_allows_next_start_without_latch(self):
        self.mark("clean-stopped")
        self.run_guard("prepare-start")
        self.run_guard("finalize-stop")
        self.assertFalse(self.failure.exists())

    def test_stale_ready_state_latches_before_next_start(self):
        self.mark("ready")
        result = self.run_guard("prepare-start", check=False)
        self.assertEqual(result.returncode, 1)
        failure = json.loads(self.failure.read_text())
        self.assertIn("previous bounded shutdown", failure["message"])

    def test_reboot_never_authenticates_reused_pid_and_start_token(self):
        self.write_process(41, "9001")
        self.mark("ready")
        self.boot_id.write_text("boot-b\n", encoding="utf-8")
        result = self.run_guard("prepare-start", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(self.failure.exists())

    def test_active_duplicate_is_rejected_without_failure_latch(self):
        self.write_process(41, "9001")
        self.mark("ready")
        result = self.run_guard("prepare-start", check=False)
        self.assertEqual(result.returncode, 75)
        self.assertFalse(self.failure.exists())
        self.run_guard("finalize-stop")
        self.assertFalse(self.failure.exists())

    def test_finalize_incomplete_stop_creates_latch(self):
        self.mark("stopping")
        result = self.run_guard("finalize-stop", check=False)
        self.assertEqual(result.returncode, 1)
        failure = json.loads(self.failure.read_text())
        self.assertIn("manager escalation", failure["message"])

    def test_existing_historical_latch_is_byte_preserved(self):
        self.mark("stopping")
        self.failure.parent.mkdir(parents=True, exist_ok=True)
        original = b'{"message":"historical","state":"failed"}\n'
        self.failure.write_bytes(original)
        result = self.run_guard("finalize-stop", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.failure.read_bytes(), original)

    def test_reviewed_recovery_requires_off_and_preserves_latch(self):
        self.mark("stopping")
        self.failure.parent.mkdir(parents=True, exist_ok=True)
        original = b'{"message":"historical","state":"failed"}\n'
        self.failure.write_bytes(original)
        preference = self.failure.parent / "ram-tetris-enabled"
        preference.write_text("on\n", encoding="utf-8")
        arguments = (
            "acknowledge-reviewed-recovery",
            "--acknowledge-reviewed-recovery",
        )
        refused = self.run_guard(*arguments, check=False)
        self.assertNotEqual(refused.returncode, 0)

        preference.write_text("off\n", encoding="utf-8")
        self.runtime.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(self.runtime / "ram-tetris.lock", os.O_CREAT | os.O_WRONLY)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = self.run_guard(*arguments, check=False)
            self.assertNotEqual(locked.returncode, 0)
        finally:
            os.close(lock_fd)
        self.run_guard(*arguments)
        state = json.loads(self.service_state.read_text())
        self.assertEqual(state["state"], "clean-stopped")
        self.assertEqual(state["reason"], "acknowledged-reviewed-recovery")
        self.assertEqual(self.failure.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
