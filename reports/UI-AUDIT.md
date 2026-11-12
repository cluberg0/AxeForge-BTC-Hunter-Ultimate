# UI audit and browser verification

Browser checks use fixture APIs, not a connected miner. They exercise the actual generated HTML and JavaScript with real browser engines; they do not establish ESP32 hardware safety, actual NVS survival, production authentication correctness, or iPhone Safari behavior.

## Repairs

- Session headers and OTP prompts are restricted to same-origin requests. Cancelling login no longer triggers three repeated prompts through GET retries. OTP transport failures remain recoverable; duplicate requests and late replies after cancellation are guarded.
- Refused OTA Guard, automatic-update and worker-toggle writes restore the displayed saved value.
- Native cooling/rollback writes are serialized, buttons disable during mutation, and polling restores their state. Presets still only fill fields before an explicit settings save.
- Backup, restore and display-page requests handle transport/HTTP errors. Restore is serialized and backup object URLs remain alive long enough for iOS download handling.
- Corrupt stored color/curve arrays cannot stop initialization. Native telemetry rows must have the complete timestamp/value/network/count/interval schema.
- Background animations pause when the document is hidden or the browser exposes data-saving mode. Existing reduced-motion and manual-off support remain independent of tab transitions.
- Pool suggestions require matching V1 transport, verified payout, at least 20 observed blocks, at least 100 accepted shares, at most 1% rejections, and no failed/missing submits. Suggestions never change configuration.
- A timing-test suggestion requires non-overlap of native approximate 95% intervals and comparable rejection fraction. One trial remains explicitly uncertain and requires repetition.
- The older energy card no longer presents upstream instantaneous-rate lottery estimates. Its BTC odds now use the same accepted-work Hunter calculation, difficulty/network/sample checks, and no-guarantee semantics as the Hunter card.
- Coin templates explicitly require the operator to check the endpoint algorithm, transport and payout-network documentation. They do not claim to verify arbitrary pools or disable payout checks.

## Commands

```
python prepare_ui.py
python hunter_ui.py
python -m py_compile prepare_ui.py hunter_ui.py tests/browser.py
python tests/browser.py
PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 BROWSER=webkit python tests/browser.py
```

JavaScript script blocks are also validated with `node --check`. Regenerating both stages must leave `overlay/main/web/index.html` byte-identical.

Playwright 1.62.0; system Chromium 156.0.8078.79; Playwright WebKit 26.5 (build 2336). For this restricted non-root environment, missing runtime dependencies were downloaded from the official Debian trixie repository and extracted into `/workspace/toolchains/browser-sysroot`; library symlinks were added to the local Playwright bundle. WebKit's host preflight still incorrectly reported `libGLESv2.so.2`; skipping that preflight permits the actual engine and all assertions to run. No browser feature assertions are skipped.

The suite covers Hunter states, start/stop/refusal, all 13 data series, implausible hash-rate exclusion, monthly data, CSV download, empty history, cooling and rollback independence, refused saves, duplicate native saves, profile staging, the four tabs and four system subpages through clicks, widths 320/375/390/430/768, OTP cancellation/transport recovery, cross-origin header isolation, failed screen switching, JSON backup/restore, movement of all four backgrounds on the same open page, reduced motion, manual off, hidden-page pause, and uncaught JavaScript exceptions. Screenshots are under `dist/screenshots/` for each engine.

## Limits

- Playwright WebKit on Linux is not physical iPhone Safari or its Low Power Mode. Safari does not expose a reliable Low Power Mode API; manual motion control and reduced-motion remain available, and iOS may throttle animations itself.
- ULTIMATE adds all 13 colored physical side scales aligned with the plot in a horizontally scrollable graph container. The plot retains a readable minimum width; screenshots show left axes, plot and right axes. Page-level overflow remains prohibited.
- Coin templates are configuration storage, not verified support for arbitrary BTC/BCH/DGB/SPACE/FB/XEC pools. Automated network-specific address and Stratum compatibility verification remains unsupported; native payout enforcement remains unchanged.
- Fixtures do not simulate every production API, USB/OTA transfer, or every possible original button action. No real miner was accessed.

ULTIMATE final verification: reports/browser-ultimate-chromium.log and reports/browser-ultimate-webkit.log; both complete exit 0, adding six-stage repeated Benchmark Lab, optional independent Guardian and all 13 side scales. Pool counters are explicitly per-slot since boot; current-host recommendations are withheld because identity across configuration changes is not proven.
