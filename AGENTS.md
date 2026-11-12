# Codex: AxeForge Gamma 601 native firmware handoff

Read `TASK.md` and `README.md` before changing anything. This package is a candidate source overlay, not a proven firmware release. User uses iPhone only for installation; final deliverable must be one OTA app `.bin` plus checksum and rollback instructions. Do not ask the user to install a compiler or use USB unless recovering from an actual failed boot.

- Upstream: https://github.com/IsSasoriDev/AxeForge, v1.4.10, commit e84c651c36a4b5f91c537577704245ded032592d. ESP-IDF 5.3.2, esp32s3, sdkconfig.defaults.gamma. GPL-3.0.
- `overlay/` holds modified native modules and final HTML; `apply.py` + `patch_hunter.py` patch the pinned upstream. `base-ui.html`, `prepare_ui.py`, `hunter_ui.py` are generator inputs; do not accidentally overwrite the final HTML with an older intermediate. Keep generated and source UI consistent.
- Build with `scripts/prepare.sh`, `scripts/test.sh`, `scripts/build.sh`; use `.github/workflows/build.yml` if local cloud build unavailable. Audit/repair scripts and upstream integration as necessary. Preserve modifications in tracked files; `upstream/` is disposable and ignored. Do not commit personal credentials or generated binaries to source.
- Never change flash partition table, erase NVS, disable safeguards, enable automatic external OTA, or broaden hardware clocks/voltage by default. Do not change wallet/pool defaults. All optional autonomous actions must be off by default and explicitly enabled. No unsupervised power experiments.
- A passing unit test or simulated browser is not evidence of physical validation. Do not claim real-device testing. Report exact commands, test outcomes, skipped checks and build SHA. Do not distribute a failed or unverified candidate as ready to flash.
