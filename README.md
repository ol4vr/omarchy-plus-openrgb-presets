# OpenRGB Presets

A Hugin-specific Omarchy bar plugin for switching between reviewed static,
hardware-animated, and synchronized OpenRGB Effects presets.

## Presets

- **Static Red** — calibrated static red.
- **Static Blue** — static darkest Alliance blue (`#000B22`) on every controller.
- **Static White** — static white with ST100 logo compensation.
- **Animated Rainbow** — controller-native animation with an ST100 fallback.
- **Neon Rain** — synchronized five-color Rain effect.
- **Aurora Comet** — synchronized green Comet effect.
- **Spectrum Wave** — synchronized Rainbow Wave effect.
- **Matte Black Orange** — Electric Sunrise motion using `#FF4400`, `#E83B00`, `#C92B00`, and `#501000`.
- **Electric Sunrise** — synchronized blue, violet, red, and orange Sunrise effect.
- **For the Horde!** — Electric Sunrise motion using `#8B0000`, `#680000`, `#4A0000`, and `#180000`.
- **For the Alliance!** — Electric Sunrise motion using `#0033AA`, `#002788`, `#001A66`, and `#000B22`.
- **Black (Turn Off RGB)** — stops active effects and sends black to every controller.

The seven synchronized presets are stored as reviewed Hugin Effects profiles in
`effects-profiles/`. Their 60 FPS assignments contain only the GPU, both ST100
zones, and the three motherboard zones. Static and hardware presets stop every
active software effect before changing controller modes, preventing an old
effect thread from overwriting the selected state.

## DDR5 lighting and static fallback

All four Corsair DDR5 modules remain outside continuously updating Effects
Plugin assignments. Version 0.4.15 replaces the former uniform fallback with
one complete twelve-color Direct-mode array per DIMM after active effects are
stopped and the non-DDR effect is loaded. The six entries below are paired LED
groups from logical indices `0-1` through `10-11`; each listed color is sent to
both LEDs in its group. Every color comes from that preset's accepted RAM
Tetris palette.

| Preset | Six paired static groups (`0-1` through `10-11`) |
| --- | --- |
| Static Red | `#8B0000 · #8B0000 · #8B0000 · #8B0000 · #8B0000 · #8B0000` |
| Static Blue | `#000B22 · #000B22 · #000B22 · #000B22 · #000B22 · #000B22` |
| Static White | `#FFFFFF · #FFFFFF · #FFFFFF · #FFFFFF · #FFFFFF · #FFFFFF` |
| Animated Rainbow | `#11FF00 · #8A2BE2 · #FFD400 · #FF0040 · #8A2BE2 · #11FF00` |
| Neon Rain | `#5500FF · #11FF00 · #00FF8C · #FF00F6 · #FFD400 · #5500FF` |
| Aurora Comet | `#95FF00 · #00D4FF · #8A2BE2 · #8A2BE2 · #00D4FF · #95FF00` |
| Spectrum Wave | `#11FF00 · #8A2BE2 · #FFD400 · #FF0040 · #8A2BE2 · #11FF00` |
| Electric Sunrise | `#FF0040 · #FF0051 · #3C00FF · #0044FF · #FF0051 · #FF0040` |
| Matte Black Orange | `#FF4400 · #E83B00 · #C92B00 · #501000 · #E83B00 · #FF4400` |
| Black | `#000000 · #000000 · #000000 · #000000 · #000000 · #000000` |
| For the Horde! | `#8B0000 · #680000 · #4A0000 · #180000 · #680000 · #8B0000` |
| For the Alliance! | `#0033AA · #002788 · #001A66 · #000B22 · #002788 · #0033AA` |

Four-color palettes use the approved `A B C D B A` group order. The
three-color Aurora palette uses `A B C C B A`; five-color Neon Rain uses
`A B C D E A`, repeating only its first existing color. Single-color presets
remain uniform and Black remains fully off. Animated Rainbow continues to use
the GPU and motherboard hardware rainbow modes plus the ST100 fallback. No
non-DDR color, animation setting, profile, or zone mapping changes.

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
| Animated Rainbow | `#11FF00`, `#8A2BE2`, `#FFD400`, `#FF0040` |
| Neon Rain | `#5500FF`, `#11FF00`, `#00FF8C`, `#FF00F6`, `#FFD400` |
| Aurora Comet | `#95FF00`, `#00D4FF`, `#8A2BE2` |
| Spectrum Wave | `#11FF00`, `#8A2BE2`, `#FFD400`, `#FF0040` |
| Electric Sunrise | `#FF0040`, `#FF0051`, `#3C00FF`, `#0044FF` |
| Matte Black Orange | `#FF4400`, `#E83B00`, `#C92B00`, `#501000` |
| For the Horde! | `#8B0000`, `#680000`, `#4A0000`, `#180000` |
| For the Alliance! | `#0033AA`, `#002788`, `#001A66`, `#000B22` |

Static Red, Static Blue, and Static White use their one accepted static color.

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

Version 0.4.13 refines only the Animated Rainbow and Spectrum Wave RAM Tetris
palettes to the accepted green, purple, yellow, and red colors. Their non-DDR
Effects behavior and neutral static DDR5 fallback remain unchanged.

Version 0.4.14 changed only the Animated Rainbow and Spectrum Wave uniform
static DDR5 fallback from `#404040` to the owner-approved OpenRGB CLI color
`#0033AA`. Version 0.4.15 supersedes every uniform fallback with the fixed
paired arrays documented above while leaving RAM Tetris, non-DDR Effects, and
animation behavior unchanged.

Version 0.4.16 makes a user-requested OFF transition race-free. The helper
publishes the `user-off` stop request before changing the persisted preference,
and the writer treats an OFF value as a clean stop only when that matching stop
request is present. An unexplained preference change still latches a fail-closed
state, while healthy OFF restoration continues to use the selected preset's
reviewed static array.

Version 0.4.17 compacts the Lighting Panel without changing RGB behavior. The
two-column preset library keeps its six-row order, exact swatches, mode badges,
keyboard navigation, and focus states while removing card subtitles and
reducing vertical space. The active card retains its description and now shows
the exact mode: Static Color, Rainbow, Rain, Comet, Rainbow Wave, Sunrise, or
Lights Off. RAM Tetris uses a compact memory-chip row. Static Red, Static Blue,
Static White, For the Horde!, and For the Alliance! are display-label changes
only; their stable preset identifiers, saved-state compatibility, palettes, and
restoration paths are unchanged.

Version 0.4.18 makes an intentional lifecycle handoff race-free. The outgoing
lifecycle serializes an authenticated stop record against every RGB write,
then waits for the writer to terminate and release its singleton before
releasing lifecycle ownership. The record is bound to the lifecycle and SDK
PID/start-token identities. A successor still performs its own SDK listener,
seven-controller, SPD5118, Effects, preset, and kernel-error validation before
starting a writer. A zero-owner interval without the matching record, abrupt
parent death, duplicate lifecycle, or changed SDK identity remains a persistent
fail-closed event; no grace period, automatic recovery, or latch clearing was
added.

Version 0.4.19 removes lifecycle ownership from Quickshell. The plugin manifest
now exposes only the bar widget; no QML `Process` starts, restarts, or stops the
lifecycle. An Omarchy+-owned `systemd --user` service starts with the graphical
session, reports ready only after preset restoration and the complete read-only
SDK, seven-controller, four-SPD5118, Effects, preset, lifecycle, and kernel-error
gate, and stops at graphical-session teardown. It has no automatic restart.
Normal Quickshell restart, plugin hot reload, and UI failure therefore leave
the lifecycle, SDK, inhibitor, logind monitor, and optional writer unchanged.
Bounded service shutdown retains the v0.4.18 authenticated writer stop and
singleton release. A private persistent service-state guard preserves an
existing failure latch and creates one if shutdown requires manager escalation.

Version 0.4.20 makes the startup and resume kernel-journal gate cover the whole
bounded controller-discovery window. One immutable journal cursor is captured
before the first of at most fifteen read-only attempts. Every attempt checks
all communication errors after that cursor, so a later seven-controller result
cannot erase an earlier failure. Missing or incomplete journal access and any
matching error fail closed before `apply-preset` can run. The retry count,
delay, ownership checks, SPD5118 checks, presets, Effects profiles, colors, and
writer behavior are unchanged.

Version 0.4.21 bounds deliberate service shutdown inside systemd's existing
20-second stop budget. One 15-second lifecycle deadline now covers the
authenticated writer stop, SDK termination, inhibitor release, and logind
monitor cleanup. Child reaping occurs only after the tracked PID/start-token
identity has exited or become a zombie; a live child can no longer enter an
unbounded shell `wait`. The SDK still receives TERM first and SIGKILL only
after its listener identity is revalidated. A surviving or transferred SDK
listener, exhausted deadline, or incomplete writer stop remains fail closed
and leaves the service boundary incomplete for the existing guard to latch.

Version 0.4.22 adds one universal Lighting Recovery interface without adding a
generic service restart, SDK restart, preset selection, or direct RGB write. A
persistent failure replaces the RAM Tetris toggle with a compact red Recover control. A
Tetris-only writer failure is distinguished from a full lifecycle/SDK outage;
controller, kernel, and unknown failures remain separate blocked classes. The
first click runs a read-only classification and health review. The two
historically reviewed v0.4.11/v0.4.12 false positives can advance to a timed
explicit confirmation while the independent service, lifecycle, SDK,
controller inventory, four SPD5118 endpoints, Effects contract, locks, and
kernel history all pass.

The extension also accepts one exact incomplete service boundary: a correlated
current-boot `stopping/deliberate` owner record with a reviewed lifecycle
failure reason, the exact failed unit and OpenRGB package, an active graphical
session, the Hugin detector policy, zero owners or SDK listener, free locks,
and clean kernel history. Confirmation preserves both original records and the
reviewed OpenRGB configuration bytes, writes the preference OFF, invokes the
existing boundary acknowledgment, and starts the service at most once. The
service itself must report ready and the complete
seven-controller, four-SPD5118, Effects, ownership, and journal gate must pass
before the unchanged latch is cleared. Failure leaves the evidence and latch
in place with no retry. Neither recovery path starts RAM Tetris.

The failure row shows a stable error code and short description. Its expandable
diagnostic view retains the original backend reason, incident reference,
first-detected UTC timestamp, affected subsystem, and recovery disposition.
Copy Diagnostics places only those concise non-sensitive fields on the
clipboard. The original failure bytes remain the authority; display codes are
never recovery authorization.

Stable diagnostic mappings are:

| Code | Condition | Subsystem | Automatic recovery |
| --- | --- | --- | --- |
| `LGT-LIF-001` | stale or manager-completed lifecycle boundary | lifecycle | exact boundary-gated one start |
| `LGT-LIF-002` | unauthenticated writer termination at a lifecycle boundary | lifecycle | exact boundary-gated one start |
| `LGT-LIF-003` | lifecycle identity, handoff, boot, or suspend continuity changed | lifecycle | blocked |
| `LGT-SDK-001` | SDK process, listener, connection, or protocol became invalid | SDK | blocked |
| `LGT-EFX-001` | Effects contract or profile became invalid | Effects | blocked |
| `LGT-EFX-002` | preset application failed after Tetris quiesced | Effects | blocked |
| `LGT-EFX-003` | saved preset restoration failed | Effects | blocked |
| `LGT-TET-001` | unreviewed Tetris writer/control failure | Tetris | blocked |
| `LGT-TET-002` | writer exited unexpectedly | Tetris | blocked |
| `LGT-TET-003` | writer failed to quiesce | Tetris | blocked |
| `LGT-TET-101` | reviewed legacy lifecycle-count false positive | Tetris | health-gated confirmation |
| `LGT-TET-102` | reviewed legacy Spectrum Effects-name false positive | Tetris | health-gated confirmation |
| `LGT-CTL-001` | controller inventory, mode, LED count, or write failure | controller | blocked |
| `LGT-CTL-002` | required SPD5118 endpoint missing or unreadable | controller | blocked |
| `LGT-KRN-001` | kernel journal or relevant I2C/SMBus/SPD error | kernel | blocked |
| `LGT-UNK-000` | unknown or malformed failure | unknown | manual review |

Exact backend messages and conservative prefixes assign these display codes.
Only the exact two reviewed legacy messages or the exact correlated deliberate
lifecycle boundary—not their display codes—can enter recovery.

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

The panel library uses six complete two-column rows: Static Red / Static Blue,
Static White / Animated Rainbow, Neon Rain / Aurora Comet, Spectrum Wave /
Electric Sunrise, Matte Black Orange / Black, and For the Horde! / For the
Alliance!.

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

`omarchy-plus-openrgb-presets.service` owns `openrgb-lifecycle` independently
of Quickshell. It is wanted by and part of `graphical-session.target`, uses
`Type=notify`, and has `Restart=no`. The plugin contains no service entry point
and no QML lifecycle process; its panel is only a client of persisted state and
the bounded preset and RAM Tetris commands. Shell restart, plugin hot reload,
and UI failure cannot terminate or replace a healthy lifecycle.

Before launching OpenRGB, the lifecycle reuses the existing
`127.0.0.1:6742` listener only when its owner has the exact accepted OpenRGB
server command. It records whether the server was launched or adopted together
with its PID and Linux `/proc` start-time token. A server launched by the
service receives a Linux parent-death signal and remains in the service cgroup;
an already-running accepted server is identity-guarded during initial migration.
OpenRGB output is written to the per-session runtime log `openrgb-server.log`.
The service restores the last successful preset after the SDK and accepted
controllers become ready. Preset changes normally take about one second rather
than repeating the hardware scan.

Before any startup or resume restoration write, `ram-tetris validate-hardware`
captures one kernel-journal baseline, then independently verifies the lifecycle
and SDK identities, exactly seven accepted controllers, all four readable
SPD5118 temperatures, and the complete post-baseline error window across every
bounded discovery retry. The service becomes ready only after the restore succeeds and
`ram-tetris validate-health` then verifies those gates again together with the
selected preset's six-zone non-DDR Effects contract. An ON preference with a
failure latch remains ON but starts no writer. An ON preference without a latch
requires exactly one validated writer before readiness is published.

Hugin does not currently provide a stable mapping from generic DesignWare I2C
controller numbers to individual accepted RGB devices. The bounded gate
therefore treats `i2c_designware` timeouts, and other I2C, I801, SMBus, or
SPD5118 communication failures, as relevant without claiming that they are
DDR5-specific. USB, GPU, network, storage, and other unrelated kernel errors do
not match this policy. The retained kernel line is the evidence for later bus
classification.

`openrgb-lifecycle` monitors logind's `PrepareForSleep` signal and holds a
standard delay inhibitor while Hugin is awake. Before suspend or hibernation it
terminates OpenRGB only after revalidating the tracked PID, start-time token,
exact command, and ownership of the loopback listener. It waits briefly and
uses SIGKILL only if that complete identity still matches, then releases the
inhibitor. After resume it reacquires the inhibitor, waits three seconds for
SMBus devices to settle, starts or adopts exactly one OpenRGB server, validates
all four SPD endpoints, and only then restores the saved preset. A stale PID or
changed listener is never signaled. An unexpected SDK or inhibitor loss fails
the lifecycle and records the incomplete boundary; it is never automatically
restarted or replaced.
This prevents the running OpenRGB process from leaving the four Corsair DDR5
controllers inaccessible across sleep.

One nonblocking per-user runtime lock admits only one lifecycle owner during
concurrent service startup. The inhibitor and logind monitor
are launched with Linux parent-death signals through the existing util-linux
`setpriv` command. Normal shutdown still releases them explicitly; if the
lifecycle is killed before its traps complete, the kernel sends each child
`SIGTERM`. Child processes explicitly close the runtime lock descriptor, so an
OpenRGB server, preset restoration, inhibitor, or monitor cannot accidentally
retain lifecycle ownership.

The lifecycle also owns at most one `ram-tetris` writer. A private writer lock
prevents duplicates across reconciliation and service replacement. A separate
write gate lets an outgoing lifecycle wait for any already-started frame,
atomically publish its identity-bound stop request, and exclude every later
animation or restoration write. It does not release lifecycle ownership until
the writer has safely terminated and released its singleton. The writer
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
and application restarts; later failures cannot overwrite its retained
evidence, and ordinary OFF and ON actions never clear it. Turning
the toggle OFF restores the static DDR5 array only after fresh health gates pass.
Preset changes quiesce the writer under its lock before applying the existing
preset. Suspend and an explicitly initiated lifecycle replacement stop it
before SDK teardown or adoption. A parent-death signal without the authenticated
stop request latches as unexplained ownership loss. Quickshell is no longer the
writer's ancestor, so an abrupt shell exit is irrelevant to writer ownership.

On ordinary service stop, systemd signals only the lifecycle first. The
lifecycle serializes a `shutdown` stop record against writes, waits for the
writer and its singleton lock, stops the exact SDK listener, and releases the
inhibitor and monitor before recording `clean-stopped`. `ExitType=cgroup`,
`KillMode=mixed`, and parent-death signals keep every launched child within the
service-manager boundary. `TimeoutStopSec=20` is the outer bound. If cleanup
does not finish inside the lifecycle's 15-second internal deadline, the main
process exits failed and `KillMode=mixed` gives the manager five seconds to
kill any remaining cgroup process before its outer deadline. `ExecStopPost`
records a persistent failure latch before a later start can create a writer. A
manager-mediated `SIGUSR1` is reserved for an owner-authorized replacement
handoff; it uses the same authenticated writer stop but may retain an adopted
SDK whose identity remains valid.

The persistent owner record includes the kernel boot ID, lifecycle PID, and
`/proc` start token. An incomplete stop, power loss, or stale record from an
earlier boot creates or preserves the failure latch and blocks service startup
before SDK restoration. After a separately reviewed recovery, leave RAM Tetris
OFF with zero writer-lock owners, then acknowledge only the service boundary:

```bash
~/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/openrgb-service-guard \
  acknowledge-reviewed-recovery --acknowledge-reviewed-recovery
```

That command preserves the failure latch. `lighting-recovery` may invoke it
only for the exact correlated current-boot `stopping/deliberate` boundary after
preserving both records, setting RAM Tetris OFF, and confirming that the exact
failed unit has no owner, listener, or lock. It performs one service start and
requires full readiness before clearing the unchanged reviewed latch. Every
other lifecycle/SDK failure, and every hardware, controller, kernel, or unknown
failure, remains manual-review only. The legacy `ram-tetris clear-failure`
command always refuses; exact reasons and boundary bytes—not display codes—are
the authority for recovery.

The original technical record remains readable without changing state:

```bash
~/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/lighting-recovery status
~/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/lighting-recovery \
  copy-diagnostics --print
```

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
  "$PLUGIN_DIR/Panel.qml"
/usr/bin/bash -n "$PLUGIN_DIR/apply-preset"
/usr/bin/bash -n "$PLUGIN_DIR/openrgb-lifecycle"
/usr/bin/bash -n "$PLUGIN_DIR/install-effects-plugin"
/usr/bin/python3 -m py_compile "$PLUGIN_DIR/effects-sdk"
/usr/bin/python3 -m py_compile \
  "$PLUGIN_DIR/ram-tetris" \
  "$PLUGIN_DIR/ram_tetris_core.py" \
  "$PLUGIN_DIR/lighting-recovery" \
  "$PLUGIN_DIR/openrgb-service-guard"
/usr/bin/systemd-analyze --user verify \
  "$PLUGIN_DIR/systemd/omarchy-plus-openrgb-presets.service"
"$PLUGIN_DIR/tests/test-lifecycle-duplicate-prevention"
"$PLUGIN_DIR/tests/test-lifecycle-inhibitors"
/usr/bin/bash "$PLUGIN_DIR/tests/test-lifecycle-tetris-handoff"
"$PLUGIN_DIR/tests/test-independent-lifecycle"
/usr/bin/python3 "$PLUGIN_DIR/tests/test-presets.py"
/usr/bin/python3 "$PLUGIN_DIR/tests/test-ram-tetris.py"
/usr/bin/python3 "$PLUGIN_DIR/tests/test-lighting-recovery.py"
/usr/bin/python3 "$PLUGIN_DIR/tests/test-service-guard.py"
"$PLUGIN_DIR/openrgb-lifecycle" --check
"$PLUGIN_DIR/apply-preset" --list
"$PLUGIN_DIR/apply-preset" --dry-run black
"$PLUGIN_DIR/apply-preset" --dry-run spectrum-wave
"$PLUGIN_DIR/apply-preset" --dry-run matte-black-orange
"$PLUGIN_DIR/apply-preset" --dry-run deep-blue
```

## Install

Install through Omarchy only after the source and the user-service cutover have
been reviewed. A new installation needs both the plugin checkout and its
Omarchy+-owned unit:

```bash
omarchy plugin add https://github.com/ol4vr/omarchy-plus-openrgb-presets.git --enable
/usr/bin/install -Dm0644 \
  ~/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/systemd/omarchy-plus-openrgb-presets.service \
  ~/.config/systemd/user/omarchy-plus-openrgb-presets.service
systemctl --user daemon-reload
systemctl --user enable --now omarchy-plus-openrgb-presets.service
```

The plugin uses the `nf-md-lightbulb_on_50` Nerd Font icon and defaults to the
left bar section. Hugin's bar configuration places it immediately after Screen
Time, with the panel opening below the widget.

When started, the service performs one background scan and restores the last
successful preset. The fallback for a missing state file is Static White. The
removed Tokyo Night Purple identifier migrates to Static White; the internal
identifier remains `bright-white` for saved-state compatibility.

### Owner-authorized v0.4.18 migration

The v0.4.18-to-v0.4.19 transition is deliberately not automatic. Before
cutover, record the lifecycle, SDK, inhibitor, monitor, writer, and lock
identities; verify seven controllers and four readable SPD5118 endpoints; and
preserve the preference and failure-latch bytes. With the present ON preference
and historical latch, the required writer count is zero.

1. Stage the reviewed unit under `~/.config/systemd/user/` and run only
   `systemctl --user daemon-reload`. Do not enable or start it yet.
2. Reconcile only the plugin checkout to the accepted v0.4.19 revision. Removing
   the manifest service destroys the old QML owner. Do not continue until that
   lifecycle has exited, its lock is free, no writer exists, and the accepted
   SDK PID/start token is unchanged.
3. Start `omarchy-plus-openrgb-presets.service` once. It must acquire the sole
   lifecycle lock, adopt the existing listener, complete preset restoration and
   independent readiness validation, and report `ready`. The existing latch
   must remain byte-identical, preference must remain ON, and writer count must
   remain zero.
4. Only after those checks pass, enable the already-running unit for the next
   graphical session with
   `systemctl --user enable omarchy-plus-openrgb-presets.service`. Do not use
   `Restart=`, retry a failed start, clear the latch, or toggle RAM Tetris
   during cutover.

If the old lifecycle or writer remains, the SDK identity changes unexpectedly,
or the new service does not become ready, stop without starting another owner.
The service's first restoration uses the existing accepted preset path and can
write that preset; it therefore remains a separately authorized live-hardware
step even though this source candidate performs no such operation.

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

## Roll back the 0.4.18 lifecycle handoff repair

First leave RAM Tetris OFF after a reviewed healthy static restoration, then
redeploy exact accepted v0.4.17 commit
`a1e72a287c3d2b22fc2dcbc26e0310a79e8c2b6b`. Version 0.4.17 does not serialize
an authenticated handoff against RGB writes and can latch a legitimate
Quickshell zero-owner interval, so do not perform a shell-restart acceptance
test with RAM Tetris active after rollback. Never clear an existing failure
latch merely to complete rollback.

## Roll back the 0.4.19 independent lifecycle

Rollback must reverse ownership before restoring v0.4.18. First perform the
normal bounded stop of `omarchy-plus-openrgb-presets.service`. It must publish
the authenticated writer stop, release the writer singleton, stop its verified
SDK when required, record `clean-stopped`, and leave no lifecycle, inhibitor,
monitor, or writer process. If the stop times out or a failure latch appears,
do not continue and do not force a QML owner to start beside it.

After zero ownership is proven, disable the unit without starting or stopping
anything else, redeploy exact v0.4.18 commit
`b9210192369e3898b397c315f41b96a4751232e6`, and allow its restored QML service
to become the sole lifecycle owner. Remove the staged unit only after it is
disabled and inactive, then reload the user manager. Preserve active preset,
RAM Tetris preference, failure latch, and all Effects profiles. An ON preference
with the historical latch remains ON with zero writers after rollback.

## Roll back the 0.4.20 journal-window correction

Perform the normal bounded service stop and require a `clean-stopped` boundary
with no lifecycle or writer owner. Then redeploy exact v0.4.19 commit
`0d34d294d092f93433d527d6a4375725b47ba57f` and start it only through the
existing user-service procedure. Version 0.4.19 resets the kernel-journal
baseline between discovery retries, so do not treat its startup or resume gate
as proof that earlier retry-window communication errors were absent. Preserve
the active preset, Tetris preference, historical failure latch, and Effects
profiles throughout rollback.

## Roll back the 0.4.22 Lighting Recovery interface

Redeploy exact published v0.4.21 commit
`c9481f0780055e2045a67772467a7f0caae3ee16`. This removes only the classified
recovery helper, expandable diagnostics, and Recover-button UI. It restores
the historical reviewed-clear CLI behavior, so do not use that command as a
substitute for the v0.4.22 safety protocol. Preserve the active preset,
preference, failure latch, lifecycle service state, and any retained recovery
evidence. Rollback does not start or stop the service, SDK, Quickshell, RAM
Tetris, Effects, or a preset.

## Remove

First request the bounded stop:

```bash
systemctl --user stop omarchy-plus-openrgb-presets.service
```

Then verify that the unit is inactive, the service-state record is
`clean-stopped`, and the lifecycle and writer locks are free. If any check
fails, stop the removal. After a clean stop, remove ownership in this order:

```bash
systemctl --user disable omarchy-plus-openrgb-presets.service
/usr/bin/rm -- ~/.config/systemd/user/omarchy-plus-openrgb-presets.service
systemctl --user daemon-reload
omarchy plugin remove io.github.ol4vr.openrgb-presets
```

Removing the checkout first would remove the unit's executable and stop guard
while they are still needed. The ordered procedure leaves no enabled or staged
unit and no competing lifecycle owner. The official Effects Plugin binary,
saved profiles, current preset, RAM Tetris preference, and persistent failure
latch remain in place.

## ST100 rainbow limitation

The ST100 starts its internal animated rainbow after a USB power cycle, but
OpenRGB exposes only Direct mode and cannot return it to firmware animation.
Animated Rainbow therefore uses a static eight-color base strip and compensated
logo color. Spectrum Wave drives the ST100 through the Effects Plugin.
