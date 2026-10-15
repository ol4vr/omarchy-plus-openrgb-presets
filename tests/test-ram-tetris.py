#!/usr/bin/python3
"""Focused offline validation for the v0.4.12 RAM Tetris integration."""

from __future__ import annotations

import fcntl
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from fractions import Fraction
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True

core_spec = importlib.util.spec_from_file_location(
    "ram_tetris_core", ROOT / "ram_tetris_core.py"
)
assert core_spec and core_spec.loader
core = importlib.util.module_from_spec(core_spec)
sys.modules[core_spec.name] = core
core_spec.loader.exec_module(core)

loader = importlib.machinery.SourceFileLoader(
    "ram_tetris_runtime", str(ROOT / "ram-tetris")
)
runtime_spec = importlib.util.spec_from_loader(loader.name, loader)
assert runtime_spec
runtime = importlib.util.module_from_spec(runtime_spec)
sys.modules[runtime_spec.name] = runtime
loader.exec_module(runtime)


class FakeSDK:
    def __init__(self, color: str = "#180000") -> None:
        self.writes: list[tuple[int, tuple[str, ...]]] = []
        self.controllers = [
            runtime.ControllerSnapshot(
                index,
                identity.name,
                identity.location,
                "Direct",
                12,
                (color,) * 12,
            )
            for index, identity in enumerate(core.VERIFIED_DIMMS)
        ]
        self.controllers.extend(
            runtime.ControllerSnapshot(
                index, f"non-ddr-{index}", f"usb:{index}", "Direct", 1, ("#000000",)
            )
            for index in range(4, 7)
        )

    def inventory(self):
        return tuple(self.controllers)

    def active_effects(self):
        return ("Sunrise",)

    def update_leds(self, index, colors):
        value = tuple(colors)
        self.writes.append((index, value))
        old = self.controllers[index]
        self.controllers[index] = runtime.ControllerSnapshot(
            old.index, old.name, old.location, old.mode, old.led_count, value
        )


class FakeHealth:
    def __init__(self, fail_spd: bool = False) -> None:
        self.fail_spd = fail_spd
        self.begun = False

    def begin(self):
        self.begun = True

    def verify_processes(self):
        return None

    def temperatures(self):
        if self.fail_spd:
            raise runtime.SafetyStop("10-0050 temperature is unreadable")
        return {endpoint: 40_000 for endpoint in runtime.SPD_ENDPOINTS}

    def no_new_kernel_errors(self):
        return None


class FakeEffects:
    def verify(self, active):
        if tuple(active) != ("Sunrise",):
            raise runtime.SafetyStop("effects changed")


class FakeControl:
    def __init__(self, reason: str | None) -> None:
        self.reason = reason
        self.states: list[str] = []

    def stop_reason(self):
        return self.reason

    def status(self, state, _message, **_extra):
        self.states.append(state)


class PaletteAndFrames(unittest.TestCase):
    def test_all_twelve_exact_palettes(self):
        self.assertEqual(len(core.PRESET_PALETTES), 12)
        self.assertEqual(
            core.PRESET_PALETTES["horde-red"],
            ("#8B0000", "#680000", "#4A0000", "#180000"),
        )
        self.assertEqual(
            core.PRESET_PALETTES["alliance-blue"],
            ("#0033AA", "#002788", "#001A66", "#000B22"),
        )
        self.assertEqual(
            core.PRESET_PALETTES["matte-black-orange"],
            ("#FF4400", "#E83B00", "#C92B00", "#501000"),
        )
        self.assertEqual(
            core.PRESET_PALETTES["electric-sunrise"],
            ("#FF0040", "#FF0051", "#3C00FF", "#0044FF"),
        )
        self.assertTrue(
            all(
                core.OFF not in palette
                for name, palette in core.PRESET_PALETTES.items()
                if name != "black"
            )
        )

    def test_cycle_is_36_accumulation_frames_plus_reset(self):
        frames = core.generate_cycle("horde-red", 24)
        self.assertEqual(len(frames), 37)
        self.assertTrue(frames[-1].reset)
        self.assertEqual(frames[-1].colors, (core.OFF,) * 12)
        self.assertEqual(
            [
                sum(color != core.OFF for color in frame.colors)
                for frame in frames
                if frame.block == 5
            ],
            [12],
        )

    def test_landed_block_colors_persist(self):
        frames = core.generate_cycle("horde-red", 24)
        first_landed = frames[10].colors[10:12]
        self.assertNotEqual(first_landed, (core.OFF, core.OFF))
        for frame in frames[11:-1]:
            self.assertEqual(frame.colors[10:12], first_landed)

    def test_single_colors_do_not_randomize_and_black_is_off(self):
        self.assertEqual(
            {
                color
                for frame in core.generate_cycle("deep-blue", 9)
                for color in frame.colors
            },
            {core.OFF, "#000B22"},
        )
        self.assertEqual(core.generate_cycle("black", 9)[0].colors, (core.OFF,) * 12)

    def test_static_fallbacks_are_unchanged(self):
        self.assertEqual(core.STATIC_DDR5_COLORS["animated-rainbow"], "#404040")
        self.assertEqual(core.STATIC_DDR5_COLORS["electric-sunrise"], "#3C00FF")
        self.assertEqual(core.STATIC_DDR5_COLORS["horde-red"], "#180000")
        self.assertEqual(core.STATIC_DDR5_COLORS["black"], core.OFF)


class SchedulerTests(unittest.TestCase):
    def test_independent_seeds_phases_and_randomized_intervals(self):
        streams = core.default_streams("horde-red", 24)
        self.assertEqual(len({stream.seed for stream in streams}), 4)
        self.assertEqual(
            [stream.due for stream in streams],
            [Fraction(0), Fraction(1, 25), Fraction(2, 25), Fraction(3, 25)],
        )
        timings = [core.frame_intervals(stream.seed, 0) for stream in streams]
        self.assertGreater(len(set(timings)), 1)
        self.assertTrue(
            all(set(values) <= set(core.FRAME_INTERVALS) for values in timings)
        )

    def test_simulated_coordinator_enforces_both_rate_limits(self):
        streams = list(core.default_streams("horde-red", 24))
        last_global = None
        last_dimm = {}
        writes = []
        previous = {}
        for _ in range(300):
            stream = min(streams, key=lambda item: (item.due, item.identity.location))
            at = stream.due
            if last_global is not None:
                at = max(at, last_global + Fraction(1, 20))
            if stream.identity in last_dimm:
                at = max(at, last_dimm[stream.identity] + Fraction(1, 5))
            if last_global is not None:
                self.assertGreaterEqual(at - last_global, Fraction(1, 20))
            if stream.identity in last_dimm:
                self.assertGreaterEqual(at - last_dimm[stream.identity], Fraction(1, 5))
            self.assertNotEqual(previous.get(stream.identity), stream.frame.colors)
            writes.append((at, stream.identity))
            previous[stream.identity] = stream.frame.colors
            last_global = at
            last_dimm[stream.identity] = at
            stream.advance(at)
        counts = {
            identity: sum(item[1] == identity for item in writes)
            for identity in core.VERIFIED_DIMMS
        }
        self.assertGreaterEqual(min(counts.values()), 65)
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 10)

    def test_no_catchup_after_delay(self):
        stream = core.default_streams("horde-red", 24)[0]
        stream.advance(Fraction(10))
        self.assertGreaterEqual(stream.due, Fraction(51, 5))


class ProcessIdentityTests(unittest.TestCase):
    @staticmethod
    def write_process(
        proc_root: Path,
        pid: int,
        ppid: int,
        argv: tuple[str, ...] = runtime.LIFECYCLE_ARGV,
    ) -> None:
        process = proc_root / str(pid)
        process.mkdir()
        process.joinpath("cmdline").write_bytes(
            b"\0".join(item.encode() for item in argv) + b"\0"
        )
        process.joinpath("status").write_text(
            f"Name:\tbash\nPid:\t{pid}\nPPid:\t{ppid}\n",
            encoding="utf-8",
        )

    def test_three_same_argv_processes_reduce_to_the_owned_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            self.write_process(proc_root, 300, 100)
            self.write_process(proc_root, 301, 300)
            self.write_process(proc_root, 302, 301)

            self.assertEqual(
                runtime._independent_lifecycle_pids(300, proc_root), (300,)
            )

    def test_independent_same_argv_lifecycle_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            self.write_process(proc_root, 100, 1, ("/usr/bin/quickshell",))
            self.write_process(proc_root, 300, 100)
            self.write_process(proc_root, 301, 300)
            self.write_process(proc_root, 400, 100)

            self.assertEqual(
                runtime._independent_lifecycle_pids(300, proc_root), (300, 400)
            )


class RuntimeSafetyTests(unittest.TestCase):
    def writer(self, reason, *, fail_spd=False):
        sdk = FakeSDK("#8B0000")
        control = FakeControl(reason)
        writer = runtime.TetrisWriter(
            sdk, FakeHealth(fail_spd), FakeEffects(), control, "horde-red"
        )
        return writer, sdk, control

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_user_off_restores_four_static_arrays(self, _preset, _preference):
        writer, sdk, control = self.writer("user-off")
        writer.run()
        self.assertEqual(len(sdk.writes), 4)
        self.assertTrue(all(colors == ("#180000",) * 12 for _, colors in sdk.writes))
        self.assertEqual(control.states[-1], "off")

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_preset_transition_stops_without_restoration(self, _preset, _preference):
        writer, sdk, control = self.writer("preset-change")
        writer.run()
        self.assertEqual(sdk.writes, [])
        self.assertEqual(control.states[-1], "stopped")

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_spd_failure_writes_nothing_and_does_not_restore(
        self, _preset, _preference
    ):
        writer, sdk, _control = self.writer(None, fail_spd=True)
        with self.assertRaisesRegex(runtime.SafetyStop, "temperature"):
            writer.run()
        self.assertEqual(sdk.writes, [])

    def test_default_off_and_separate_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ | {
                "HOME": directory,
                "XDG_STATE_HOME": f"{directory}/state",
                "XDG_RUNTIME_DIR": f"{directory}/runtime",
            }
            subprocess.run(
                [ROOT / "ram-tetris", "status"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            status = json.loads(
                subprocess.run(
                    [ROOT / "ram-tetris", "status"],
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            )
            self.assertFalse(status["preference"])
            subprocess.run(
                [ROOT / "ram-tetris", "enable"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                Path(
                    env["XDG_STATE_HOME"],
                    "omarchy-plus/openrgb-presets/ram-tetris-enabled",
                ).read_text(),
                "on\n",
            )
            subprocess.run(
                [ROOT / "ram-tetris", "disable"],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                Path(
                    env["XDG_STATE_HOME"],
                    "omarchy-plus/openrgb-presets/ram-tetris-enabled",
                ).read_text(),
                "off\n",
            )
            stop = json.loads(
                Path(
                    env["XDG_RUNTIME_DIR"],
                    "omarchy-plus/openrgb-presets/ram-tetris.stop",
                ).read_text()
            )
            self.assertEqual(stop["reason"], "user-off")

    def test_disposable_checkout_commands_do_not_create_bytecode(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory, "plugin")
            checkout.mkdir()
            for name in ("ram-tetris", "ram_tetris_core.py"):
                shutil.copy2(ROOT / name, checkout / name)

            state_home = Path(directory, "state")
            runtime_home = Path(directory, "runtime")
            env = os.environ | {
                "HOME": directory,
                "XDG_STATE_HOME": str(state_home),
                "XDG_RUNTIME_DIR": str(runtime_home),
            }
            env.pop("PYTHONDONTWRITEBYTECODE", None)
            entrypoint = checkout / "ram-tetris"
            commands = (
                ("status",),
                ("enable",),
                ("disable",),
                ("request-stop", "user-off"),
                ("clear-stop",),
                ("fail", "simulated communication failure"),
                ("clear-failure", "--acknowledge-reviewed-recovery"),
                (
                    "run",
                    "--server-pid",
                    "1",
                    "--server-start",
                    "1",
                    "--lifecycle-pid",
                    "1",
                    "--lifecycle-start",
                    "1",
                ),
            )
            for command in commands:
                subprocess.run(
                    [entrypoint, *command],
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            self.assertFalse(any(checkout.rglob("__pycache__")))
            self.assertFalse(any(checkout.rglob("*.pyc")))

    def test_duplicate_runner_lock_fails_closed_before_hardware(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory, "state/omarchy-plus/openrgb-presets")
            runtime_root = Path(directory, "runtime/omarchy-plus/openrgb-presets")
            state.mkdir(parents=True)
            runtime_root.mkdir(parents=True)
            (state / "active-preset").write_text("horde-red\n")
            (state / "ram-tetris-enabled").write_text("on\n")
            env = os.environ | {
                "XDG_STATE_HOME": str(Path(directory, "state")),
                "XDG_RUNTIME_DIR": str(Path(directory, "runtime")),
            }
            with (runtime_root / "ram-tetris.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = subprocess.run(
                    [
                        ROOT / "ram-tetris",
                        "run",
                        "--server-pid",
                        "1",
                        "--server-start",
                        "1",
                        "--lifecycle-pid",
                        "1",
                        "--lifecycle-start",
                        "1",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            self.assertEqual(result.returncode, 75)

    def test_failure_latch_persists_and_toggle_cannot_clear_it(self):
        with tempfile.TemporaryDirectory() as directory:
            state_home = Path(directory, "state")
            first_runtime = Path(directory, "runtime-one")
            second_runtime = Path(directory, "runtime-two")
            env = os.environ | {
                "HOME": directory,
                "XDG_STATE_HOME": str(state_home),
                "XDG_RUNTIME_DIR": str(first_runtime),
            }

            subprocess.run(
                [ROOT / "ram-tetris", "enable"],
                env=env,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [ROOT / "ram-tetris", "fail", "simulated SPD failure"],
                env=env,
                check=True,
                capture_output=True,
            )
            failure_path = (
                state_home / "omarchy-plus/openrgb-presets/ram-tetris-failure.json"
            )
            self.assertTrue(failure_path.is_file())

            subprocess.run(
                [ROOT / "ram-tetris", "disable"],
                env=env,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [ROOT / "ram-tetris", "enable"],
                env=env,
                check=True,
                capture_output=True,
            )
            status = json.loads(
                subprocess.run(
                    [ROOT / "ram-tetris", "status"],
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            )
            self.assertEqual(status["state"], "failed")
            self.assertTrue(status["preference"])

            relaunched_env = env | {"XDG_RUNTIME_DIR": str(second_runtime)}
            relaunched_status = json.loads(
                subprocess.run(
                    [ROOT / "ram-tetris", "status"],
                    env=relaunched_env,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            )
            self.assertEqual(relaunched_status["state"], "failed")
            refused = subprocess.run(
                [
                    ROOT / "ram-tetris",
                    "clear-failure",
                    "--acknowledge-reviewed-recovery",
                ],
                env=relaunched_env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertTrue(failure_path.exists())

            subprocess.run(
                [ROOT / "ram-tetris", "disable"],
                env=relaunched_env,
                check=True,
                capture_output=True,
            )
            missing_acknowledgement = subprocess.run(
                [ROOT / "ram-tetris", "clear-failure"],
                env=relaunched_env,
                check=False,
                capture_output=True,
            )
            self.assertNotEqual(missing_acknowledgement.returncode, 0)
            subprocess.run(
                [
                    ROOT / "ram-tetris",
                    "clear-failure",
                    "--acknowledge-reviewed-recovery",
                ],
                env=relaunched_env,
                check=True,
                capture_output=True,
            )
            self.assertFalse(failure_path.exists())

    def test_sdk_connection_failure_is_persistently_latched(self):
        class FailingSDK:
            def open(self):
                raise runtime.SafetyStop("simulated SDK connection failure")

            def close(self):
                return None

        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory, "state/omarchy-plus/openrgb-presets")
            state.mkdir(parents=True)
            (state / "active-preset").write_text("horde-red\n")
            (state / "ram-tetris-enabled").write_text("on\n")
            environment = {
                "HOME": directory,
                "XDG_STATE_HOME": str(Path(directory, "state")),
                "XDG_RUNTIME_DIR": str(Path(directory, "runtime")),
            }
            arguments = runtime.argparse.Namespace(
                server_pid=100,
                server_start="200",
                lifecycle_pid=300,
                lifecycle_start="400",
            )
            continuity = runtime.LifecycleIdentity(300, "400", "boot", 0)
            with (
                mock.patch.dict(os.environ, environment, clear=False),
                mock.patch.object(runtime, "OpenRGBSDK", return_value=FailingSDK()),
                mock.patch.object(
                    runtime, "_lifecycle_identity", return_value=continuity
                ),
            ):
                self.assertEqual(runtime._run(arguments), 1)
            failure = json.loads((state / "ram-tetris-failure.json").read_text())
            self.assertEqual(failure["state"], "failed")
            self.assertIn("SDK connection", failure["message"])


class EffectsContractTests(unittest.TestCase):
    def test_spectrum_wave_uses_the_live_effect_display_name(self):
        contract = runtime.EffectsContract("spectrum-wave", ROOT)

        self.assertEqual(contract.expected, Counter({"Rainbow Wave": 1}))
        contract.verify(("Rainbow Wave",))
        for active in ((), ("RainbowWave",), ("Rainbow Wave", "Sunrise")):
            with (
                self.subTest(active=active),
                self.assertRaisesRegex(
                    runtime.SafetyStop,
                    "live Effects instances changed or include DDR5",
                ),
            ):
                contract.verify(active)

    def test_other_accepted_live_effect_names_are_unchanged(self):
        expected = {
            "neon-rain": "Rain",
            "aurora-comet": "Comet",
            "electric-sunrise": "Sunrise",
            "matte-black-orange": "Sunrise",
            "horde-red": "Sunrise",
            "alliance-blue": "Sunrise",
        }

        for preset, effect in expected.items():
            with self.subTest(preset=preset):
                contract = runtime.EffectsContract(preset, ROOT)
                self.assertEqual(contract.expected, Counter({effect: 1}))
                contract.verify((effect,))


class IntegrationSourceTests(unittest.TestCase):
    def test_panel_has_toggle_and_unchanged_twelve_card_navigation(self):
        panel = (ROOT / "Panel.qml").read_text()
        preset_section = panel.split("readonly property var presets:", 1)[1].split(
            "readonly property var activePresetData", 1
        )[0]
        self.assertEqual(preset_section.count('id: "'), 12)
        self.assertIn("RAM TETRIS", panel)
        self.assertIn("toggleRamTetris", panel)
        self.assertIn("var columns = 2", panel)
        self.assertIn("onActivateRequested: root.applySelectedPreset()", panel)

    def test_lifecycle_owns_one_writer_and_quiesces_for_sleep_handoff(self):
        lifecycle = (ROOT / "openrgb-lifecycle").read_text()
        runner = (ROOT / "ram-tetris").read_text()
        self.assertIn('--pdeathsig TERM "${RAM_TETRIS}" run', lifecycle)
        self.assertIn("stop_tetris suspend", lifecycle)
        self.assertIn("stop_tetris handoff", lifecycle)
        self.assertIn("reconcile_tetris", lifecycle)
        self.assertIn("ram-tetris.lock", (ROOT / "apply-preset").read_text())
        sleep_handler = lifecycle.split("handle_sleep_signal() {", 1)[1].split(
            "cleanup() {", 1
        )[0]
        self.assertLess(
            sleep_handler.index("stop_tetris suspend"),
            sleep_handler.index("stop_server 'suspend'"),
        )
        cleanup = lifecycle.split("cleanup() {", 1)[1].split("request_shutdown() {", 1)[
            0
        ]
        self.assertLess(
            cleanup.index("stop_tetris handoff"), cleanup.index("detach_server")
        )
        self.assertIn("self.health.verify_processes()", runner)
        self.assertIn("OpenRGB SDK process identity changed", runner)

    def test_preset_transition_owns_stop_marker_until_static_apply_finishes(self):
        apply = (ROOT / "apply-preset").read_text()
        lifecycle = (ROOT / "openrgb-lifecycle").read_text()
        runner = (ROOT / "ram-tetris").read_text()
        request = apply.index('"${RAM_TETRIS}" request-stop preset-change')
        tetris_lock = apply.index('exec 8>"${TETRIS_LOCK_FILE}"')
        quiesced = apply.index("/usr/bin/flock --wait 10 8")
        apply_call = apply.index('apply_preset "${preset}"', quiesced)
        clear = apply.index('"${RAM_TETRIS}" clear-stop', apply_call)
        self.assertLess(request, tetris_lock)
        self.assertLess(tetris_lock, quiesced)
        self.assertLess(quiesced, apply_call)
        self.assertLess(apply_call, clear)
        quiescence_failure = apply.split("if ! /usr/bin/flock --wait 10 8; then", 1)[
            1
        ].split("fi", 1)[0]
        self.assertIn("return 75", quiescence_failure)
        self.assertNotIn("apply_preset", quiescence_failure)
        self.assertIn('exec 9>"${LOCK_FILE}"', apply)
        start_function = lifecycle.split("start_tetris() {", 1)[1].split(
            "stop_tetris() {", 1
        )[0]
        self.assertNotIn("clear-stop", start_function)
        self.assertIn(
            "if control.stop_reason() is not None:\n            return 75", runner
        )
        black_gate = '[[ "$(tetris_selected_preset)" != black ]] || return 0'
        self.assertIn(black_gate, start_function)

    def test_effect_profiles_still_have_only_six_non_ddr_assignments(self):
        for profile in (ROOT / "effects-profiles").iterdir():
            document = json.loads(profile.read_text())
            zones = [
                zone
                for effect in document["Effects"]
                for zone in effect["ControllerZones"]
            ]
            self.assertEqual(len(zones), 6)
            self.assertTrue(
                all(zone.get("name") != core.VERIFIED_DIMMS[0].name for zone in zones)
            )


if __name__ == "__main__":
    unittest.main()
