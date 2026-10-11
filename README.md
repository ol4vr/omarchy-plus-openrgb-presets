# OpenRGB Presets

A Hugin-specific Omarchy bar plugin for switching between reviewed static,
hardware-animated, and synchronized OpenRGB Effects presets.

## Presets

- **Deep Red** — calibrated static red.
- **Deep Blue** — static Electric Sunrise blue (`#4000FF`) on every controller.
- **Bright White** — static white with ST100 logo compensation.
- **Animated Rainbow** — controller-native animation with an ST100 fallback.
- **Neon Rain** — synchronized five-color Rain effect.
- **Aurora Comet** — synchronized green Comet effect.
- **Spectrum Wave** — synchronized Rainbow Wave effect.
- **Matte Black Orange** — Electric Sunrise motion using `#FF4400` and off.
- **Electric Sunrise** — synchronized blue, violet, red, and orange Sunrise effect.
- **Horde Red** — Electric Sunrise motion using Deep Red `#8B0000` and off.
- **Alliance Blue** — Electric Sunrise motion using `#4000FF` and off.
- **Black (Turn Off RGB)** — stops active effects and sends black to every controller.

The seven synchronized presets are stored as reviewed Hugin Effects profiles in
`effects-profiles/`. Static and hardware presets stop every active software
effect before changing controller modes, preventing an old effect thread from
overwriting the selected state.

The panel library uses six complete two-column rows: Deep Red / Deep Blue,
Bright White / Animated Rainbow, Neon Rain / Aurora Comet, Spectrum Wave /
Electric Sunrise, Matte Black Orange / Black, and Horde Red / Alliance Blue.

## Hardware contract

The helper targets controllers by detected name, never enumeration index:

- Four Corsair Dominator Platinum RGB DDR5 modules
- ASUS TUF GeForce RTX 4090 Gaming OG OC
- Corsair ST100 RGB
- ASUS ROG STRIX Z790-F GAMING WIFI

The OpenRGB configuration must retain these addressable-zone sizes:

- Aura Addressable 1: 30 LEDs — radiator fans, CPU block, and Phanteks NV5 strip
- Aura Addressable 2: 20 LEDs — five ASUS Prime MR120 ARGB case fans
- Aura Addressable 3: 0 LEDs — unused and excluded from Effects profiles

Every operation first requires exactly seven accepted Hugin controllers: four
RAM modules and one each of the GPU, ST100, and motherboard.

## Runtime architecture

The Omarchy service starts `openrgb-lifecycle`, which owns one GUI-capable
OpenRGB process minimized in the background. Before launching OpenRGB, the
lifecycle reuses the existing `127.0.0.1:6742` listener only when its owner has
the exact accepted OpenRGB server command. It performs the slow hardware scan
once, loads the Effects Plugin, and exposes the SDK only on loopback. The
service then restores the last successful preset after the SDK and accepted
controllers become ready. Preset changes normally take about one second rather
than repeating the hardware scan.

`openrgb-lifecycle` monitors logind's `PrepareForSleep` signal and holds a
standard delay inhibitor while Hugin is awake. Before suspend or hibernation it
terminates OpenRGB, waiting briefly and using SIGKILL only if a clean shutdown
does not complete, then releases the inhibitor. After resume it reacquires the
inhibitor, waits three seconds for SMBus devices to settle, starts OpenRGB, and
restores the saved preset. This prevents the running OpenRGB process from
leaving the four Corsair DDR5 controllers inaccessible across sleep.

Every OpenRGB CLI and Effects SDK operation has a hard timeout. A stalled SDK
connection therefore produces a bounded error instead of freezing the panel.

`Panel.qml` only reads the saved preset to initialize its selection state. It
does not change hardware when the panel is constructed, so boot persistence is
independent of whether the bar panel has been opened.

`effects-sdk` is a small Python standard-library client. It discovers the
Effects Plugin by name, verifies saved profiles, stops running effect threads,
and loads reviewed profiles through the loopback SDK. It does not assume a
fixed plugin or hardware enumeration index.

## OpenRGB Effects Plugin dependency

Synchronized presets require the official OpenRGB Effects Plugin 1.0rc2 API4
binary for Linux x86-64. The GPL-2.0-or-later binary is not redistributed in
this MIT repository.

Reviewed artifact:

```text
OpenRGBEffectsPlugin_1.0rc2_Linux_amd64_415dc20.so
SHA256: 2f3c2b3c2c850e7148b4aa459bd41ccf9c56bd26fd00809fa19126ac5ad8dbc0
Source: https://openrgb.org/plugin_effects.html
```

After reviewing and downloading that artifact, install it and the seven bundled
profiles with:

```bash
PLUGIN_DIR="$PWD"
"$PLUGIN_DIR/install-effects-plugin"
```

The installer refuses a binary with any other checksum. It installs the plugin
and profiles under `~/.config/OpenRGB/plugins/`.

## Privilege boundary

The plugin runs as the graphical-session user. It never invokes `sudo`,
`pkexec`, a shell through QML, USB resets, firmware operations, or arbitrary
user-provided commands. Its standard logind delay inhibitor only delays sleep
long enough to terminate its own OpenRGB child. The SDK server accepts
connections only from Hugin's loopback interface.

`apply-preset` accepts only the twelve fixed identifiers listed by
`apply-preset --list`. It serializes changes with a private advisory lock and
records the latest OpenRGB or Effects SDK diagnostic output at:

```text
~/.local/state/omarchy-plus/openrgb-presets/last-openrgb.log
```

## Validate

```bash
PLUGIN_DIR="$PWD"
omarchy plugin validate "$PLUGIN_DIR"
qmllint -I "$OMARCHY_PATH/shell" \
  "$PLUGIN_DIR/BarWidget.qml" \
  "$PLUGIN_DIR/Panel.qml" \
  "$PLUGIN_DIR/Service.qml"
/usr/bin/bash -n "$PLUGIN_DIR/apply-preset"
/usr/bin/bash -n "$PLUGIN_DIR/openrgb-lifecycle"
/usr/bin/bash -n "$PLUGIN_DIR/install-effects-plugin"
/usr/bin/python3 -m py_compile "$PLUGIN_DIR/effects-sdk"
"$PLUGIN_DIR/tests/test-lifecycle-duplicate-prevention"
/usr/bin/python3 "$PLUGIN_DIR/tests/test-presets.py"
"$PLUGIN_DIR/openrgb-lifecycle" --check
"$PLUGIN_DIR/apply-preset" --list
"$PLUGIN_DIR/apply-preset" --dry-run black
"$PLUGIN_DIR/apply-preset" --dry-run spectrum-wave
"$PLUGIN_DIR/apply-preset" --dry-run matte-black-orange
"$PLUGIN_DIR/apply-preset" --dry-run deep-blue
```

## Install

Install through Omarchy after the source has been reviewed and committed:

```bash
omarchy plugin add https://github.com/ol4vr/omarchy-plus-openrgb-presets.git --enable
```

The plugin uses the `nf-md-lightbulb_on_50` Nerd Font icon and defaults to the
left bar section. Hugin's bar configuration places it immediately after Screen
Time, with the panel opening below the widget.

When enabled, the service performs one background scan and restores the last
successful preset. The fallback for a missing state file is Bright White. The
removed Tokyo Night Purple identifier migrates to Bright White.

## Roll back to 0.3.1

Before rolling back a deployed 0.4.0 installation, select one of the 0.3.1
presets if a new preset is active. Redeploy exact commit
`9063fce3a48912326eb6e8e024b36d48d420a8f5`, run its reviewed Effects
installer, and remove only these 0.4.0 profile files from the installed Effects
profile directory:

```text
hugin-sunrise-blue-black
hugin-sunrise-orange-black
hugin-sunrise-red-black
```

The four original bundled profile hashes are unchanged, so no existing Effects
profile needs conversion or reconstruction.

## Remove

```bash
omarchy plugin remove io.github.ol4vr.openrgb-presets
```

Removing the Omarchy plugin stops its OpenRGB background host but leaves the
official Effects Plugin binary, saved profiles, and current hardware lighting
state in place.

## ST100 rainbow limitation

The ST100 starts its internal animated rainbow after a USB power cycle, but
OpenRGB exposes only Direct mode and cannot return it to firmware animation.
Animated Rainbow therefore uses a static eight-color base strip and compensated
logo color. Spectrum Wave drives the ST100 through the Effects Plugin.
