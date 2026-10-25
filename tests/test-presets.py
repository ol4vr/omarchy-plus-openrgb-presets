"""Focused source-only validation for OpenRGB Presets 0.4.26."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "apply-preset"
PANEL = ROOT / "Panel.qml"
INSTALLER = ROOT / "install-effects-plugin"
PROFILES = ROOT / "effects-profiles"

PROFILE_HASHES = {
    "hugin-rain": "5c1c6086f4bd23e32093afe0412b079fe15b53c923faa2a54acfc93d68c9c361",
    "hugin-rainbow-comet": "efe1c16277873e91b04a75930096bbd9958b8c29ec241ac00e76b54ed923ffae",
    "hugin-rainbow-wave": "8be31745f42fb13f354f7025f2dbc84b20af4549f4678a4c7808ed7e3a61699c",
    "hugin-sunrise-blue-black": "117d4e597c6fb328c99d82dff6a15ae876d1e7cc0875ac6737999dc1123faaa8",
    "hugin-sunrise-blue-red": "c10e289c2e0966bc0f79d43dd105c855a754693a8efdeb5c69002ab2e563604c",
    "hugin-sunrise-orange-black": "02db5c13ab37021f664908e792914d5d731c783559a2d3f691e789d19f98be02",
    "hugin-sunrise-red-black": "9e22534f40e48bdaf534d796f3d82908acaa6cb5dd83e53ba4c9fec15cc4c73f",
}
NEW_PROFILES = {
    "hugin-sunrise-orange-black": {
        "human_rgb": ["#FF4400", "#E83B00", "#C92B00", "#501000"],
        "packed_rgbcolor": [17663, 15336, 11209, 4176],
        "v044_packed_rgbcolor": [17663, 15336, 11209, 15336],
        "sha256": "02db5c13ab37021f664908e792914d5d731c783559a2d3f691e789d19f98be02",
    },
    "hugin-sunrise-blue-black": {
        "human_rgb": ["#0033AA", "#002788", "#001A66", "#000B22"],
        "packed_rgbcolor": [11154176, 8922880, 6691328, 2231040],
        "v044_packed_rgbcolor": [11154176, 8922880, 6691328, 8922880],
        "sha256": "117d4e597c6fb328c99d82dff6a15ae876d1e7cc0875ac6737999dc1123faaa8",
    },
    "hugin-sunrise-red-black": {
        "human_rgb": ["#8B0000", "#680000", "#4A0000", "#180000"],
        "packed_rgbcolor": [139, 104, 74, 24],
        "v044_packed_rgbcolor": [139, 104, 74, 104],
        "sha256": "9e22534f40e48bdaf534d796f3d82908acaa6cb5dd83e53ba4c9fec15cc4c73f",
    },
}
PANEL_INDICATORS = {
    "deep-blue": (
        "Static Blue",
        "STATIC",
        "STATIC COLOR",
        "DEEP BLUE",
        "#7AA2F7",
        ["#000B22"],
    ),
    "matte-black-orange": (
        "Matte Black Orange",
        "EFFECTS",
        "SUNRISE",
        "ORANGE · RED · BURNT",
        "#FF4400",
        ["#FF4400", "#E83B00", "#C92B00"],
    ),
    "horde-red": (
        "For the Horde!",
        "EFFECTS",
        "SUNRISE",
        "RED · DEEP · DARK",
        "#F7768E",
        ["#8B0000", "#680000", "#4A0000"],
    ),
    "alliance-blue": (
        "For the Alliance!",
        "EFFECTS",
        "SUNRISE",
        "BLUE · MID · DARK",
        "#7AA2F7",
        ["#0033AA", "#002788", "#001A66"],
    ),
}
DISPLAY_LABELS = {
    "deep-red": "Static Red",
    "deep-blue": "Static Blue",
    "bright-white": "Static White",
    "animated-rainbow": "Animated Rainbow",
    "neon-rain": "Neon Rain",
    "aurora-comet": "Aurora Comet",
    "spectrum-wave": "Spectrum Wave",
    "electric-sunrise": "Electric Sunrise",
    "matte-black-orange": "Matte Black Orange",
    "black": "Black (Turn Off RGB)",
    "horde-red": "For the Horde!",
    "alliance-blue": "For the Alliance!",
}
DISPLAY_MODES = {
    "deep-red": "STATIC COLOR",
    "deep-blue": "STATIC COLOR",
    "bright-white": "STATIC COLOR",
    "animated-rainbow": "RAINBOW",
    "neon-rain": "RAIN",
    "aurora-comet": "COMET",
    "spectrum-wave": "RAINBOW WAVE",
    "electric-sunrise": "SUNRISE",
    "matte-black-orange": "SUNRISE",
    "black": "LIGHTS OFF",
    "horde-red": "SUNRISE",
    "alliance-blue": "SUNRISE",
}
VISIBLE_ORDER = [
    "deep-red",
    "deep-blue",
    "bright-white",
    "animated-rainbow",
    "neon-rain",
    "aurora-comet",
    "spectrum-wave",
    "electric-sunrise",
    "matte-black-orange",
    "black",
    "horde-red",
    "alliance-blue",
]
HELPER_ORDER = [
    "deep-red",
    "bright-white",
    "deep-blue",
    "animated-rainbow",
    "neon-rain",
    "aurora-comet",
    "spectrum-wave",
    "matte-black-orange",
    "electric-sunrise",
    "horde-red",
    "alliance-blue",
    "black",
]
RAM_DEVICE = "Corsair Dominator Platinum RGB DDR5"
GPU_DEVICE = "ASUS TUF GeForce RTX 4090 Gaming OG OC"
ST100_DEVICE = "Corsair ST100 RGB"
MAINBOARD_DEVICE = "ASUS ROG STRIX Z790-F GAMING WIFI"
NON_RAM_ZONES = [
    (GPU_DEVICE, 0),
    (ST100_DEVICE, 0),
    (ST100_DEVICE, 1),
    (MAINBOARD_DEVICE, 0),
    (MAINBOARD_DEVICE, 1),
    (MAINBOARD_DEVICE, 2),
]
DDR5_STATIC_PAIR_PATTERNS = {
    "deep-red": ("8B0000",) * 6,
    "deep-blue": ("000B22",) * 6,
    "bright-white": ("FFFFFF",) * 6,
    "animated-rainbow": (
        "11FF00",
        "8A2BE2",
        "FFD400",
        "FF0040",
        "8A2BE2",
        "11FF00",
    ),
    "neon-rain": (
        "5500FF",
        "11FF00",
        "00FF8C",
        "FF00F6",
        "FFD400",
        "5500FF",
    ),
    "aurora-comet": (
        "95FF00",
        "00D4FF",
        "8A2BE2",
        "8A2BE2",
        "00D4FF",
        "95FF00",
    ),
    "spectrum-wave": (
        "11FF00",
        "8A2BE2",
        "FFD400",
        "FF0040",
        "8A2BE2",
        "11FF00",
    ),
    "electric-sunrise": (
        "FF0040",
        "FF0051",
        "3C00FF",
        "0044FF",
        "FF0051",
        "FF0040",
    ),
    "matte-black-orange": (
        "FF4400",
        "E83B00",
        "C92B00",
        "501000",
        "E83B00",
        "FF4400",
    ),
    "black": ("000000",) * 6,
    "horde-red": (
        "8B0000",
        "680000",
        "4A0000",
        "180000",
        "680000",
        "8B0000",
    ),
    "alliance-blue": (
        "0033AA",
        "002788",
        "001A66",
        "000B22",
        "002788",
        "0033AA",
    ),
}
EFFECT_PROFILES = {
    "neon-rain": ("hugin-rain", "Rain"),
    "aurora-comet": ("hugin-rainbow-comet", "Comet"),
    "spectrum-wave": ("hugin-rainbow-wave", "Rainbow Wave"),
    "electric-sunrise": ("hugin-sunrise-blue-red", "Sunrise"),
    "matte-black-orange": ("hugin-sunrise-orange-black", "Sunrise"),
    "horde-red": ("hugin-sunrise-red-black", "Sunrise"),
    "alliance-blue": ("hugin-sunrise-blue-black", "Sunrise"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_profile(name: str) -> dict[str, object]:
    return json.loads((PROFILES / name).read_text(encoding="utf-8"))


def pack_rgbcolor(human_rgb: str) -> int:
    """Convert human #RRGGBB notation to OpenRGB's packed 0x00BBGGRR."""
    red = int(human_rgb[1:3], 16)
    green = int(human_rgb[3:5], 16)
    blue = int(human_rgb[5:7], 16)
    return red | (green << 8) | (blue << 16)


def unpack_rgbcolor(packed_rgbcolor: int) -> str:
    """Decode OpenRGB's packed 0x00BBGGRR integer to human #RRGGBB."""
    red = packed_rgbcolor & 0xFF
    green = (packed_rgbcolor >> 8) & 0xFF
    blue = (packed_rgbcolor >> 16) & 0xFF
    return f"#{red:02X}{green:02X}{blue:02X}"


class PresetTests(unittest.TestCase):
    def test_effects_profiles_exclude_ddr5_and_preserve_non_ram_zones(self) -> None:
        for name, expected_hash in PROFILE_HASHES.items():
            profile = load_profile(name)
            self.assertEqual(len(profile["Effects"]), 1, name)
            effect = profile["Effects"][0]
            self.assertEqual(effect["FPS"], 60, name)
            zones = effect["ControllerZones"]
            self.assertEqual(
                [(zone["name"], zone["zone_idx"]) for zone in zones],
                NON_RAM_ZONES,
                name,
            )
            self.assertNotIn(RAM_DEVICE, [zone["name"] for zone in zones], name)
            self.assertEqual(sha256(PROFILES / name), expected_hash, name)

    def test_human_rgb_is_packed_as_openrgb_rgbcolor(self) -> None:
        for name, specification in NEW_PROFILES.items():
            human_rgb = specification["human_rgb"]
            packed_rgbcolor = load_profile(name)["Effects"][0]["UserColors"]
            self.assertEqual(packed_rgbcolor, specification["packed_rgbcolor"], name)
            self.assertEqual(
                [pack_rgbcolor(color) for color in human_rgb],
                packed_rgbcolor,
                name,
            )
            self.assertEqual(
                [unpack_rgbcolor(color) for color in packed_rgbcolor],
                human_rgb,
                name,
            )

    def test_new_profiles_clone_electric_sunrise_except_for_four_colors(self) -> None:
        original = load_profile("hugin-sunrise-blue-red")
        original_effect = original["Effects"][0]
        self.assertEqual(
            original_effect["UserColors"], [4194559, 5308671, 16711740, 16729088]
        )

        for name, specification in NEW_PROFILES.items():
            packed_colors = specification["packed_rgbcolor"]
            profile = load_profile(name)
            expected = copy.deepcopy(original)
            expected["Effects"][0]["UserColors"] = packed_colors
            self.assertEqual(profile, expected, name)
            self.assertEqual(profile["Effects"][0]["UserColors"], packed_colors, name)
            self.assertEqual(len(profile["Effects"][0]["UserColors"]), 4, name)
            self.assertNotIn(0, profile["Effects"][0]["UserColors"], name)
            previous_colors = specification["v044_packed_rgbcolor"]
            self.assertEqual(packed_colors[:3], previous_colors[:3], name)
            self.assertNotEqual(packed_colors[3], previous_colors[3], name)
            self.assertEqual(
                profile["Effects"][0]["ControllerZones"],
                original_effect["ControllerZones"],
                name,
            )
            self.assertEqual(len(profile["Effects"][0]["ControllerZones"]), 6, name)
            self.assertEqual(profile["Effects"][0]["EffectClassName"], "Sunrise", name)
            self.assertEqual(
                profile["Effects"][0]["CustomSettings"],
                original_effect["CustomSettings"],
                name,
            )
            self.assertEqual(
                profile["Effects"][0]["Speed"], original_effect["Speed"], name
            )
            self.assertEqual(profile["Effects"][0]["FPS"], original_effect["FPS"], name)
            self.assertEqual(sha256(PROFILES / name), specification["sha256"], name)

    def test_manifest_and_panel_order(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.4.32")
        self.assertEqual(manifest["kinds"], ["bar-widget"])
        self.assertNotIn("service", manifest["entryPoints"])
        self.assertFalse((ROOT / "Service.qml").exists())

        unit = (ROOT / "systemd/omarchy-plus-openrgb-presets.service").read_text()
        self.assertIn("Type=notify", unit)
        self.assertIn("NotifyAccess=all", unit)
        self.assertIn("ExitType=cgroup", unit)
        self.assertIn("KillMode=mixed", unit)
        self.assertIn("Restart=no", unit)
        self.assertIn("TimeoutStartSec=120", unit)
        self.assertIn("TimeoutStopSec=20", unit)
        self.assertIn("PartOf=graphical-session.target", unit)
        self.assertIn("ExecStopPost=", unit)
        self.assertNotIn("NotifyAccess=main", unit)

        lifecycle = (ROOT / "openrgb-lifecycle").read_text()
        self.assertIn("readonly SHUTDOWN_BUDGET_SECONDS=15", lifecycle)
        self.assertIn("begin_shutdown_deadline", lifecycle)
        self.assertIn("wait_for_process_exit", lifecycle)

        panel = PANEL.read_text(encoding="utf-8")
        library = panel.split("readonly property var presets: [", 1)[1].split(
            "readonly property var activePresetData:", 1
        )[0]
        self.assertEqual(
            re.findall(r'^\s+id: "([a-z0-9-]+)",$', library, re.MULTILINE),
            VISIBLE_ORDER,
        )
        self.assertIn("columns: 2", panel)
        self.assertIn("function moveSelection(dx, dy)", panel)
        self.assertIn("var rows = Math.ceil(presets.length / columns)", panel)
        self.assertIn("while (nextIndex >= presets.length)", panel)
        self.assertIn("root.moveSelection(dx, dy)", panel)
        self.assertIn('id: "bright-white"', panel)
        self.assertNotIn("brightWhitePreset", panel)

        for preset, (
            label,
            kind,
            mode,
            detail,
            accent,
            swatches,
        ) in PANEL_INDICATORS.items():
            block = library.split(f'id: "{preset}"', 1)[1].split("\n    }", 1)[0]
            self.assertIn(f'label: "{label}"', block, preset)
            self.assertIn(f'kind: "{kind}"', block, preset)
            self.assertIn(f'mode: "{mode}"', block, preset)
            self.assertIn(f'detail: "{detail}"', block, preset)
            self.assertIn(f'accent: "{accent}"', block, preset)
            self.assertIn(f"swatches: {json.dumps(swatches)}", block, preset)

        for preset, label in DISPLAY_LABELS.items():
            block = library.split(f'id: "{preset}"', 1)[1].split("\n    }", 1)[0]
            self.assertIn(f'label: "{label}"', block, preset)
            self.assertIn(f'mode: "{DISPLAY_MODES[preset]}"', block, preset)
        self.assertNotIn('id: "static-red"', panel)
        self.assertNotIn('id: "static-blue"', panel)
        self.assertNotIn('id: "static-white"', panel)

        self.assertIn("height: Style.space(80)", panel)
        self.assertIn("height: Style.space(60)", panel)
        self.assertIn("rowSpacing: Style.space(7)", panel)
        self.assertIn('text: "󰍛"', panel)
        self.assertIn('? "Lighting animations stopped"', panel)
        self.assertIn("id: compactErrorCode", panel)
        self.assertIn("text: root.failureCode", panel)
        self.assertIn('? "Recovery needed"', panel)
        self.assertIn('? "Recovery blocked"', panel)
        self.assertIn(': "Manual review required"', panel)
        self.assertIn("parent.width - compactErrorCode.implicitWidth", panel)
        compact_row = panel.split("id: tetrisToggle", 1)[1].split(
            "id: diagnosticDetails", 1
        )[0]
        self.assertNotIn("failureDescription", compact_row)
        self.assertIn('? "Active" : "Static lighting"', panel)
        self.assertIn('text: root.recoveryAttemptActive ? "Working" : "Recover"', panel)
        self.assertIn('text: "󰆏  Copy diagnostics"', panel)
        self.assertIn('"Original reason: " + root.failureReason', panel)
        self.assertIn('"Latest action: " + root.recoveryFeedback', panel)
        self.assertIn("root.diagnosticsExpanded = !root.diagnosticsExpanded", panel)
        self.assertIn("onClicked: root.beginRecovery()", panel)
        self.assertIn('root.recoveryAction = "recover"', panel)
        self.assertIn("recoveryDispatchTimer.restart()", panel)
        self.assertIn(
            "if (!lightingFailure || recoveryProc.running || recoveryAttemptActive)",
            panel,
        )
        self.assertNotIn("recoveryConfirmationPending", panel)
        self.assertNotIn("confirmationTimer", panel)
        self.assertNotIn("function confirmRecovery", panel)
        self.assertNotIn("function cancelRecovery", panel)
        self.assertNotIn('text: "Confirm"', panel)
        self.assertNotIn("interval: 15000", panel)
        self.assertIn(
            "anchors.right: tetrisToggle.failed ? recoveryControls.left : toggleTrack.left",
            panel,
        )
        self.assertIn("onActivateRequested: root.applySelectedPreset()", panel)
        self.assertNotIn("onActivateRequested: root.beginRecovery()", panel)
        self.assertIn("root.activePresetData.mode", panel)
        self.assertGreaterEqual(panel.count("fontSizeMode: Text.HorizontalFit"), 2)
        self.assertIn("maximumLineCount: 1", panel)
        self.assertNotIn("text: presetCard.modelData.detail", panel)

        def move(index: int, dx: int, dy: int) -> int:
            if dy == 0:
                return (index + dx + len(VISIBLE_ORDER)) % len(VISIBLE_ORDER)
            columns = 2
            rows = (len(VISIBLE_ORDER) + columns - 1) // columns
            column = index % columns
            row = index // columns
            next_row = (row + dy + rows) % rows
            next_index = next_row * columns + column
            while next_index >= len(VISIBLE_ORDER):
                next_row = (next_row + dy + rows) % rows
                next_index = next_row * columns + column
            return next_index

        self.assertEqual(move(0, 0, -1), 10)
        self.assertEqual(move(1, 0, -1), 11)
        self.assertEqual(move(10, 0, 1), 0)
        self.assertEqual(move(11, 0, 1), 1)
        self.assertEqual(move(11, 1, 0), 0)

    def test_helper_lists_routes_and_restores_all_presets(self) -> None:
        listed = subprocess.run(
            [str(APPLY), "--list"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        self.assertEqual(listed, HELPER_ORDER)

        with tempfile.TemporaryDirectory() as state_home:
            environment = os.environ | {"XDG_STATE_HOME": state_home}
            state_dir = Path(state_home) / "omarchy-plus/openrgb-presets"
            state_dir.mkdir(parents=True)
            for preset in (
                "deep-blue",
                "matte-black-orange",
                "horde-red",
                "alliance-blue",
            ):
                (state_dir / "active-preset").write_text(
                    preset + "\n", encoding="utf-8"
                )
                current = subprocess.run(
                    [str(APPLY), "--current"],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                ).stdout.strip()
                self.assertEqual(current, preset)

    def test_every_preset_applies_one_exact_static_ddr5_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as state_home:
            environment = os.environ | {"XDG_STATE_HOME": state_home}
            for preset, pair_pattern in DDR5_STATIC_PAIR_PATTERNS.items():
                expected_colors = ",".join(
                    color for color in pair_pattern for _ in range(2)
                )
                output = subprocess.run(
                    [str(APPLY), "--dry-run", preset],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                ).stdout
                self.assertIn(f"Applied: {DISPLAY_LABELS[preset]}", output, preset)
                commands = [
                    shlex.split(line.removeprefix("DRY RUN:"))
                    for line in output.splitlines()
                    if line.startswith("DRY RUN:")
                ]
                openrgb_commands = [
                    command for command in commands if command[0] == "/usr/bin/openrgb"
                ]
                ram_segments = []
                for command in openrgb_commands:
                    device_indexes = [
                        index
                        for index, value in enumerate(command)
                        if value == "--device"
                    ]
                    for position, index in enumerate(device_indexes):
                        if command[index + 1] != RAM_DEVICE:
                            continue
                        stop = (
                            device_indexes[position + 1]
                            if position + 1 < len(device_indexes)
                            else len(command)
                        )
                        ram_segments.append(command[index:stop])

                self.assertEqual(len(ram_segments), 1, preset)
                self.assertEqual(
                    ram_segments[0],
                    [
                        "--device",
                        RAM_DEVICE,
                        "--mode",
                        "direct",
                        "--color",
                        expected_colors,
                    ],
                    preset,
                )

                if preset in EFFECT_PROFILES:
                    profile, effect = EFFECT_PROFILES[preset]
                    load_commands = [
                        command
                        for command in commands
                        if command[0] == str(ROOT / "effects-sdk")
                        and "load-profile" in command
                    ]
                    self.assertEqual(
                        load_commands,
                        [[str(ROOT / "effects-sdk"), "load-profile", profile, effect]],
                        preset,
                    )
                    stop_commands = [
                        command
                        for command in commands
                        if command == [str(ROOT / "effects-sdk"), "stop-all"]
                    ]
                    self.assertEqual(len(stop_commands), 1, preset)
                    self.assertLess(
                        commands.index(stop_commands[0]),
                        commands.index(load_commands[0]),
                        preset,
                    )
                    self.assertLess(
                        commands.index(load_commands[0]),
                        commands.index(openrgb_commands[0]),
                        preset,
                    )
                    self.assertEqual(
                        [
                            command[index + 1]
                            for command in openrgb_commands
                            for index, value in enumerate(command)
                            if value == "--device"
                        ],
                        [RAM_DEVICE],
                        preset,
                    )
                else:
                    devices = [
                        command[index + 1]
                        for command in openrgb_commands
                        for index, value in enumerate(command)
                        if value == "--device"
                    ]
                    self.assertEqual(
                        devices,
                        [
                            RAM_DEVICE,
                            GPU_DEVICE,
                            ST100_DEVICE,
                            ST100_DEVICE,
                            MAINBOARD_DEVICE,
                        ],
                        preset,
                    )

    def test_installer_registers_all_profiles_with_exact_hashes(self) -> None:
        installer = INSTALLER.read_text(encoding="utf-8")
        names_block = installer.split("readonly -a PROFILE_NAMES=(", 1)[1].split(
            "\n)", 1
        )[0]
        names = re.findall(r"^\s+(hugin-[a-z0-9-]+)$", names_block, re.MULTILINE)
        expected_names = [
            "hugin-rain",
            "hugin-rainbow-comet",
            "hugin-rainbow-wave",
            "hugin-sunrise-blue-black",
            "hugin-sunrise-blue-red",
            "hugin-sunrise-orange-black",
            "hugin-sunrise-red-black",
        ]
        self.assertEqual(names, expected_names)

        for name, expected_hash in PROFILE_HASHES.items():
            self.assertIn(f'[{name}]="{expected_hash}"', installer)


if __name__ == "__main__":
    unittest.main()
