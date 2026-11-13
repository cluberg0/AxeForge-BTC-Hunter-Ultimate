# ULTIMATE2.0 — TEST REPORT

Дата:2026-11-13 UTC. **Сборка/перечисленные программные проверки PASS. Аппаратные испытания NOT RUN.**

## Сборка и образ

- Gamma601, ESP32-S3, один BM1370. AxeForge1.4.10/e84c651, ESP-IDF**5.3.2**/9d7f2d69f50d1288526d4f1027108e314e8c879f, Xtensa GCC13.2.0_20240530.
- `axeforge-gamma-BTC-HUNTER-ultimate-2.0.bin`, версия `1.4.10-hunter-ultimate-2.0`.
- Размер**1,905,696байт**; stock app partition4194304; запас2,288,608байт. SHA-256:`bb59cc8762bc1e9962c6c96b093321a5b7a9caff5834e9f35962f4c001651f28`.
- `bash scripts/build.sh` exit0; `sdkconfig.defaults;sdkconfig.defaults.gamma`; generated Gamma/BM1370/count1, limits800MHz/1300mV/ASIC68°C/VRM85°C проверены.
- Image descriptor/version/chip/board tag/segments/bounds/XOR/appended SHA/no trailing bytes/ELF symbols/esptool image_info PASS. Отсутствуют Open-Meteo URL и Weather/Mempool/price worker symbols. Manifest source inputs до/после сборки совпал.
- Python hashlib, sha256sum и OpenSSL дали одинаковый файловый SHA. Резервный Ultimate1.0 прошёл checksum check; он ранее программно проверен, но не является подтверждённым аппаратным recovery image.
- Финальный build `reports/v2/BUILD.log` exit0, compiler warnings0. В предыдущих попытках исправлен отсутствующий cmath namespace; одна попытка отклонена защитой от изменения source inputs во время сборки. Непроверенные промежуточные app не экспортировались как результат.
- Чистый pinned checkout + вся цепочка apply/patch_v2 воспроизводит**334 файла** побайтово: REPRO.log. UI генераторы prepare_ui/hunter_ui/v2_ui дают тот же итоговый HTML.

## Проверки

| Проверка | Результат |
|---|---|
| Штатный AxeForge host suite |157 checks,0failed, ASan/UBSan; стандартная host board fixture, не физический Gamma|
| Прежние native модули |math/Hunter/Intelligence/Guardian PASS с ASan/UBSan и Wall/Wextra/Werror; сохранены ledger/target/archive/restore/benchmark/failure tests|
| Stratum wire/ASIC UART |PASS real cJSON ID/escaping/OOM, короткий extranonce, session/ACK invariants; синтетические partial/noise/back-to-back/CRC5/duplicate frames|
| Bitcoin target |10007 exact integer differential compact vectors + Genesis/границы/PoW limit PASS|
| Native network policy |active180s/standby900s, TCP-independent silence policy, capped2..60s backoff, immediate failover/30s failback/session change PASS|
| Production reconnect code |IO restart не обходит задержку, healthy session сбрасывает задержку до2s перед ожиданием, explicit config epoch skips wait PASS|
| Network event diagnostics |real module + cJSON: reconnects, per-slot TCP up/down, RX, errors, handler mean/max latency, 64-bit>UINT32 counters, stale active selection, UTC validation/write failure PASS|
| Production services |Farm ждёт explicit task notification; update checker/install только по запросу; price start не создаёт задачу; Guardian idle worker не делает HTTP, повторный manual request не пишет NVS PASS|
| Clock/Weather/Mempool |реальный service код с fakes: NTP servers/init/callback, init task self-delete, weather invalid/no refresh tasks, Mempool no worker, UTC persistence/unchanged-value no-write/NVS/mutex failure PASS|
| Hardware counter |production on_counter: uint32 wrap/reset/zero-dt/atomic reset request/error baseline/recovery; настоящие error deltas видны PASS|
| Tuner/Settings guard |реальный power_ceiling<=25W, saved cap не переписан, explicit30W rejected before mutations, unrelated settings accepted PASS|
| OTA/NVS/pause |production handlers/branches с allocator/socket/NVS fakes; drop/timeout/OOM/wrong size/no erase/no boot selection on error; deterministic send/pause concurrency PASS|
| API/static checks |штатный api_contract/flasher check +4 new endpoint schemas и реальный native JSON, stock api_guard/Origin/CSRF/2FA wiring PASS; node syntax/Python compile/generator byte equality PASS|
| Chromium/WebKit |оба exit0:320/375/390/430/768px, навигация/модалки/2FA/ошибки/backup fixture,13шкал/CSV/пропуски/анимация,18/22/25W staging/TURBO blocked, UTC save, two-series dashboard, Benchmark/Guardian PASS|

Команды: `AXEFORGE_HOST_SYSROOT=/workspace/toolchains/host-sysroot bash scripts/test.sh`; `python3 tests/browser.py`; `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 BROWSER=webkit python3 tests/browser.py`; `bash scripts/build.sh`; `python3 scripts/stack_report.py`. Все завершились exit0. WebKit реально работал после установки локальных runtime libs; пропущена только ошибочная host-library preflight, не assertions. Логи TESTS.log/browser-*-final.log/BUILD.log и screenshots приложены. Дополнительно compare counter запускался с кодом Ultimate1 из прежнего архива.

## Одинаковая последовательность для Ultimate1/2

На одной синтетической последовательности valid-counter reset и следующего error-counter read:

| Значение | Ultimate1 | Ultimate2 |
|---|---:|---:|
| ASIC GH/s после нормального окна |1431.656|1431.656|
| Valid counter units в окне |2000|2000|
| Ложные error units после reset |4294967247|0|
| Размер app |1901968|1905696|
| Static DIRAM |176427|176683|

`identical-counter-comparison.log` получен компиляцией реальных функций обеих версий с одинаковыми входами. Это доказывает исправление reset/underflow accounting. Оно не доказывает причину конкретного ранее наблюдавшегося3933.24TH/s, для которой нет raw trace. Реальные error counts не фильтруются; недостоверные valid-rate samples логируются и не загрязняют историю/tuner.

Flash delta+3728байт (~0.2%); static DIRAM+256байт. Linker DIRAM176683/341760, остаток165077; отдельное IRAM window16383/16384 не равно runtime free heap. Целевые stack frames записаны в target-stack-usage.txt; это не измерение полного call-chain/RTOS high-water. Фоновые weather6144B internal, Mempool8192B PSRAM и price8192B PSRAM stacks больше не создаются; NTP init3072B завершается после запуска SNTP. Реальное количество свободного heap/PSRAM на майнере не измерено.

## Сохранённые условия и пределы

Побайтовое сравнение с Ultimate1 подтвердило неизменность15 ключевых файлов: partitions/default configs/Gamma board, monitor/board_bitaxe, settings defaults/read, OTA Guard, ASIC driver/header, native Hunter/Intelligence и work builder. Точный список/хеши — build-metadata.json. Изменён только программный tuning ceiling25W, а не штатные hardware hard cutoffs. Нет второго freq/voltage controller, изменения register/baud или автоактивации TURBO. Adaptive Silicon Map остаётся компактным набором текущей/предыдущей проверенной точки; stock tuner применяет fallback только безопасно. Watchdog/self-test/PSU protection не заменялись.

Wi-Fi, кошелёк, worker, pools и сохранённые настройки NVS не стираются app OTA. UTC хранится в новом af_clock; старый city сохранён, но погода больше не определяет timezone. Для Уссурийска указать600мин. Сохранённый cap30W остаётся в NVS, effective auto tuning cap25W; для повторного сохранения/импорта30W надо выбрать допустимый cap<=25W. Профили не применяются при открытии страницы.

Удалены Weather/Mempool/price/automatic update polling. NTP, уведомления о реальных событиях, ICMP diagnostics, manual farm/Guardian/OTA и локальные API остаются. Price-on/auto-update preferences сохраняются для совместимости, но не запускают отключённые действия; ручной tariff/energy учёт сохранён.

- Физического Gamma601 нет. Реальная OTA/rollback/iPhone Safari, UART/CRC на железе, VIN/температуры/PSU, free heap/task high-water,24/7 leak/stability и full live V1/TLS/SV2 lifecycle **NOT RUN**.
- Причина конкретного idle сообщения без полного timestamped лога и сетевого capture не доказана. Исправлены подтверждённые source defects/policies: одинаковый idle threshold standby/active, backoff reset on mere TCP connect и bypass по IO restart. TCP keepalive проверен сборкой/API; фактические disconnect deadlines зависят от TCP/сети и требуют стенда.
- HTTP priority3 ниже Stratum5/ASIC12; GET diagnostics не вызывает сетевые операции и не берёт pool IO mutex. Это уменьшает конкуренцию, но не доказывает отсутствие любой задержки в shared lwIP/TLS/flash без нагрузочного теста устройства.
- Accepted-work estimate отдельно от ASIC counter; это оценка по сложности ACK за uptime, не физически измеренные все SHA-256. SV2 aggregate replies не превращаются в точную V1 статистику.
- Local candidate/pool accepted/explorer observation разделены. Explorer не consensus/reward proof; нет гарантии доставки при disconnect и resend на другой pool. Нативные candidate send/target/session paths сохранены.
- Finite job slots не различают произвольно задержанные старые UART frames после reuse; software hash validation сохранена. Template uniqueness ограничена доступными текущими шаблонами/сеансом, не глобальной базой всех работ.
- 3.5h Benchmark Lab испытан на симулированном времени, не на физическом майнере. Рост useful work/day, реальной вероятности BTC и производительности **не измерен**. Длительное A/B на одинаковых настройках — отдельный HARDWARE-TEST-PLAN.
- Реальная проверка всех alternate coin/address/pool combinations не добавлялась. Нет автоматической смены монет/пулов по неподтверждённому преимуществу.
- WebKit Linux не Safari iPhone. GitHub Actions workflow готов, но удалённый запуск/публикация не выполнялись.

Expected effect: меньше необязательных TLS/HTTP операций, меньше ложных reconnect/counter errors и более точная диагностика. Измеренный аппаратный эффект неизвестен. См.CHANGELOG/INSTALL-IPHONE/HARDWARE-TEST-PLAN и reports/v2/COMPETITOR-REVIEW.md с закреплёнными источниками пяти проектов. Нет обещания магического повышения вероятности блока.
