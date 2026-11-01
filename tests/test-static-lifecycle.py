#!/usr/bin/env python3
"""Focused offline checks for the static OpenRGB lifecycle."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / "openrgb-lifecycle"
APPLY = ROOT / "apply-preset"
UNIT = ROOT / "systemd/omarchy-plus-openrgb-presets.service"
RECONCILER = ROOT / "reconcile-static-service"


class StaticLifecycleTests(unittest.TestCase):
    def test_unit_has_one_non_restarting_static_lifecycle(self) -> None:
        unit = UNIT.read_text(encoding="utf-8")
        self.assertIn("Type=simple", unit)
        self.assertIn("Restart=no", unit)
        self.assertIn("TimeoutStopSec=15", unit)
        self.assertIn("openrgb-lifecycle", unit)
        self.assertNotIn("openrgb-service-guard", unit)
        self.assertNotIn("ExecStartPost", unit)
        self.assertNotIn("ExecStopPost", unit)
        self.assertNotIn("notify", unit.lower())

    def test_service_reconciler_never_operates_the_service(self) -> None:
        source = RECONCILER.read_text(encoding="utf-8")
        self.assertIn('systemctl --user enable', source)
        self.assertIn('systemctl --user daemon-reload', source)
        self.assertNotIn("--now", source)
        for operation in (" start", " stop", " restart", " try-restart"):
            self.assertNotIn(operation, source)

    def test_lifecycle_refuses_a_real_competing_flock(self) -> None:
        with tempfile.TemporaryDirectory() as runtime:
            lock_dir = Path(runtime) / "omarchy-plus/openrgb-presets-static"
            lock_dir.mkdir(parents=True)
            lock_path = lock_dir / "lifecycle.flock"
            with lock_path.open("w", encoding="utf-8") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                command = (
                    f'source {LIFECYCLE!s}; '
                    'if acquire_lifecycle; then exit 0; else exit 75; fi'
                )
                result = subprocess.run(
                    ["/usr/bin/bash", "-c", command],
                    env=os.environ | {"XDG_RUNTIME_DIR": runtime},
                    check=False,
                )
            self.assertEqual(result.returncode, 75)

    def test_failed_spd_checkpoint_cannot_reach_a_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as state_home, tempfile.TemporaryDirectory() as marker_dir:
            marker = Path(marker_dir) / "write"
            command = f"""
source {APPLY!s}
validate_package() {{ return 0; }}
validate_spd() {{ return 1; }}
run_openrgb() {{ : > {marker!s}; }}
run_effects() {{ : > {marker!s}; }}
main deep-red
"""
            result = subprocess.run(
                ["/usr/bin/bash", "-c", command],
                env=os.environ | {"XDG_STATE_HOME": state_home},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())
            self.assertIn("Four healthy SPD5118", result.stderr)

    def test_mutation_lock_descriptor_is_closed_for_children(self) -> None:
        command = f"""
source {APPLY!s}
exec 9>/dev/null
run_child /usr/bin/bash -c 'test ! -e /proc/self/fd/9'
"""
        result = subprocess.run(
            ["/usr/bin/bash", "-c", command], check=False
        )
        self.assertEqual(result.returncode, 0)

    def test_runtime_has_no_automatic_sdk_restart_or_hardware_poll_loop(self) -> None:
        lifecycle = LIFECYCLE.read_text(encoding="utf-8")
        self.assertIn("refusing automatic restart", lifecycle)
        self.assertEqual(lifecycle.count("restore_preset"), 3)
        self.assertNotIn("start_server\n", lifecycle)
        self.assertNotIn("ram-tetris", lifecycle.lower())
        self.assertNotIn("checkpoint", lifecycle.lower())
        self.assertNotIn("recovery", lifecycle.lower())
        resume = lifecycle.split("resume_from_sleep() {", 1)[1].split("\n}", 1)[0]
        startup = lifecycle.split("main() {", 1)[1]
        self.assertIn("restore_preset non-ram", resume)
        self.assertIn("restore_preset\n", startup)

    def test_mutations_revalidate_sdk_owner_immediately(self) -> None:
        helper = APPLY.read_text(encoding="utf-8")
        openrgb_body = helper.split("run_openrgb() {", 1)[1].split("\n}", 1)[0]
        effects_body = helper.split("run_effects() {", 1)[1].split("\n}", 1)[0]
        self.assertIn("validate_sdk_owner", openrgb_body)
        self.assertIn("validate_sdk_owner", effects_body)
        self.assertIn("validate_spd", openrgb_body)
        self.assertIn("validate_spd", effects_body)
        self.assertIn("--nodetect", openrgb_body)


if __name__ == "__main__":
    unittest.main()
