# Ultimate2.0 TURBO1000 — результаты

2026-11-13 UTC. Сборка и перечисленные программные проверки PASS. Физические Gamma601/iPhone,24/7 испытания и измерение прироста НЕ ВЫПОЛНЯЛИСЬ. Устройство не прошивалось.

## Образ и воспроизводимость

- `axeforge-gamma-BTC-HUNTER-ultimate-2.0-TURBO1000.bin`; app version `1.4.10-hunter-2.0-TURBO1000`.
- Gamma601/ESP32-S3/один BM1370; AxeForge v1.4.10/e84c651c36a4b5f91c537577704245ded032592d; ESP-IDF v5.3.2/9d7f2d69f50d1288526d4f1027108e314e8c879f; Xtensa GCC13.2.0_20240530.
- Размер1925072байт; OTA slot4194304байт; запас2269232байт(54%). SHA-256: `f05a28224dd6be99775bb27dd5d1ea78c3dc9d2928406d2a0161df1e35cc2757`.
- `bash scripts/build.sh` exit0, финальный журнал reports/turbo/BUILD.log:0errors/0warnings. Ранний compile failure из-за misleading indentation исправлен. Промежуточный неуспешный образ не является релизом.
- Board generation Gamma/BM1370/count1, stock800MHz/1300mV/ASIC68°C/VRM85°C, неизменные partitions/defaults/board/OTA Guard sources проверены build script. Новое runtime расширение частоты открывается только active manual TURBO.
- Независимая проверка ESP image: chip/version/board marker/segments/bounds/XOR/appended SHA/no trailing bytes; esptool image_info checksum/hash valid. Python hashlib, sha256sum и OpenSSL дали одинаковый файловый SHA. ELF содержит Turbo и прежние native модули; weather/mempool/price workers отсутствуют.
- Manifest входных исходников совпадает до/после сборки и с текущими исходниками. Чистый pinned checkout+вся цепочка apply.py/patch_turbo.py воспроизводит338файлов побайтово. UI из prepare_ui.py/hunter_ui.py/v2_ui.py/turbo_ui.py совпадает с overlay и встроенным web ресурсом.
- ASIC драйвер/монитор изменены патчами, bootloader source/config и flash layout сохранены. Бинарная таблица разделов имеет тот же SHA, что релиз2.0. OTA комплект содержит только app для прошивки; debug ELF/map/config не предназначены для OTA.
- Идентичный BIN на другой машине/дате не заявляется: IDF включает время/пути. Пин SDK/upstream/dependencies и manifest фиксируют процесс и входы; исходный ZIP содержит полный patched upstream и все генераторы.

## Выполненные проверки

| Проверка | Реальный результат |
|---|---|
| Штатный AxeForge host suite |157checks/0failed, ASan/UBSan; host fixture, не устройство|
| Native Hunter/Intelligence/Guardian/math |PASS ASan/UBSan, Wall/Wextra/Werror; target/ledger/archive/settings/benchmark/fault cases сохранены|
| Stratum/UART/counters/network |PASS real cJSON/OOM/session/ACK, noise/partial/CRC/duplicate frames; production counter wrap/reset/visible errors, reconnect/backoff/service wakeup tests|
| Target |PASS10007 independent compact-target reference vectors, Genesis/zero/sign/overflow/PoW boundaries|
| PLL |PASS7201 точных сравнений с оригинальным solver из pinned upstream;800..1000 шаг12.5 выражаются точно; production ramp/partial failure/recovery|
| Production tuner |PASS extracted actual apply/climb/run_turbo_phase with injected measurements: постепенный1000 ceiling, power stop,1300mV ceiling, последний проверенный режим, возврат к786/1170 без изменения cfg; failed-write order; stock800 сохранён|
| Production Gamma board |PASS partial PLL failure отражает частичный programmed clock; stale/NaN VIN/Pout/Iout не продлевают power freshness; stock cap/off guards|
| Turbo module/API |PASS реальный модуль с fake hardware/NVS/HTTP: явное подтверждение, ranges/preconditions, no forced clock,30→25/23 reserve, stale sensor/session/error/thermal/watchdog, insufficient ACK,16-point map/недостаток NVS, stop vs hold, no armed persistence|
| API/JS/image failures |PASS5native endpoint schemas/source guards/runtime JSON, upstream API/flasher contracts, API/OTA failure harnesses, JS syntax, image negative cases|
| UI |PASS Chromium+Linux WebKit:4вкладки/подразделы,5ширин,13шкал,навигация/графики/профили/2FA/recovery,ручное TURBO подтверждение/start/stop/refusal,Benchmark/Guardian;0JS errors. Mock APIs, не реальный ASIC/Safari iOS|
| Target stack |Xtensa stack frames получены: tuner_task304, climb208, measure112, turbo::get736байт. Это отдельные static frames, не полный call-chain/high-water proof|

Команды: `AXEFORGE_HOST_SYSROOT=/workspace/toolchains/host-sysroot bash scripts/test.sh`; `python3 tests/browser.py`; `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 BROWSER=webkit python3 tests/browser.py`; IDF5.3.2 activated → `bash scripts/build.sh`; `python3 scripts/stack_report.py`. SYSROOT/skip flag нужны только данной облачной среде; обычный Linux использует установленные зависимости. Точные результаты: reports/turbo/TESTS.log, BUILD.log, REPRO.log, browser-*-final.log; reports/target-stack-usage.txt и build-metadata.json. Удалённый GitHub Actions не запускался.

## Ограничения и сравнение с2.0

- Запрос мощности18..30W — верхний параметр, не цель. Резерв3W; Gamma TPS546 даёт Pout+5W, не калиброванный вход всей платы. Поэтому effective budget<=25W, при VIN<4.95V/ASIC>=62°C/VRM>=70°C/PSU unknown<=23W; плохие условия останавливают эксперимент. Реальная безопасность30W не подтверждена и30W нагрузка не разрешается этим релизом.
- Stock hard protections не подняты. TURBO добавляет stricter65°C/75°C, VIN4.85..5.35V, Iin<=5.5A/Iout<=24A, sensor freshness<=3s, fan>=600RPM и heartbeat<=10s. Iin вычислен из оценки мощности. Частота PLL расчётная/запрограммированная; физическая частота и lock ASIC не измерены.
- До запуска нужны30min свежей стабильной точки<=800MHz,100ACK, V1 failover и штатный tuner Locked. Каждая ступень120s прогрев+300s измерение, Neff>=30. При высокой сложности пула эксперимент может завершиться из-за недостатка данных; короткие share windows не доказывают прирост.
- Карта16точек сохраняется отдельно af_turbo; loaded history не применяется автоматически. За одну сессию допускается проверенный lower fallback; при аварии/ручной остановке/неопределённом PLL — возврат к исходной stock точке или shutdown при неудаче. Активность и экспериментальный разгон не сохраняются в settings.
- Настройки/NVS/OTA проверены по исходникам и failure harnesses. Реальное сохранение Wi-Fi/wallet/pools, OTA rollback/probation, поведение при brownout/OOM/thermal faults требуют устройства/отдельного стенда; мы не проводили опасные физические воздействия.
- Измеренный размер приложения+19376байт относительно2.0(1905696байт). Backup2.0 SHA:`bb59cc8762bc1e9962c6c96b093321a5b7a9caff5834e9f35962f4c001651f28`. Предыдущий app программно проверен, не физически подтверждён для пользователя.
- Ожидаемый эффект: возможность осторожно исследовать дополнительные рабочие точки при сохранении stock режима и защита от перечисленных write/freshness/stop ошибок. Прирост TH/s, полезной работы/сутки, вероятности блока и безопасность1000MHz не измерены. Сравнение производительности с2.0 при одинаковых настройках не выполнялось без Gamma. План: HARDWARE-TEST-PLAN.md; OTA/откат: INSTALL-IPHONE.md.
