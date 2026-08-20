# OpenRGB Presets

A Hugin-specific Omarchy Quattro bar plugin for choosing reviewed OpenRGB lighting presets.

## Presets

- **Tokyo Night Purple** — the calibrated Hugin baseline.
- **Deep Red** — a dark static red.
- **Bright White** — a clean static white with ST100 logo compensation.
- **Animated Rainbow** — hardware animation on the RAM, GPU, and ASUS Aura controller, plus a static rainbow on the ST100 base.

## Hardware contract

The helper targets controllers by their detected names, never by enumeration index:

- Four Corsair Dominator Platinum RGB DDR5 modules
- ASUS TUF GeForce RTX 4090 Gaming OG OC
- Corsair ST100 RGB
- ASUS ROG STRIX Z790-F GAMING WIFI

The user OpenRGB configuration must retain these addressable zone sizes:

- Aura Addressable 1: 30 LEDs — radiator fans, CPU block, and Phanteks NV5 strip
- Aura Addressable 2: 20 LEDs — five ASUS Prime MR120 ARGB case fans

## Privilege boundary

The plugin runs `/usr/bin/openrgb` as the graphical-session user. It never invokes `sudo`, `pkexec`, a shell, USB reset, OpenRGB I2C tools, firmware operations, or arbitrary user-provided commands.

The `apply-preset` helper accepts only four fixed preset identifiers. It serializes changes with a private state-directory lock and records OpenRGB's latest diagnostic output at:

```text
~/.local/state/omarchy-plus/openrgb-presets/last-openrgb.log
```

## Validate

```bash
PLUGIN_DIR="$PWD"
omarchy plugin validate "$PLUGIN_DIR"
qmllint -I "$OMARCHY_PATH/shell" \
  "$PLUGIN_DIR/BarWidget.qml" "$PLUGIN_DIR/Panel.qml"
/usr/bin/bash -n "$PLUGIN_DIR/apply-preset"
"$PLUGIN_DIR/apply-preset" --dry-run tokyo-night-purple
```

## Install

Install through Omarchy after the source has been reviewed and committed to its owned repository:

```bash
omarchy plugin add https://github.com/ol4vr/omarchy-plus-openrgb-presets.git --enable
```

The plugin uses the `nf-md-lightbulb_on_50` Nerd Font icon and defaults to the left bar section. Hugin's central bar configuration places it immediately after Screen Time. Its panel is anchored to the widget and opens directly below it.

When first enabled, the plugin restores the saved preset or applies Tokyo Night Purple when no saved state exists.

## Remove

```bash
omarchy plugin remove io.github.ol4vr.openrgb-presets
```

Removing the plugin does not change the currently active hardware lighting state.

## ST100 rainbow limitation

The ST100 starts its internal animated rainbow after a USB power cycle, but OpenRGB exposes only Direct mode for this controller and cannot return it to firmware animation. The Animated Rainbow preset therefore uses a static eight-color base strip and a compensated logo color. It does not reset USB or continuously stream software animation frames.
