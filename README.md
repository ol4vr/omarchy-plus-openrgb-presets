# OpenRGB Presets

A Hugin-specific Omarchy bar plugin for switching between reviewed static,
hardware-animated, and synchronized OpenRGB Effects presets.

## Presets

- **Deep Red** — calibrated static red.
- **Deep Blue** — static darkest Alliance blue (`#000B22`) on every controller.
- **Bright White** — static white with ST100 logo compensation.
- **Animated Rainbow** — controller-native animation with an ST100 fallback.
- **Neon Rain** — synchronized five-color Rain effect.
- **Aurora Comet** — synchronized green Comet effect.
- **Spectrum Wave** — synchronized Rainbow Wave effect.
- **Matte Black Orange** — Electric Sunrise motion using `#FF4400`, `#E83B00`, `#C92B00`, and `#501000`.
- **Electric Sunrise** — synchronized blue, violet, red, and orange Sunrise effect.
- **Horde Red** — Electric Sunrise motion using `#8B0000`, `#680000`, `#4A0000`, and `#180000`.
- **Alliance Blue** — Electric Sunrise motion using `#0033AA`, `#002788`, `#001A66`, and `#000B22`.
- **Black (Turn Off RGB)** — stops active effects and sends black to every controller.

The seven synchronized presets are stored as reviewed Hugin Effects profiles in
`effects-profiles/`. Their 60 FPS assignments contain only the GPU, both ST100
zones, and the three motherboard zones. Static and hardware presets stop every
active software effect before changing controller modes, preventing an old
effect thread from overwriting the selected state.

## DDR5 lighting and static fallback

Version 0.4.8 keeps all four Corsair DDR5 modules out of continuously updating
Effects Plugin assignments. Selecting or restoring a preset writes one static
Direct-mode color to the shared DDR5 device name after active effects are
stopped and the non-DDR effect is loaded. The GPU, ST100, and motherboard
retain the exact existing profile, 60 FPS rate, colors, animation settings,
and zone mappings. Animated Rainbow
continues to use the GPU and motherboard hardware rainbow modes plus the ST100
fallback, while DDR5 receives one static write instead of its former hardware
rainbow selection.

| Preset | Static DDR5 color | Source |
| --- | --- | --- |
| Deep Red | `#8B0000` | owner-approved |
| Deep Blue | `#000B22` | owner-approved |
| Bright White | `#FFFFFF` | owner-approved |
| Animated Rainbow | `#404040` | owner-approved neutral dim white |
| Neon Rain | `#5500FF` | darkest decoded profile `UserColors` entry |
| Aurora Comet | `#404040` | owner-approved neutral dim white |
| Spectrum Wave | `#404040` | owner-approved neutral dim white |
| Electric Sunrise | `#3C00FF` | darkest decoded profile `UserColors` entry |
| Matte Black Orange | `#501000` | owner-approved |
| Black | `#000000` | owner-approved |
| Horde Red | `#180000` | owner-approved |
| Alliance Blue | `#000B22` | owner-approved |

Animated Rainbow, Aurora Comet, and Spectrum Wave do not expose a finite active
palette from which a unique darkest color can be derived: the two rainbow
effects generate the spectrum, while Comet has `RandomColors` enabled. Their
owner-approved static DDR5 fallback is therefore neutral dim white. No source
palette or non-DDR visual effect is changed by this workaround.

Version 0.4.9 adds a compact **RAM Tetris** toggle without changing the twelve
preset cards or keyboard navigation. Its separate preference defaults to OFF
and is stored as `ram-tetris-enabled` beside the selected preset. OFF retains
the v0.4.8 static mapping above. ON uses six two-LED blocks per DIMM, preserves
landed block colors, and independently fills and resets all four modules. Each
new block draws from the selected preset's reviewed palette with black
excluded. Single-color presets remain single-color. Black keeps every DDR5 LED
off and suspends animation while preserving the ON preference.

| Preset | RAM Tetris palette |
| --- | --- |
| Animated Rainbow | `#FF4D6D`, `#FFD166`, `#06D6A0`, `#4CC9F0`, `#9B5DE5` |
| Neon Rain | `#5500FF`, `#11FF00`, `#00FF8C`, `#FF00F6`, `#FFD400` |
| Aurora Comet | `#95FF00`, `#00D4FF`, `#8A2BE2` |
| Spectrum Wave | `#FF4D6D`, `#FFD166`, `#06D6A0`, `#4CC9F0`, `#9B5DE5` |
| Electric Sunrise | `#FF0040`, `#FF0051`, `#3C00FF`, `#0044FF` |
| Matte Black Orange | `#FF4400`, `#E83B00`, `#C92B00`, `#501000` |
| Horde Red | `#8B0000`, `#680000`, `#4A0000`, `#180000` |
| Alliance Blue | `#0033AA`, `#002788`, `#001A66`, `#000B22` |

Deep Red, Deep Blue, and Bright White use their one accepted static color.

Version 0.4.10 changes no lighting behavior. The RAM Tetris entry point disables
Python bytecode generation before loading its local scheduler module, keeping
Git-managed production checkouts free of generated `__pycache__` and `.pyc`
artifacts for every command.

Version 0.4.11 corrects lifecycle duplicate detection without changing RGB
behavior. The writer still verifies its lifecycle PID, start token, and exact
argv, but excludes descendant Bash helpers that inherit the owner's argv. An
independent same-argv lifecycle remains a fail-closed duplicate.

Version 0.4.12 maps Spectrum Wave's profile class name `RainbowWave` to the
Effects SDK display name `Rainbow Wave`. The writer continues to require the
exact single expected live effect and the reviewed six non-DDR assignments;
missing, duplicate, or additional Effects instances still fail closed.

Human-facing colors in this documentation use `#RRGGBB`. Effects Plugin
`UserColors` store OpenRGB `RGBColor` integers in packed `0x00BBGGRR` order.
The experimental orange, blue, and red Sunrise gradients are therefore stored
as `[17663, 15336, 11209, 4176]`,
`[11154176, 8922880, 6691328, 2231040]`, and `[139, 104, 74, 24]`,
respectively.

Effects Plugin 1.0rc2's Sunrise implementation always renders four gradient
stops. Each experimental profile supplies all four explicitly, with a darker
same-hue final stop for stronger visible motion without relying on zero-valued
black padding. FPS, speed, motion, intensity, radius, timing, and controller
assignments remain identical to Electric Sunrise.

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

The Omarchy service starts `openrgb-lifecycle`, which maintains one GUI-capable
OpenRGB process minimized in the background. Before launching OpenRGB, the
lifecycle reuses the existing `127.0.0.1:6742` listener only when its owner has
the exact accepted OpenRGB server command. It records whether the server was
launched or adopted together with its PID and Linux `/proc` start-time token.
Ordinary Quickshell teardown releases only the lifecycle's tracking state; it
does not signal either an adopted server or one launched by the outgoing
lifecycle. The successor validates and adopts the same listener identity, so a
shell restart does not repeat the hardware scan. OpenRGB output is written to
the per-session runtime log `openrgb-server.log` rather than a Quickshell pipe
that closes during handoff. The service restores the last successful preset
after the SDK and accepted controllers become ready. Preset changes normally
take about one second rather than repeating the hardware scan.

`openrgb-lifecycle` monitors logind's `PrepareForSleep` signal and holds a
standard delay inhibitor while Hugin is awake. Before suspend or hibernation it
terminates OpenRGB only after revalidating the tracked PID, start-time token,
exact command, and ownership of the loopback listener. It waits briefly and
uses SIGKILL only if that complete identity still matches, then releases the
inhibitor. After resume it reacquires the inhibitor, waits three seconds for
SMBus devices to settle, starts or adopts exactly one OpenRGB server, and
restores the saved preset. A stale PID or changed listener is never signaled.
This prevents the running OpenRGB process from leaving the four Corsair DDR5
controllers inaccessible across sleep.

One nonblocking per-user runtime lock admits only one lifecycle owner during
plugin rescans or concurrent shell startup. The inhibitor and logind monitor
are launched with Linux parent-death signals through the existing util-linux
`setpriv` command. Normal shutdown still releases them explicitly; if the
lifecycle is killed before its traps complete, the kernel sends each child
`SIGTERM`. Child processes explicitly close the runtime lock descriptor, so an
OpenRGB server, preset restoration, inhibitor, or monitor cannot accidentally
retain lifecycle ownership.

The lifecycle also owns at most one `ram-tetris` writer. A private writer lock
prevents duplicates across reconciliation and Quickshell handoff. The writer
uses one non-detecting SDK connection, resolves each DIMM by exact name and
I801 address before every update, and globally serializes complete twelve-LED
frames. Seeded 200, 300, or 400 ms intervals enforce at most five updates per
second per DIMM, 20 globally, 200 ms per DIMM, and 50 ms globally. Delayed
frames are rescheduled instead of replayed as bursts.

Before each write it rechecks the SDK PID/start token/argv/listener, lifecycle,
boot and suspend identity, seven-controller inventory, all four SPD5118
readings, Direct mode and twelve LEDs, the active six-zone Effects contract,
selected preset, and new kernel errors. A failed gate latches a visible panel
failure in persistent private state and stops without a recovery write or
automatic restart. The latch survives lifecycle, Quickshell, suspend/resume,
and application restarts; ordinary OFF and ON actions never clear it. Turning
the toggle OFF restores the static DDR5 color only after fresh health gates pass.
Preset changes quiesce the writer under its lock before applying the existing
preset. Suspend and Quickshell handoff stop it before SDK teardown or adoption;
a parent-death signal prevents an orphan writer after abrupt shell exit.

Clearing a hardware-failure latch is deliberately absent from the panel. After
a separately reviewed recovery establishes healthy hardware, the owner must
first leave RAM Tetris OFF and then run:

```bash
~/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/ram-tetris \
  clear-failure --acknowledge-reviewed-recovery
```

The command refuses to run while the preference is ON or while a writer owns
the singleton lock. A later ON request still passes every normal health gate.

Legacy 0.3.x/0.4.0 inhibitors and logind monitors can be classified for
one-time cleanup with the read-only `--classify-legacy-inhibitor` and
`--classify-legacy-monitor` modes. They require the candidate and active
lifecycle PIDs plus their `/proc` start-time tokens, and return `stale-legacy`
only when the exact command, user, cgroup, and user-systemd parent all match.
The inhibitor check also requires its expected process-group ownership; the
monitor check requires a uniquely paired owned inhibitor from the same startup
window. Every other process is ineligible. Cleanup still requires separate
owner authorization and an immediate identity recheck.

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
/usr/bin/python3 -m py_compile "$PLUGIN_DIR/ram-tetris" "$PLUGIN_DIR/ram_tetris_core.py"
"$PLUGIN_DIR/tests/test-lifecycle-duplicate-prevention"
"$PLUGIN_DIR/tests/test-lifecycle-inhibitors"
/usr/bin/python3 "$PLUGIN_DIR/tests/test-presets.py"
/usr/bin/python3 "$PLUGIN_DIR/tests/test-ram-tetris.py"
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

## Roll back the 0.4.1 lifecycle correction

Redeploy exact 0.4.0 commit
`a903531e6d0b743e83cd29a94b25d46a78a1495c`. The correction adds only an
ephemeral lock file below `$XDG_RUNTIME_DIR/omarchy-plus/openrgb-presets`; it
can be left for the next login or removed after the corrected lifecycle has
stopped. Rolling back does not change presets, Effects profiles, OpenRGB
configuration, or saved active-preset state.

## Roll back the 0.4.2 palette correction

Redeploy exact 0.4.1 commit
`ec74773e02d20d8d31550627d71f7524ae543789` and run its reviewed Effects
installer. This restores only the previous stored color values and release
metadata; it does not change the accepted panel layout, lifecycle behavior,
controller assignments, or saved active-preset state.

## Roll back the 0.4.3 color tuning

Redeploy exact 0.4.2 commit
`02fb0eaecd69ac944866283c41b5971f11745eb3` and run its reviewed Effects
installer. This restores the prior Deep Blue command, the three prior animated
palettes, their panel indicators, and release metadata without changing the
accepted layout, lifecycle behavior, controller assignments, or saved preset.

## Roll back the 0.4.4 palette refinement

Redeploy exact 0.4.3 commit
`27b90a1060c12f05e3bfd83762599723263d880f` and run its reviewed Effects
installer. This restores only the three prior two-color profile palettes,
their panel indicators, and release metadata without changing Deep Blue,
Electric Sunrise, the accepted layout, lifecycle behavior, controller
assignments, or saved preset.

## Roll back the 0.4.5 darker gradient endpoints

Redeploy exact 0.4.4 commit
`ce587ab09de1d434809653b911a7bac22c067ea9` and run its reviewed Effects
installer. This restores only the prior fourth color in each experimental
Sunrise profile and its release metadata without changing the first three
colors, animation settings, controller assignments, panel layout, lifecycle
behavior, or saved preset.

## Roll back the 0.4.6 final Deep Blue color

Redeploy exact 0.4.5 commit
`f5cee512e9eebcd29d1f75e3411e670bb7169692`. This restores only the static
Deep Blue CLI color, its panel indicator, focused assertions, documentation,
and release metadata. Effects profiles, animation settings, controller
assignments, panel layout, lifecycle behavior, and saved preset are unchanged.

## Roll back the 0.4.7 SDK lifecycle handoff correction

Redeploy exact 0.4.6 commit
`1e70d15f2ad20c3b4d2bf6606b7054d9b9c2e7c6`. This restores the previous SDK
cleanup behavior and release metadata without changing presets, Effects
profiles, controller mappings, OpenRGB configuration, or saved preset. Because
0.4.6 can terminate an adopted listener during shell teardown, perform rollback
only with the reviewed controller-health preflight and preserve the active
server identity for recovery.

## Roll back the 0.4.8 static DDR5 workaround

Redeploy exact accepted v0.4.7 commit
`ae8d12589e5f77b190fa0cffcde06bfa55fbe4f7` and run its reviewed Effects
installer to restore the seven original ten-zone profiles. Do not roll back or
reapply a profile while DDR5 SPD access is degraded. After a reviewed cold
recovery and seven-controller health check, applying the saved preset restores
the prior continuously animated DDR5 behavior. Version 0.4.8 changes no panel,
palette, non-DDR animation, SDK lifecycle, controller identity, or persisted
preset format.

## Roll back the 0.4.9 RAM Tetris integration

First turn RAM Tetris OFF while all hardware-health gates pass, then verify the
selected preset's static DDR5 color. Redeploy exact accepted v0.4.8 commit
`da442105970eff86e669ebc6d72326e23c8e11a8`. The separate
`ram-tetris-enabled` preference may remain as inert state or be removed only
after the lifecycle is stopped. The rollback restores accepted static DDR5
behavior without changing the twelve presets, seven Effects profiles, OpenRGB
or Effects Plugin binaries, or non-DDR animations. If communication is already
degraded, do not request a restoration write; stop for hardware-recovery
review instead. Do not delete `ram-tetris-failure.json` merely to complete a
rollback; preserve it as failure evidence until that review is complete.

## Remove

```bash
omarchy plugin remove io.github.ol4vr.openrgb-presets
```

Removing the Omarchy plugin stops its lifecycle, inhibitor, and logind monitor
but leaves the verified OpenRGB SDK host running, just as an ordinary shell
handoff does. A deliberate SDK stop remains a separate owner-authorized
operation. The official Effects Plugin binary, saved profiles, and current
hardware lighting state remain in place.

## ST100 rainbow limitation

The ST100 starts its internal animated rainbow after a USB power cycle, but
OpenRGB exposes only Direct mode and cannot return it to firmware animation.
Animated Rainbow therefore uses a static eight-color base strip and compensated
logo color. Spectrum Wave drives the ST100 through the Effects Plugin.
