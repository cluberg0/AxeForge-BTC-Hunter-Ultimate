# TURBO1000 UNLOCK — TEST REPORT

2026-11-16 UTC. Программные проверки/сборка PASS; физические Gamma601/iPhone,24/7 и прирост полезной работы НЕ ПРОВЕРЕНЫ. Устройство не прошивалось.

## Образ

`axeforge-gamma-BTC-HUNTER-TURBO1000-UNLOCK.bin`; descriptor `1.4.10-hunter-TURBO1000-UNLOCK`;1934992байт; stock OTA slot4194304; запас2259312байт(53.86%).

SHA-256: `77ee3aff42c1067e31e4b35e965688188553b78d888ca63d8ad01f23cf5eac93`.

Gamma601/ESP32-S3/один BM1370. AxeForge1.4.10/e84c651c36a4b5f91c537577704245ded032592d. ESP-IDF5.3.2/9d7f2d69f50d1288526d4f1027108e314e8c879f, GCC13.2.0_20240530. Code commit531125a; исходники/инструкции и логи в финальном Git commit веткиturbo1000-unlock.

`bash scripts/build.sh` exit0,0compiler warnings/errors. Gamma/BM1370/count1, stock800/1300, critical68/80 ASIC и85/100 VRM, experimental software profile1000 проверены. Штатный GPIO/VRM profile, OTA Guard, bootloader source/defaults и таблица разделов не изменены; partition-table.bin SHA совпал с предыдущим релизом. App OTA не записывает bootloader/partitions/NVS.

Image/chip/version/board tag/segments/bounds/XOR/appended SHA/no trailing bytes и esptool checksum/hash PASS. SHA совпал у hashlib/sha256sum/OpenSSL. Manifest входных исходников одинаков до/после и соответствует текущему upstream. Чистый pinned checkout+весь apply.py/patch_unlock.py воспроизводит338файлов побайтово;4UI generators согласованы. Межмашинная побайтовая идентичность BIN не заявляется(IDF timestamp/paths).

## Выполненные тесты

| Критерий | Результат |
|---|---|
| Штатный AxeForge |157checks/0failed,ASan/UBSan, host fixture|
| Реальные native gates |PASS compiled production gates: available=true,800→1000 после unlock,1300mV/board hard power неизменны; Weak PSU возвращает800 без потери разрешения|
| Реальные API guards |PASS900MHz/30W после unlock; stock>800/25W,1001MHz,1301mV,31W отклонены до изменений; typed confirmation проверяется до settings mutations|
| Автопоиск |PASS production apply/climb/confirmation/phase with deterministic hardware measurements: до1000,12.5MHz lattice, повторные окна, минимальное стабильное напряжение, power/error wall,1300 bound, откат/failed-write ordering/stock800|
| Реальный Turbo module |PASS ASan/UBSan: PSU30/6→25.5 и40/8→30, bigger PSU не превышает30; voltage derating, sensor/session/ACK/error/thermal/watchdog guards, best-score не выбирает более высокую частоту с худшей работой, NVS reserve/map16, manual stop race|
| NVS/boot/recovery |PASS injected backend: PSU/search config round-trip, разрешение без auto-arming, отказ на invalid/corrupt config/write failure; saved>800 runtime возвращается в525/1150, hard-rating guard и Safe Recovery reset. Штатный settings.overclock использует прежний NVS key|
| PLL/board |PASS7201 differential original-solver vectors;16ступеней800..1000 в принятой12.5MHz сетке; driver ramp/failure; stale/NaN power reads не обновляют freshness|
| Прежние модули |PASS Hunter/Intel/Guardian, ACK/session/OOM/UART/CRC/duplicate tests, network reconnect/counters/services. Их production source не менялся|
| Bitcoin target |PASS10007 independent exact compact-target reference vectors + Genesis/boundaries|
| API/JS/OTA |PASS5native runtime JSON/schema/source guard contracts, upstream API/flasher contracts, existing OTA failure harnesses/image negative tests, JS syntax|
| Chromium/WebKit |PASS5widths/4tabs, native limits/unlock/lock, PSU40/8→30, explicit start/configure/stop/refusal, previous graphs/profiles/2FA/Benchmark/Guardian;0JS errors. Mock server, Linux WebKit — не Safari iPhone|
| Stack/размер |Xtensa static stack frames и IDF size report получены; не runtime high-water/heap soak proof|

Команды: `AXEFORGE_HOST_SYSROOT=/workspace/toolchains/host-sysroot bash scripts/test.sh`; `python3 tests/browser.py`; `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 BROWSER=webkit python3 tests/browser.py`; активированный IDF5.3.2 → `bash scripts/build.sh`; `python3 scripts/stack_report.py`. Локальные sysroot/skip flag специфичны облачной среде, не нужны владельцу iPhone.

Логи: reports/unlock/TESTS.log,BUILD.log,REPRO.log,browser-*-final.log,build-metadata.json; reports/size.txt,target-stack-usage.txt,image-info.txt,build-inputs.*.json. Ранние browser failure выявили реальный конфликт form-scoped имени turboStart/turboStop; исправлено window-qualified вызовами. Ранее сохранённые недоступный Gamma envelope/25W guards устранены в конечной цепочке патчей.

## Политика питания и ограничения

- User cap<=30W; отдельно native hard board40W/cutoff46W не повышены. Программный experimental профиль1000 не является физической характеристикой или подтверждённым запасом Gamma.
- Бюджет=min(user, min(declaredW,5V×A)−max(2W,10%)−1.5W, min(A−0.5A,6.5A)×min(VIN,5V)−1.5W). При неизвестном PSU/VIN<4.95/ASIC>=62/VRM>=70 дополнительно−10%. При30W/6A/нормальных условиях25.5W;40W/8A —30W. Фиксированного25W в TURBO нет.6.5A — программный исследовательский потолок, не паспортный предел платы.
- TPS546 Pout+штатные5W оценивает всю плату; остаточный запас1.5W не заменяет калибровку. Номинал БП заявляет пользователь, ESP32 не умеет проверить надпись на корпусе. Нельзя вводить больший БП вместо физической замены.
- Стоковые68/80°C ASIC,85/100°C VRM и аварийные защиты сохранены. Исследовательские65/75°C, VIN4.85..5.35, Iout<=24A и fresh power/sensors строже. Они остаются программной консервативной политикой. Монитор учитывает паспортную мощность/ток при unlock на любой частоте; budget окна обновляется каждую секунду.
- До поиска нужны30min fresh stable stock point,>=100ACK, V1 failover, tuner Locked. Каждое окно Neff>=30; repeat/voltage trials могут занимать много часов. Недостаток accepted work завершает поиск. Hashrate ranking=стабильный ASIC counter rate с долей ACK, accepted difficulty work/estimate отдельно; увеличение частоты не равно улучшению работы.
- Применённая PLL — конфигурация после команды драйверу/расчёт делителей, не физический readback или измерение частоты/lock. ДробныеPLL сохранены как округлённые uint16метки(813→812.5); аппаратно достижимая1000MHz и выбранное напряжение не подтверждены.
- Unlock/PSU/user cap сохраняются, corrupt config fail-closed; поиск не auto-resume. Boot при сохранённом>800 и выключение режима возвращают525/1150; прочие пользовательские настройки остаются. Физический OTA/power-loss/NVS retention/thermal/PSU fault/heap soak/rollback ещё требуют устройства/стенда.
- Измеренный программный delta BIN:+9920байт относительно TURBO1000(1925072). Backup SHA f05a28224dd6be99775bb27dd5d1ea78c3dc9d2928406d2a0161df1e35cc2757 проверен; предыдущий app также не аппаратно проверен у пользователя.
- Ожидаемый эффект: доступный расширенный диапазон/PSU-derived limit и более обоснованный выбор точки без конкурирующего управляющего task. РостTH/s/полезной работы/вероятности BTC не измерен; сравнение на одинаковом Gamma не выполнялось. INSTALL-IPHONE.md и HARDWARE-TEST-PLAN.md содержат дальнейшую установку/откат/физические проверки.
