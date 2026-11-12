# Integration audit — 2026-11-12

Pinned AxeForge: `e84c651c36a4b5f91c537577704245ded032592d` (v1.4.10). All source changes are applied by `apply.py`, the original patchers and `integration-hardening.patch`; new pure helpers are in `overlay/main/asic/rx_frame.h` and `overlay/main/stratum/v1_wire.h`.

Fixed: duplicate/unknown V1 acknowledgements no longer increment legacy accepted/rejected/work counters; uint32 JSON IDs are parsed without cJSON valueint saturation; fractional/nonfinite/out-of-range IDs rejected; reconnect occurs before submit ID reuse. Source session wallet/worker and BTC context are retained independently of mutable settings. Jobs and authorizations are JSON escaped, and real cJSON allocation failure injection confirms partial trees never produce requests without params. Failed transport writes cause reconnect and never replay a candidate to another pool.

Job templates are allocated before replacing published memory; failed copying/building skips work safely. `clean_jobs` is consumed atomically with its copied template. Empty extranonce1 uses an explicit subscribe state; invalid hex and fractional extranonce sizes are rejected. Actual `work::build` tests cover short extranonce counter masking and header identity.

ASIC Work is published before UART transmission, using the unchanged stock slot mapping. `pause(true)` and final send share a mutex: pause waits for an existing send and invalidates all Work before returning; a builder checks pause/power/readiness inside that same barrier. No register values, baud rates, power/temperature thresholds, frequency/voltage limits or partition layouts changed.

Counter baselines now have one writer; reset requests cross tasks atomically. Nonphysical count deltas are logged and excluded before smoothing/tuner windows, and native archive sees missing/stale counters as gaps. This fixes an observed software reset race but does not prove that every possible source of the earlier 3933.24 TH/s sample has been isolated without raw device traces.

UART RX previously flushed all queued bytes after a partial read or preamble error and accepted responses without checking CRC. The new bounded collector retains fragments across timeouts, slides over noise/bad CRC, and preserves following valid frames. ASIC discovery and result reading have exclusive RX ownership during recovery. No new ISR work or dynamic RX allocations. The CRC rule is independently corroborated by the official Bitaxe implementation: [asic_common.c](https://github.com/bitaxeorg/ESP-Miner/blob/2492d00571a179dc833eefce2c53290edbb359bc/components/asic/asic_common.c), [crc.c](https://github.com/bitaxeorg/ESP-Miner/blob/2492d00571a179dc833eefce2c53290edbb359bc/components/asic/crc.c), [BM1370 wire layout](https://github.com/bitaxeorg/ESP-Miner/blob/2492d00571a179dc833eefce2c53290edbb359bc/components/asic/bm1370.c). Evidence hashes are in `uart-reference-evidence.json`.

All compact target hits are offered to their originating session before statistics. Only a known originating BTC host and a target within Bitcoin mainnet pow limit enter the BTC candidate journal; all-network target hits still submit as shares. A pool-provided target match does **not** establish consensus validity or chain inclusion; this firmware has no full validating Bitcoin node. Unknown SHA-256d pool compatibility, payout template enforcement and regional endpoint behavior need explicit testing.

## Executed integration checks

- Actual upstream host suite forced rebuild with ASan/UBSan: **157 checks, 0 failed**, including `work::build`, Genesis/hash/coinbase, payout/SV2/PMBus safety vectors. Uses the upstream default host board fixture, not physical Gamma.
- `tests/v1_wire.cpp`, ASan/UBSan + real cJSON: PASS; ID boundaries, escaping exact credentials/job bytes, no injected line, allocation failure at 60 positions.
- `tests/uart_rx.cpp`, ASan/UBSan: PASS; 11-byte BM1370 and 9-byte BM1397 layouts, every partial split, timeout retention, noise, overlapping preamble, every single-bit payload/CRC corruption, back-to-back intact frames. These are synthesized streams corroborated by official protocol implementation, not captured hardware frames.
- Clean pinned Git worktree reconstruction: exact byte matches for hardened integration sources and helper headers. Final complete overlay/Guardian reconstruction is recorded by the main build report.

## Limits

No BM1370, UART hardware, real pool socket/TLS server, OTA operation, power-loss or long-duration FreeRTOS stress test was available. Pure helpers plus native ledger tests do not prove the full live send/receive lifecycle. The ASIC's finite slot identities inherently cannot distinguish arbitrarily delayed old UART responses after slot reuse; candidate software hash verification remains in place. Header exhaustion tracking covers the current equivalent template, not a persistent global map across reboots or arbitrary template cycling. Hardware tests must verify CRC behavior, init/recovery and UART timing before an unattended release claim. `job_sent` measures return from the driver queue operation, not physical hashing start or UART drain completion.
