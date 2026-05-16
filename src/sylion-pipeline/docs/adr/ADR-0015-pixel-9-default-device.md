# ADR-0015: Pixel 9 as Default Provisioned Device (replaces Pixel 8 seed)

**Status:** Accepted
**Date:** 2026-04-19
**Author:** pixel-provisioning-council (v5.9.1 re-audit)

## Context

Finding PIX-1 (P1-10) identified the historical main issue of SYLION: the device provisioning subsystem hardcoded `"pixel8"` as the seed device identifier in `dashboard/db.py:1349`, while `pixel_provision.py:46` defined `EXPECTED_MODEL = "Pixel 9"` as the provisioning target. This mismatch meant:

1. The database was seeded with a `"pixel8"` device record on every fresh install.
2. `pixel_provision.py` queried for a device matching `EXPECTED_MODEL = "Pixel 9"` — and found none.
3. Provisioning silently failed or returned stale Pixel 8 data.
4. The `"unauthorized"` ADB state (device connected but not authorised for ADB debugging) was not handled — the code assumed the device was either fully authorised or missing.

This is described as the **primary historical issue** of the platform: the device pipeline appeared to work (no crash) but was never actually provisioning the correct device.

Options considered:
- **D1** — Keep Pixel 8 seed, change `EXPECTED_MODEL` to match (wrong direction — Pixel 9 is the target hardware)
- **D2** — Replace seed with `"pixel9"`, enforce `EXPECTED_MODEL`, add `"unauthorized"` state handler (chosen)
- **D3** — Make device model configurable via `config.yaml` with no hardcoded default
- **D4** — Remove the seed device entirely and require manual provisioning on first boot

## Decision

Three coordinated changes:

1. **Seed replacement**: `dashboard/db.py` seed record changed from `"pixel8"` to `"pixel9"` with display name `"Pixel 9"`. A migration step detects existing `"pixel8"` rows and upgrades them to `"pixel9"` with a `migrated_from_pixel8=True` flag preserved in the `metadata` JSON column.

2. **EXPECTED_MODEL enforcement**: `pixel_provision.py` raises `ProvisioningError` (instead of silently returning `None`) when the connected device model does not match `EXPECTED_MODEL`. The error is logged with the actual detected model to aid debugging.

3. **Unauthorized state handling**: ADB device state `"unauthorized"` is now explicitly caught. The provisioning flow returns a structured error `{"status": "unauthorized", "action": "accept_adb_prompt_on_device"}` instead of timing out or returning a generic failure.

## Consequences

### Positive
- Resolves the primary historical failure mode: fresh installs now provision the correct Pixel 9 hardware.
- `"unauthorized"` state surfaces a clear, actionable error message to the operator instead of a silent timeout.

### Negative
- Existing databases with `"pixel8"` device records require the migration step. If the migration runs against a database that has been customised (e.g., renamed device entry), the auto-upgrade may incorrectly reclassify it. Operators with non-standard device names should review post-migration.
- Hardcoding `EXPECTED_MODEL = "Pixel 9"` in source (option D2) means deployments using a different Pixel model (e.g., Pixel 9 Pro) still require a code change. Option D3 (config file) is deferred to v5.10.

### Neutral
- The `migrated_from_pixel8` metadata flag provides an audit trail for QA validation of the migration.

## Alternatives Considered

- **D3 (config-driven model)**: The correct long-term solution; deferred because it requires a config schema change and UI update that are out of scope for a patch release.
- **D4 (no seed)**: Would break `test_pixel_provision_*` tests that expect a seeded device record; rejected.

## References

- `dashboard/db.py` — device seed, migration step `migrate_pixel8_to_pixel9()`
- `pixel_provision.py` — `EXPECTED_MODEL`, `ProvisioningError`, `"unauthorized"` handler
- Finding PIX-1 in `FINDINGS_MATRIX_v591.md`
- `reports/pixel-provisioning-council/REPORT.md`
