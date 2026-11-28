# Firmware engineering rules

- Review the actual extracted and patched firmware sources, not just patch generators.
- Follow deep modules and narrow interfaces. Keep recovery state owned by the tuner, hardware constraints owned by the protection layer, and persistent journal storage behind a bounded interface.
- Review module cycles, tangled dependencies, leaked fields and shallow wrappers. Fix root causes, not symptoms or suppressions.
- Use deslop-please (https://github.com/deterministic-machines/deslop-please) only for supported languages; verify the Python/JS/TS port and pin its version before CI integration. For C/C++, use Cppcheck and Clang-Tidy with the actual build configuration.
- Never bypass temperature, voltage, current, power or ASIC protections. Revalidate saved operating points before resuming tuning; use bounded retries and backoff.
- Exclude credentials, pool secrets and Wi-Fi passwords from journals. Bound memory and flash writes.
- Run native regression, fault injection, ASan/UBSan where supported, WebKit download checks, and OTA structure and SHA256 verification. Do not disable tests or suppress findings to obtain a passing build.
- Report actual commit and CI evidence; distinguish compilation, simulation and physical testing. Do not claim physical testing without evidence.
