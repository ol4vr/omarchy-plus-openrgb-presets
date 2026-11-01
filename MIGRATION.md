# Static Edition migration and rollback

This is a prepared procedure, not authorization to operate production. Service
start/stop, deployment, unit reconciliation, or hardware writes require a
separate owner-approved task.

## Immutable v0.4.45 archive

Before replacing production, require the service to remain failed/stopped with
no lifecycle, SDK, listener, preset helper, writer, or relevant lock owner.
Require the unchanged failure latch and lifecycle boundary checksums already
recorded for `LR-9845F46B583CA2C1`, four readable SPD5118 endpoints, and the
exact installed package and executable.

Create one new protected directory named with UTC time and the v0.4.45 commit.
Populate it without changing the live state with:

1. a complete Git bundle whose HEAD is
   `388dd9c2fd118722c32b24565e41465ab2412be0`;
2. a byte archive of the clean installed plugin tree;
3. the installed and source user units;
4. `manifest.json`, OpenRGB package/version and executable checksum records;
5. the original failure latch, lifecycle boundary, RAM/Tetris preference, and
   all retained recovery evidence; and
6. `SHA256SUMS` covering every archived file.

Verify the bundle as a complete history and verify every checksum from a
different working directory. Make archive files read-only. Never move, edit,
or delete the original incident files to create this copy.

## Stopped-service migration

After Static Edition is published at one immutable commit and BASE pins that
exact commit:

1. repeat the stopped-service, zero-owner, package, SPD, kernel, latch,
   boundary, and archive checks;
2. reconcile only OpenRGB Presets to the published Static Edition commit;
3. run the reviewed `reconcile-static-service install`, which installs the
   byte-identical Static Edition user unit, reloads the user manager, and
   enables the unit without starting it;
4. verify the checkout is clean/detached, the manifest and unit are exact, and
   no removed Tetris/recovery runtime file exists in the active checkout;
5. preserve `ram-tetris-enabled`, the historical latch, boundary, journals,
   and evidence unchanged as ignored archival state;
6. preserve a valid selected preset when it is one of the twelve names;
   otherwise let the new source default to Electric Sunrise; and
7. leave the service stopped for a separately authorized first-start test.

The first authorized start is one attempt. Acceptance requires the exact
package/binary and source identities, one owned SDK listener, seven accepted
controllers, four readable SPD endpoints, ready Effects, the selected preset,
the expected static DIMM color (or static black when RAM Lighting is OFF), and
no relevant new kernel fault. A failure leaves the historical v0.4.45 evidence
untouched and does not trigger a recovery workflow or retry.

## Fresh BASE restoration

BASE must pin the published Static Edition commit, install the exact
`openrgb-hugin 1.0rc3-3.2` package contract, restore the reviewed detector and
Effects configuration, install/enable only the Static Edition unit, and default
the selected preset to Electric Sunrise. It must not restore `ram-tetris`,
Tetris preferences, Tetris services, service guards, or lighting recovery
commands. Missing RAM Lighting preference intentionally means ON.

## Source rollback

Rollback does not start OpenRGB and does not clear or acknowledge any latch:

1. require the Static Edition service stopped and all owners absent;
2. verify the protected v0.4.45 archive and bundle checksums;
3. reconcile the plugin to exact commit
   `388dd9c2fd118722c32b24565e41465ab2412be0`;
4. restore the archived v0.4.45 unit byte-for-byte and reload the user manager;
5. verify the original latch, lifecycle boundary, and evidence still match
   their protected checksums; and
6. leave the service stopped. Any return to the old runtime requires its
   previously reviewed recovery/start procedure and separate authorization.

The new `ram-lighting-enabled` preference may remain as inert state during a
rollback. The old runtime does not consume it.
