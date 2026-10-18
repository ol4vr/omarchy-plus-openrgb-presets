#!/usr/bin/python3
"""Focused offline validation for the v0.4.21 RAM Tetris integration."""

from __future__ import annotations

import fcntl
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from collections import Counter
from contextlib import redirect_stdout
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
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
    def __init__(
        self,
        color: str = "#180000",
        colors: tuple[str, ...] | None = None,
    ) -> None:
        initial = colors if colors is not None else (color,) * core.LED_COUNT
        self.writes: list[tuple[int, tuple[str, ...]]] = []
        self.controllers = [
            runtime.ControllerSnapshot(
                index,
                identity.name,
                identity.location,
                "Direct",
                12,
                initial,
            )
            for index, identity in enumerate(core.VERIFIED_DIMMS)
        ]
        self.controllers.extend(
            runtime.ControllerSnapshot(
                index, f"non-ddr-{index}", f"usb:{index}", "Direct", 1, ("#000000",)
            )
            for index in range(4, 7)
        )

    def open(self):
        return None

    def close(self):
        return None

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
    def __init__(
        self, fail_spd: bool = False, process_failure: str | None = None
    ) -> None:
        self.fail_spd = fail_spd
        self.process_failure = process_failure
        self.begun = False
        self.window_checks = 0
        self.server = runtime.ServerIdentity(200, "server-start")
        self.lifecycle = runtime.LifecycleIdentity(300, "lifecycle-start", "boot", 0)

    def begin(self):
        self.begun = True

    def verify_processes(self):
        if self.process_failure is not None:
            raise runtime.SafetyStop(self.process_failure)

    def temperatures(self):
        if self.fail_spd:
            raise runtime.SafetyStop("10-0050 temperature is unreadable")
        return {endpoint: 40_000 for endpoint in runtime.SPD_ENDPOINTS}

    def no_new_kernel_errors(self):
        return None

    def no_kernel_errors_since_baseline(self):
        self.window_checks += 1


class WindowHealth(FakeHealth):
    def __init__(self, window_events: list[str | None]) -> None:
        super().__init__()
        self.window_events = list(window_events)

    def no_kernel_errors_since_baseline(self):
        super().no_kernel_errors_since_baseline()
        event = self.window_events.pop(0)
        if event is not None:
            raise runtime.SafetyStop(f"new relevant kernel error: {event}")


class SequencedSDK(FakeSDK):
    def __init__(self, controller_counts: list[int]) -> None:
        super().__init__("#8B0000")
        self.controller_counts = list(controller_counts)
        self.inventory_calls = 0

    def inventory(self):
        count = self.controller_counts[self.inventory_calls]
        self.inventory_calls += 1
        return tuple(self.controllers[:count])


class FakeEffects:
    def verify(self, active):
        if tuple(active) != ("Sunrise",):
            raise runtime.SafetyStop("effects changed")


class FakeControl:
    def __init__(
        self, reason: str | None, request: runtime.StopRequest | None = None
    ) -> None:
        self.request = request
        if request is None and reason is not None:
            self.request = runtime.StopRequest(reason)
        self.states: list[str] = []

    def stop_reason(self):
        return self.request.reason if self.request is not None else None

    def stop_request(self):
        return self.request

    def status(self, state, _message, **_extra):
        self.states.append(state)


class PaletteAndFrames(unittest.TestCase):
    def test_all_twelve_exact_palettes(self):
        self.assertEqual(
            core.PRESET_PALETTES,
            {
                "deep-red": ("#8B0000",),
                "deep-blue": ("#000B22",),
                "bright-white": ("#FFFFFF",),
                "animated-rainbow": (
                    "#11FF00",
                    "#8A2BE2",
                    "#FFD400",
                    "#FF0040",
                ),
                "neon-rain": (
                    "#5500FF",
                    "#11FF00",
                    "#00FF8C",
                    "#FF00F6",
                    "#FFD400",
                ),
                "aurora-comet": ("#95FF00", "#00D4FF", "#8A2BE2"),
                "spectrum-wave": (
                    "#11FF00",
                    "#8A2BE2",
                    "#FFD400",
                    "#FF0040",
                ),
                "electric-sunrise": (
                    "#FF0040",
                    "#FF0051",
                    "#3C00FF",
                    "#0044FF",
                ),
                "matte-black-orange": (
                    "#FF4400",
                    "#E83B00",
                    "#C92B00",
                    "#501000",
                ),
                "black": (),
                "horde-red": ("#8B0000", "#680000", "#4A0000", "#180000"),
                "alliance-blue": (
                    "#0033AA",
                    "#002788",
                    "#001A66",
                    "#000B22",
                ),
            },
        )
        self.assertTrue(
            all(
                core.OFF not in palette
                for name, palette in core.PRESET_PALETTES.items()
                if name != "black"
            )
        )

    def test_rainbow_blocks_use_only_the_refined_palette(self):
        expected = {"#11FF00", "#8A2BE2", "#FFD400", "#FF0040"}
        for preset in ("animated-rainbow", "spectrum-wave"):
            observed: set[str] = set()
            for seed in range(16):
                frames = core.generate_cycle(preset, seed)
                landed = frames[-2].colors
                self.assertNotIn(core.OFF, landed)
                self.assertLessEqual(set(landed), expected)
                for index in range(0, core.LED_COUNT, core.BLOCK_SIZE):
                    self.assertEqual(landed[index], landed[index + 1])
                observed.update(landed)
            self.assertEqual(observed, expected)

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

    def test_all_static_fallback_patterns_are_exact_palette_pairs(self):
        expected_pairs = {
            "deep-red": ("#8B0000",) * 6,
            "deep-blue": ("#000B22",) * 6,
            "bright-white": ("#FFFFFF",) * 6,
            "animated-rainbow": (
                "#11FF00",
                "#8A2BE2",
                "#FFD400",
                "#FF0040",
                "#8A2BE2",
                "#11FF00",
            ),
            "neon-rain": (
                "#5500FF",
                "#11FF00",
                "#00FF8C",
                "#FF00F6",
                "#FFD400",
                "#5500FF",
            ),
            "aurora-comet": (
                "#95FF00",
                "#00D4FF",
                "#8A2BE2",
                "#8A2BE2",
                "#00D4FF",
                "#95FF00",
            ),
            "spectrum-wave": (
                "#11FF00",
                "#8A2BE2",
                "#FFD400",
                "#FF0040",
                "#8A2BE2",
                "#11FF00",
            ),
            "electric-sunrise": (
                "#FF0040",
                "#FF0051",
                "#3C00FF",
                "#0044FF",
                "#FF0051",
                "#FF0040",
            ),
            "matte-black-orange": (
                "#FF4400",
                "#E83B00",
                "#C92B00",
                "#501000",
                "#E83B00",
                "#FF4400",
            ),
            "black": (core.OFF,) * 6,
            "horde-red": (
                "#8B0000",
                "#680000",
                "#4A0000",
                "#180000",
                "#680000",
                "#8B0000",
            ),
            "alliance-blue": (
                "#0033AA",
                "#002788",
                "#001A66",
                "#000B22",
                "#002788",
                "#0033AA",
            ),
        }
        for preset, pair_pattern in expected_pairs.items():
            pattern = core.static_pattern_for(preset)
            self.assertEqual(len(pattern), core.LED_COUNT, preset)
            self.assertEqual(pattern[::2], pair_pattern, preset)
            self.assertEqual(pattern[1::2], pair_pattern, preset)
            if preset == "black":
                self.assertEqual(set(pattern), {core.OFF})
            else:
                self.assertEqual(set(pattern), set(core.PRESET_PALETTES[preset]))


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
        expected = core.static_pattern_for("horde-red")
        self.assertTrue(all(colors == expected for _, colors in sdk.writes))
        self.assertEqual(control.states[-1], "off")

    @mock.patch.object(runtime, "_preference", return_value=False)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_user_off_preference_transition_is_a_clean_stop(self, _preset, _preference):
        writer, sdk, control = self.writer("user-off")
        writer.run()
        self.assertEqual(len(sdk.writes), 4)
        expected = core.static_pattern_for("horde-red")
        self.assertTrue(all(colors == expected for _, colors in sdk.writes))
        self.assertEqual(control.states[-1], "off")

    @mock.patch.object(runtime, "_preference", return_value=False)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_unexplained_preference_change_still_fails_closed(
        self, _preset, _preference
    ):
        writer, sdk, _control = self.writer(None)
        with self.assertRaisesRegex(runtime.SafetyStop, "preference changed"):
            writer.run()
        self.assertEqual(sdk.writes, [])

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_user_off_skips_already_correct_static_arrays(self, _preset, _preference):
        sdk = FakeSDK(colors=core.static_pattern_for("horde-red"))
        control = FakeControl("user-off")
        writer = runtime.TetrisWriter(
            sdk, FakeHealth(), FakeEffects(), control, "horde-red"
        )
        writer.run()
        self.assertEqual(sdk.writes, [])
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
    def test_authenticated_handoff_accepts_real_zero_owner_interval(
        self, _preset, _preference
    ):
        health = FakeHealth(process_failure="expected one OpenRGB lifecycle, found 0")
        request = runtime.StopRequest(
            "handoff", 300, "lifecycle-start", 200, "server-start"
        )
        sdk = FakeSDK("#8B0000")
        control = FakeControl(None, request)
        writer = runtime.TetrisWriter(sdk, health, FakeEffects(), control, "horde-red")

        writer.run()

        self.assertEqual(sdk.writes, [])
        self.assertEqual(control.states, ["stopped"])

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_persistent_missing_lifecycle_without_handoff_still_fails_closed(
        self, _preset, _preference
    ):
        sdk = FakeSDK("#8B0000")
        writer = runtime.TetrisWriter(
            sdk,
            FakeHealth(process_failure="expected one OpenRGB lifecycle, found 0"),
            FakeEffects(),
            FakeControl(None),
            "horde-red",
        )

        with self.assertRaisesRegex(runtime.SafetyStop, "found 0"):
            writer.run()
        self.assertEqual(sdk.writes, [])

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_unexpected_parent_death_without_handoff_still_fails_closed(
        self, _preset, _preference
    ):
        writer, sdk, _control = self.writer(None)
        writer.request_termination(signal.SIGTERM)

        with self.assertRaisesRegex(runtime.SafetyStop, "not preceded"):
            writer.run()
        self.assertEqual(sdk.writes, [])

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_duplicate_lifecycle_and_sdk_identity_changes_still_fail_closed(
        self, _preset, _preference
    ):
        for failure in (
            "expected one OpenRGB lifecycle, found 2",
            "OpenRGB SDK process identity changed",
        ):
            with self.subTest(failure=failure):
                sdk = FakeSDK("#8B0000")
                writer = runtime.TetrisWriter(
                    sdk,
                    FakeHealth(process_failure=failure),
                    FakeEffects(),
                    FakeControl(None),
                    "horde-red",
                )
                with self.assertRaisesRegex(runtime.SafetyStop, failure):
                    writer.run()
                self.assertEqual(sdk.writes, [])

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_mismatched_handoff_identity_is_not_authorized(self, _preset, _preference):
        request = runtime.StopRequest("handoff", 999, "wrong", 200, "server-start")
        sdk = FakeSDK("#8B0000")
        writer = runtime.TetrisWriter(
            sdk,
            FakeHealth(),
            FakeEffects(),
            FakeControl(None, request),
            "horde-red",
        )

        with self.assertRaisesRegex(runtime.SafetyStop, "does not match"):
            writer.run()
        self.assertEqual(sdk.writes, [])

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_stop_publication_excludes_writes_and_blocks_later_frames(
        self, _preset, _preference
    ):
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                "XDG_STATE_HOME": f"{directory}/state",
                "XDG_RUNTIME_DIR": f"{directory}/runtime",
            }
            with mock.patch.dict(os.environ, environment, clear=False):
                control = runtime.RuntimeControl()
                gate_fd = os.open(
                    control.write_lock_path, os.O_WRONLY | os.O_CREAT, 0o600
                )
                fcntl.flock(gate_fd, fcntl.LOCK_SH)
                published = threading.Event()
                request = runtime.StopRequest(
                    "handoff", 300, "lifecycle-start", 200, "server-start"
                )

                def publish():
                    control.publish_stop(request)
                    published.set()

                publisher = threading.Thread(target=publish)
                publisher.start()
                self.assertFalse(published.wait(0.05))
                self.assertFalse(control.stop_path.exists())
                fcntl.flock(gate_fd, fcntl.LOCK_UN)
                os.close(gate_fd)
                publisher.join(timeout=1)
                self.assertTrue(published.is_set())

                sdk = FakeSDK("#8B0000")
                writer_fd = os.open(control.write_lock_path, os.O_WRONLY)
                try:
                    writer = runtime.TetrisWriter(
                        sdk,
                        FakeHealth(),
                        FakeEffects(),
                        control,
                        "horde-red",
                        writer_fd,
                    )
                    writer.expected = {
                        identity: sdk.controllers[index].colors
                        for index, identity in enumerate(core.VERIFIED_DIMMS)
                    }
                    wrote = writer._write(
                        core.VERIFIED_DIMMS[0],
                        core.generate_cycle("horde-red", 24)[0].colors,
                    )
                finally:
                    os.close(writer_fd)

                self.assertFalse(wrote)
                self.assertEqual(sdk.writes, [])

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_handoff_interrupts_user_off_restoration_without_later_writes(
        self, _preset, _preference
    ):
        control = FakeControl("user-off")
        sdk = FakeSDK("#8B0000")
        original_update = sdk.update_leds

        def update_then_handoff(index, colors):
            original_update(index, colors)
            control.request = runtime.StopRequest(
                "handoff", 300, "lifecycle-start", 200, "server-start"
            )

        sdk.update_leds = update_then_handoff
        writer = runtime.TetrisWriter(
            sdk, FakeHealth(), FakeEffects(), control, "horde-red"
        )

        writer.run()

        self.assertEqual(len(sdk.writes), 1)
        self.assertEqual(control.states[-1], "stopped")

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_parent_loss_during_restoration_stops_without_later_writes(
        self, _preset, _preference
    ):
        control = FakeControl("user-off")
        sdk = FakeSDK("#8B0000")
        original_update = sdk.update_leds
        writer = runtime.TetrisWriter(
            sdk, FakeHealth(), FakeEffects(), control, "horde-red"
        )

        def update_then_lose_parent(index, colors):
            original_update(index, colors)
            writer.request_termination(signal.SIGTERM)

        sdk.update_leds = update_then_lose_parent

        with self.assertRaisesRegex(runtime.SafetyStop, "not preceded"):
            writer.run()
        self.assertEqual(len(sdk.writes), 1)

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_spd_failure_writes_nothing_and_does_not_restore(
        self, _preset, _preference
    ):
        writer, sdk, _control = self.writer(None, fail_spd=True)
        with self.assertRaisesRegex(runtime.SafetyStop, "temperature"):
            writer.run()
        self.assertEqual(sdk.writes, [])

    @mock.patch.object(runtime, "_preference", return_value=True)
    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_successor_runs_every_health_gate_before_writer_startup(
        self, _preset, _preference
    ):
        events: list[str] = []

        class RecordingHealth(FakeHealth):
            def begin(inner_self):
                events.append("kernel-baseline")

            def verify_processes(inner_self):
                events.append("sdk-listener-and-lifecycle")

            def temperatures(inner_self):
                events.append("spd")
                return super().temperatures()

            def no_new_kernel_errors(inner_self):
                events.append("kernel-errors")

        class RecordingSDK(FakeSDK):
            def inventory(inner_self):
                events.append("controllers")
                return super().inventory()

            def active_effects(inner_self):
                events.append("effects")
                return super().active_effects()

            def update_leds(inner_self, index, colors):
                events.append("write")
                super().update_leds(index, colors)

        class StopAfterStartup(FakeControl):
            def status(inner_self, state, _message, **_extra):
                events.append(f"status-{state}")
                inner_self.states.append(state)
                if state == "running":
                    inner_self.request = runtime.StopRequest(
                        "handoff", 300, "lifecycle-start", 200, "server-start"
                    )

        sdk = RecordingSDK("#8B0000")
        writer = runtime.TetrisWriter(
            sdk,
            RecordingHealth(),
            FakeEffects(),
            StopAfterStartup(None),
            "horde-red",
        )

        writer.run()

        self.assertEqual(
            events[:7],
            [
                "kernel-baseline",
                "sdk-listener-and-lifecycle",
                "spd",
                "kernel-errors",
                "controllers",
                "effects",
                "status-running",
            ],
        )
        self.assertNotIn("write", events)

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

    def test_disable_publishes_stop_before_preference_off(self):
        calls = []

        def record_stop(_control, reason, *_identity):
            calls.append(("stop", reason))

        def record_preference(path, value):
            calls.append(("preference", path.name, value))

        with tempfile.TemporaryDirectory() as directory:
            environment = {
                "XDG_STATE_HOME": f"{directory}/state",
                "XDG_RUNTIME_DIR": f"{directory}/runtime",
            }
            with (
                mock.patch.dict(os.environ, environment, clear=False),
                mock.patch.object(runtime, "_request_stop", side_effect=record_stop),
                mock.patch.object(
                    runtime, "_atomic_text", side_effect=record_preference
                ),
                mock.patch.object(sys, "argv", ["ram-tetris", "disable"]),
            ):
                self.assertEqual(runtime.main(), 0)

        self.assertEqual(
            calls,
            [
                ("stop", "user-off"),
                ("preference", "ram-tetris-enabled", "off\n"),
            ],
        )

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
                    check=command[0] != "clear-failure",
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

    def test_lifecycle_stop_cli_requires_bound_process_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime_home = Path(directory, "runtime")
            env = os.environ | {
                "XDG_STATE_HOME": str(Path(directory, "state")),
                "XDG_RUNTIME_DIR": str(runtime_home),
            }
            result = subprocess.run(
                [ROOT / "ram-tetris", "request-stop", "handoff"],
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires lifecycle and server identities", result.stderr)
            self.assertFalse(
                runtime_home.joinpath(
                    "omarchy-plus/openrgb-presets/ram-tetris.stop"
                ).exists()
            )

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
            deprecated_clear = subprocess.run(
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
            self.assertNotEqual(deprecated_clear.returncode, 0)
            self.assertIn("lighting-recovery", deprecated_clear.stderr)
            self.assertTrue(failure_path.exists())

    def test_new_failure_cannot_replace_retained_latch_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                "XDG_STATE_HOME": str(Path(directory, "state")),
                "OPENRGB_RUNTIME_DIR": str(Path(directory, "runtime")),
            }
            failure_path = Path(
                environment["XDG_STATE_HOME"],
                "omarchy-plus/openrgb-presets/ram-tetris-failure.json",
            )
            failure_path.parent.mkdir(parents=True)
            original = b'{"message":"October 16 incident","state":"failed"}\n'
            failure_path.write_bytes(original)

            with mock.patch.dict(os.environ, environment, clear=False):
                runtime.RuntimeControl().fail("later restoration failure")

            self.assertEqual(failure_path.read_bytes(), original)

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


class ServiceReadinessTests(unittest.TestCase):
    @staticmethod
    def arguments():
        return SimpleNamespace(
            lifecycle_pid=300,
            lifecycle_start="lifecycle-start",
            server_pid=200,
            server_start="server-start",
        )

    def run_discovery_window(self, counts, events):
        sdk = SequencedSDK(counts)
        health = WindowHealth(events)
        with (
            mock.patch.object(runtime, "OpenRGBSDK", return_value=sdk),
            mock.patch.object(
                runtime, "_lifecycle_identity", return_value=health.lifecycle
            ),
            mock.patch.object(runtime, "LinuxHealth", return_value=health),
            mock.patch.object(runtime.time, "sleep") as sleep,
        ):
            result = runtime._hardware_health(
                self.arguments(), attempts=len(counts), retry_delay=1.0
            )
        return result, sdk, health, sleep

    def test_clean_startup_with_immediate_controller_discovery(self):
        result, sdk, health, sleep = self.run_discovery_window([7], [None])

        self.assertEqual(result[3], 4)
        self.assertTrue(health.begun)
        self.assertEqual(health.window_checks, 1)
        self.assertEqual(sdk.inventory_calls, 1)
        sleep.assert_not_called()
        self.assertEqual(sdk.writes, [])

    def test_clean_startup_preserves_one_window_across_retries(self):
        result, sdk, health, sleep = self.run_discovery_window(
            [0, 4, 7], [None, None, None]
        )

        self.assertEqual(result[3], 4)
        self.assertTrue(health.begun)
        self.assertEqual(health.window_checks, 3)
        self.assertEqual(sdk.inventory_calls, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(sdk.writes, [])

    def test_first_retry_error_survives_later_successful_enumeration(self):
        sdk = SequencedSDK([0, 7])
        health = WindowHealth(
            [None, "i2c_designware.2: controller timed out during first retry"]
        )
        with (
            mock.patch.object(runtime, "OpenRGBSDK", return_value=sdk),
            mock.patch.object(
                runtime, "_lifecycle_identity", return_value=health.lifecycle
            ),
            mock.patch.object(runtime, "LinuxHealth", return_value=health),
            mock.patch.object(runtime.time, "sleep"),
            self.assertRaisesRegex(runtime.SafetyStop, "first retry"),
        ):
            runtime._hardware_health(self.arguments(), attempts=2, retry_delay=1.0)

        self.assertEqual(sdk.inventory_calls, 2)
        self.assertEqual(health.window_checks, 2)
        self.assertEqual(sdk.writes, [])

    def test_error_between_retries_fails_closed(self):
        sdk = SequencedSDK([0, 0, 7])
        health = WindowHealth(
            [None, "i2c_designware.0: controller timed out between retries", None]
        )
        with (
            mock.patch.object(runtime, "OpenRGBSDK", return_value=sdk),
            mock.patch.object(
                runtime, "_lifecycle_identity", return_value=health.lifecycle
            ),
            mock.patch.object(runtime, "LinuxHealth", return_value=health),
            mock.patch.object(runtime.time, "sleep"),
            self.assertRaisesRegex(runtime.SafetyStop, "between retries"),
        ):
            runtime._hardware_health(self.arguments(), attempts=3, retry_delay=1.0)

        self.assertEqual(sdk.inventory_calls, 2)
        self.assertEqual(health.window_checks, 2)
        self.assertEqual(sdk.writes, [])

    def test_error_on_final_successful_retry_fails_closed(self):
        sdk = SequencedSDK([0, 4, 7])
        health = WindowHealth(
            [None, None, "i2c_designware.2: controller timed out on final retry"]
        )
        with (
            mock.patch.object(runtime, "OpenRGBSDK", return_value=sdk),
            mock.patch.object(
                runtime, "_lifecycle_identity", return_value=health.lifecycle
            ),
            mock.patch.object(runtime, "LinuxHealth", return_value=health),
            mock.patch.object(runtime.time, "sleep"),
            self.assertRaisesRegex(runtime.SafetyStop, "final retry"),
        ):
            runtime._hardware_health(self.arguments(), attempts=3, retry_delay=1.0)

        self.assertEqual(sdk.inventory_calls, 3)
        self.assertEqual(health.window_checks, 3)
        self.assertEqual(sdk.writes, [])

    def test_complete_window_always_uses_original_journal_cursor(self):
        health = runtime.LinuxHealth(
            runtime.ServerIdentity(200, "server-start"),
            runtime.LifecycleIdentity(300, "lifecycle-start", "boot", 0),
        )
        with mock.patch.object(
            health,
            "_journal",
            side_effect=(
                "-- cursor: baseline\n",
                "-- cursor: after-first\n",
                "-- cursor: after-second\n",
            ),
        ) as journal:
            health.begin()
            health.no_kernel_errors_since_baseline()
            health.no_kernel_errors_since_baseline()

        self.assertEqual(health.kernel_baseline, "baseline")
        self.assertEqual(health.kernel_cursor, "baseline")
        self.assertEqual(
            journal.call_args_list[1:],
            [
                mock.call(["--after-cursor", "baseline", "--show-cursor"]),
                mock.call(["--after-cursor", "baseline", "--show-cursor"]),
            ],
        )

    def test_missing_or_incomplete_journal_access_fails_closed(self):
        health = runtime.LinuxHealth(
            runtime.ServerIdentity(200, "server-start"),
            runtime.LifecycleIdentity(300, "lifecycle-start", "boot", 0),
        )
        with (
            mock.patch.object(
                runtime.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, ["journalctl"]),
            ),
            mock.patch.object(runtime, "LinuxHealth", return_value=health),
            mock.patch.object(
                runtime, "_lifecycle_identity", return_value=health.lifecycle
            ),
            mock.patch.object(runtime, "OpenRGBSDK") as sdk_factory,
            self.assertRaisesRegex(
                runtime.SafetyStop, "current-boot kernel journal is unreadable"
            ),
        ):
            runtime._hardware_health(self.arguments(), attempts=3, retry_delay=1.0)
        sdk_factory.assert_not_called()

        incomplete_health = runtime.LinuxHealth(
            runtime.ServerIdentity(200, "server-start"),
            runtime.LifecycleIdentity(300, "lifecycle-start", "boot", 0),
        )
        with (
            mock.patch.object(
                incomplete_health,
                "_journal",
                return_value="journal output without a cursor\n",
            ),
            mock.patch.object(runtime, "LinuxHealth", return_value=incomplete_health),
            mock.patch.object(
                runtime,
                "_lifecycle_identity",
                return_value=incomplete_health.lifecycle,
            ),
            mock.patch.object(runtime, "OpenRGBSDK") as sdk_factory,
            self.assertRaisesRegex(runtime.SafetyStop, "did not return a cursor"),
        ):
            runtime._hardware_health(self.arguments(), attempts=3, retry_delay=1.0)
        sdk_factory.assert_not_called()

    def test_kernel_error_policy_includes_designware_without_unrelated_failures(self):
        relevant = (
            "i2c_designware i2c_designware.2: controller timed out",
            "i801_smbus 0000:00:1f.4: transaction failed",
            "spd5118 10-0050: probe error -6",
        )
        unrelated = (
            "NVRM: GPU error during modeset",
            "usb 1-2: device descriptor read failed",
            "EXT4-fs error: unrelated storage failure",
        )

        self.assertTrue(
            all(runtime.RELEVANT_KERNEL_ERROR.search(line) for line in relevant)
        )
        self.assertTrue(
            all(not runtime.RELEVANT_KERNEL_ERROR.search(line) for line in unrelated)
        )

    def test_startup_and_resume_refuse_restore_after_failed_gate(self):
        lifecycle = ROOT / "openrgb-lifecycle"
        for phase, invocation in (
            ("startup", "start_restore"),
            (
                "resume",
                (
                    "suspended=true; start_inhibitor() { :; }; "
                    "start_server() { start_restore; }; handle_sleep_signal false"
                ),
            ),
        ):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                marker = Path(directory, "rgb-write")
                apply = Path(directory, "apply-preset")
                apply.write_text(
                    f"#!/usr/bin/bash\nprintf '%s\\n' write >{marker!s}\n",
                    encoding="utf-8",
                )
                apply.chmod(0o700)
                script = (
                    f"source {lifecycle!s}; "
                    "process_start_time() { printf '%s' lifecycle-start; }; "
                    "server_pid=200; server_start_time=server-start; "
                    f"if {invocation}; then exit 99; fi"
                )
                result = subprocess.run(
                    ["/usr/bin/bash", "-c", script],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=os.environ
                    | {
                        "APPLY_PRESET": str(apply),
                        "OPENRGB_RESUME_DELAY": "0",
                        "RAM_TETRIS": "/usr/bin/false",
                    },
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(marker.exists())

    def test_pre_restore_hardware_gate_covers_spd_without_writes(self):
        sdk = FakeSDK("#8B0000")
        health = FakeHealth()
        output = io.StringIO()
        arguments = SimpleNamespace(
            lifecycle_pid=300,
            lifecycle_start="lifecycle-start",
            server_pid=200,
            server_start="server-start",
        )
        with (
            mock.patch.object(runtime, "OpenRGBSDK", return_value=sdk),
            mock.patch.object(
                runtime, "_lifecycle_identity", return_value=health.lifecycle
            ),
            mock.patch.object(runtime, "LinuxHealth", return_value=health),
            redirect_stdout(output),
        ):
            self.assertEqual(runtime._validate_hardware(arguments), 0)

        result = json.loads(output.getvalue())
        self.assertEqual(result["controller_count"], 7)
        self.assertEqual(result["dimm_count"], 4)
        self.assertEqual(len(result["temperatures_mc"]), 4)
        self.assertEqual(sdk.writes, [])

    def test_pre_restore_hardware_gate_refuses_unreadable_spd(self):
        sdk = FakeSDK("#8B0000")
        health = FakeHealth(fail_spd=True)
        arguments = SimpleNamespace(
            lifecycle_pid=300,
            lifecycle_start="lifecycle-start",
            server_pid=200,
            server_start="server-start",
        )
        with (
            mock.patch.object(runtime, "OpenRGBSDK", return_value=sdk),
            mock.patch.object(
                runtime, "_lifecycle_identity", return_value=health.lifecycle
            ),
            mock.patch.object(runtime, "LinuxHealth", return_value=health),
            mock.patch.object(runtime.time, "sleep"),
            self.assertRaisesRegex(runtime.SafetyStop, "temperature"),
        ):
            runtime._validate_hardware(arguments)
        self.assertEqual(sdk.writes, [])

    @mock.patch.object(runtime, "_selected_preset", return_value="horde-red")
    def test_read_only_health_gate_covers_all_four_dimms_without_writes(self, _preset):
        sdk = FakeSDK("#8B0000")
        health = FakeHealth()
        output = io.StringIO()
        arguments = SimpleNamespace(
            lifecycle_pid=300,
            lifecycle_start="lifecycle-start",
            server_pid=200,
            server_start="server-start",
        )
        with (
            mock.patch.object(runtime, "OpenRGBSDK", return_value=sdk),
            mock.patch.object(
                runtime, "_lifecycle_identity", return_value=health.lifecycle
            ),
            mock.patch.object(runtime, "LinuxHealth", return_value=health),
            mock.patch.object(runtime, "EffectsContract", return_value=FakeEffects()),
            redirect_stdout(output),
        ):
            self.assertEqual(runtime._validate_health(arguments), 0)

        result = json.loads(output.getvalue())
        self.assertEqual(result["controller_count"], 7)
        self.assertEqual(result["dimm_count"], 4)
        self.assertEqual(len(result["temperatures_mc"]), 4)
        self.assertEqual(result["preset"], "horde-red")
        self.assertEqual(sdk.writes, [])


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
        self.assertIn('stop_tetris "${tetris_reason}"', lifecycle)
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
            cleanup.index('stop_tetris "${tetris_reason}"'),
            cleanup.index("detach_server"),
        )
        stop = lifecycle.split("stop_tetris() {", 1)[1].split(
            "reconcile_tetris() {", 1
        )[0]
        self.assertLess(
            stop.index('"${FLOCK_BIN}" --wait "${lock_wait}" "${stop_lock_fd}"'),
            stop.index("TETRIS_STOP_FILE"),
        )
        self.assertLess(
            stop.index("TETRIS_STOP_FILE"),
            stop.index('wait_for_process_exit "${tetris_pid}"'),
        )
        for field in (
            "lifecycle_pid",
            "lifecycle_start",
            "server_pid",
            "server_start",
        ):
            self.assertIn(field, stop)
        self.assertIn("self.health.verify_processes()", runner)
        self.assertIn("OpenRGB SDK process identity changed", runner)
        self.assertEqual(runtime.LIFECYCLE_ARGV[-1], "--service")
        restore = lifecycle.split("start_restore() {", 1)[1].split(
            "start_server() {", 1
        )[0]
        self.assertLess(
            restore.index('"${RAM_TETRIS}" validate-hardware'),
            restore.index('"${APPLY_PRESET}" --restore'),
        )
        self.assertIn('"${SETPRIV_BIN}" --pdeathsig TERM', restore)
        self.assertIn("--server-start", restore)
        self.assertIn("--lifecycle-start", restore)
        self.assertNotIn("for attempt in {1..15}", restore)
        self.assertIn("HARDWARE_GATE_ATTEMPTS = 15", runner)
        self.assertIn("no_kernel_errors_since_baseline", runner)
        self.assertIn("refusing preset write", restore)
        reconcile = lifecycle.split("reconcile_tetris() {", 1)[1].split(
            "expected_server_command() {", 1
        )[0]
        self.assertIn("! tetris_local_stop_requested", reconcile)
        self.assertNotIn('"state": "running"', reconcile)

    def test_unexpected_sdk_or_inhibitor_loss_has_no_recovery_branch(self):
        lifecycle = (ROOT / "openrgb-lifecycle").read_text()
        loop = lifecycle.split("while true; do", 1)[1]
        self.assertIn("refusing automatic recovery", loop)
        self.assertIn("refusing automatic replacement", loop)
        self.assertNotIn("exited unexpectedly; restarting", loop)
        self.assertNotIn('"${SLEEP_BIN}" 2\n      start_server', loop)
        self.assertIn(
            '! is_server_listener "${server_pid}" "${server_start_time}"', loop
        )

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
