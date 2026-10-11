#!/usr/bin/env python3
"""Focused source-only validation for OpenRGB Presets 0.4.6."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "apply-preset"
PANEL = ROOT / "Panel.qml"
INSTALLER = ROOT / "install-effects-plugin"
PROFILES = ROOT / "effects-profiles"

ORIGINAL_PROFILE_HASHES = {
    "hugin-rain": "d730f06b7c90d7051ac94e48de674829ed87bbac107a43981c8f84b93d955ebe",
    "hugin-rainbow-comet": "4f3b61a63086f5d98c07354d912cb82c987dde178c28ad95a54010e807f3f84f",
    "hugin-rainbow-wave": "fe977da32d9f8dbb9babd4d8dfc146b7d586aa00d477a56a635118a7b5c64cc9",
    "hugin-sunrise-blue-red": "dc42def0e003f7e24993584d4db7f50f021922a0574b6b722ffa16dfa931cb06",
}
NEW_PROFILES = {
    "hugin-sunrise-orange-black": {
        "human_rgb": ["#FF4400", "#E83B00", "#C92B00", "#501000"],
        "packed_rgbcolor": [17663, 15336, 11209, 4176],
        "v044_packed_rgbcolor": [17663, 15336, 11209, 15336],
        "sha256": "7c568e6d66b1d0bec7e5d542cc7c2ed90add36a73b7596a6c33ccbacd319b41f",
    },
    "hugin-sunrise-blue-black": {
        "human_rgb": ["#0033AA", "#002788", "#001A66", "#000B22"],
        "packed_rgbcolor": [11154176, 8922880, 6691328, 2231040],
        "v044_packed_rgbcolor": [11154176, 8922880, 6691328, 8922880],
        "sha256": "0498bcb01a53c37a4d64b5ea33e9a7ffbe206f30584d78464aa1cbbd2ee36780",
    },
    "hugin-sunrise-red-black": {
        "human_rgb": ["#8B0000", "#680000", "#4A0000", "#180000"],
        "packed_rgbcolor": [139, 104, 74, 24],
        "v044_packed_rgbcolor": [139, 104, 74, 104],
        "sha256": "b1dd58fe5810389a353016eeacc1a36016908f5377ec9860df83d82b2fe77194",
    },
}
PANEL_INDICATORS = {
    "deep-blue": ("STATIC", "DEEP BLUE", "#000B22", ["#000B22"]),
    "matte-black-orange": (
        "EFFECTS",
        "ORANGE · RED · BURNT",
        "#FF4400",
        ["#FF4400", "#E83B00", "#C92B00"],
    ),
    "horde-red": (
        "EFFECTS",
        "RED · DEEP · DARK",
        "#8B0000",
        ["#8B0000", "#680000", "#4A0000"],
    ),
    "alliance-blue": (
        "EFFECTS",
        "BLUE · MID · DARK",
        "#0033AA",
        ["#0033AA", "#002788", "#001A66"],
    ),
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
    def test_original_effects_profiles_are_byte_identical(self) -> None:
        for name, expected_hash in ORIGINAL_PROFILE_HASHES.items():
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
        self.assertEqual(original_effect["UserColors"], [4194559, 5308671, 16711740, 16729088])

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
            self.assertEqual(profile["Effects"][0]["ControllerZones"], original_effect["ControllerZones"], name)
            self.assertEqual(len(profile["Effects"][0]["ControllerZones"]), 10, name)
            self.assertEqual(profile["Effects"][0]["EffectClassName"], "Sunrise", name)
            self.assertEqual(profile["Effects"][0]["CustomSettings"], original_effect["CustomSettings"], name)
            self.assertEqual(profile["Effects"][0]["Speed"], original_effect["Speed"], name)
            self.assertEqual(profile["Effects"][0]["FPS"], original_effect["FPS"], name)
            self.assertEqual(sha256(PROFILES / name), specification["sha256"], name)

    def test_manifest_and_panel_order(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.4.6")

        panel = PANEL.read_text(encoding="utf-8")
        library = panel.split(
            "readonly property var presets: [", 1
        )[1].split("readonly property var activePresetData:", 1)[0]
        self.assertEqual(re.findall(r'^\s+id: "([a-z0-9-]+)",$', library, re.MULTILINE), VISIBLE_ORDER)
        self.assertIn('columns: 2', panel)
        self.assertIn("function moveSelection(dx, dy)", panel)
        self.assertIn("var rows = Math.ceil(presets.length / columns)", panel)
        self.assertIn("while (nextIndex >= presets.length)", panel)
        self.assertIn("root.moveSelection(dx, dy)", panel)
        self.assertIn('id: "bright-white"', panel)
        self.assertNotIn("brightWhitePreset", panel)

        for preset, (kind, detail, accent, swatches) in PANEL_INDICATORS.items():
            block = library.split(f'id: "{preset}"', 1)[1].split("\n    }", 1)[0]
            self.assertIn(f'kind: "{kind}"', block, preset)
            self.assertIn(f'detail: "{detail}"', block, preset)
            self.assertIn(f'accent: "{accent}"', block, preset)
            self.assertIn(f"swatches: {json.dumps(swatches)}", block, preset)

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
                (state_dir / "active-preset").write_text(preset + "\n", encoding="utf-8")
                current = subprocess.run(
                    [str(APPLY), "--current"],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                ).stdout.strip()
                self.assertEqual(current, preset)

    def test_new_preset_dry_runs_have_exact_commands(self) -> None:
        expected_profiles = {
            "matte-black-orange": "hugin-sunrise-orange-black",
            "horde-red": "hugin-sunrise-red-black",
            "alliance-blue": "hugin-sunrise-blue-black",
        }
        with tempfile.TemporaryDirectory() as state_home:
            environment = os.environ | {"XDG_STATE_HOME": state_home}
            deep_blue = subprocess.run(
                [str(APPLY), "--dry-run", "deep-blue"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            ).stdout
            self.assertIn("stop-all", deep_blue)
            self.assertEqual(set(re.findall(r"--color ([0-9A-F,]+)", deep_blue)), {"000B22"})
            self.assertNotIn("000000", deep_blue)
            command = shlex.split(deep_blue.split("DRY RUN: ", 2)[2].splitlines()[0])
            self.assertEqual(
                [command[index + 1] for index, value in enumerate(command) if value == "--device"],
                [
                    "Corsair Dominator Platinum RGB DDR5",
                    "ASUS TUF GeForce RTX 4090 Gaming OG OC",
                    "Corsair ST100 RGB",
                    "Corsair ST100 RGB",
                    "ASUS ROG STRIX Z790-F GAMING WIFI",
                ],
            )
            self.assertEqual(
                [command[index + 1] for index, value in enumerate(command) if value == "--zone"],
                ["0", "1"],
            )

            for preset, profile in expected_profiles.items():
                output = subprocess.run(
                    [str(APPLY), "--dry-run", preset],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                ).stdout
                self.assertIn(f"load-profile {profile} Sunrise", output)
                self.assertNotIn("stop-all", output)

            electric_sunrise = subprocess.run(
                [str(APPLY), "--dry-run", "electric-sunrise"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            ).stdout
            self.assertIn(
                "load-profile hugin-sunrise-blue-red Sunrise",
                electric_sunrise,
            )

            black = subprocess.run(
                [str(APPLY), "--dry-run", "black"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            ).stdout
            self.assertIn("stop-all", black)
            self.assertEqual(
                set(re.findall(r"--color ([0-9A-F,]+)", black)),
                {"000000"},
            )

    def test_installer_registers_all_profiles_with_exact_hashes(self) -> None:
        installer = INSTALLER.read_text(encoding="utf-8")
        names_block = installer.split(
            "readonly -a PROFILE_NAMES=(", 1
        )[1].split("\n)", 1)[0]
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

        for name, expected_hash in ORIGINAL_PROFILE_HASHES.items():
            self.assertIn(f'[{name}]="{expected_hash}"', installer)
        for name, specification in NEW_PROFILES.items():
            self.assertIn(f'[{name}]="{specification["sha256"]}"', installer)


if __name__ == "__main__":
    unittest.main()
