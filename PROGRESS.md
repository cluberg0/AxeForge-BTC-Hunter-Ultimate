# TURBO1000 UNLOCK

База12b8cbf, веткаturbo1000-unlock; новых агентов нет. Scope только overclock/config/PLL/tuner/API/UI.
Выполнено: software experimental Gamma profile1000 отдельно от stock800, persistent settings.overclock+typed OVERCLOCK, PSU config NVS validated on boot, default no forced clock/experiment. Manual API>800, user<=30W/max1300; one tuner phase, PLL12.5MHz lattice/rounded labels, voltage minimum+repeat measurements+ACK-adjusted hardware score/map. Safe boot/recovery525/1150 for unvalidated extended clocks; disable returns stock.
Power: user<=30, declared PSU watts/amps,10%(>=2W) reserve,0.5A reserve,1.5W input-estimate margin, continuous voltage/thermal/unknown derating; no fixed25W in Turbo. Default30W/6A gives25.5W;40W/8A gives30W before dynamic derating. Original hard limits/bootloader/partitions unchanged.
Проверки: previous iteration full host/ASan/UBSan/5API+JS, Chromium/WebKit PASS; final confirmation running after dynamic budget/PSU hard-rating guard. Native gates and API900/30 vs1001/1301/31 refusal; boot/NVS corruption; best-score preference and PLL7201 covered. Clean apply338files identical before last small hook; recheck needed.
Осталось: финальные build/tests/repro results, SHA, release docs/package, final Git commit. No physical Gamma/iPhone tests, no measured gain, device not flashed.
