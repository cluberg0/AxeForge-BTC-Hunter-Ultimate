# BTC HUNTER ULTIMATE — TEST REPORT

Дата: 2026-11-12 UTC. **Сборка и перечисленные программные проверки PASS. Аппаратные испытания NOT RUN.** Это полноценный скомпилированный app OTA; проверенная на реальном Gamma эксплуатационная стабильность не заявляется.

## Артефакт и сборка

- `axeforge-gamma-BTC-HUNTER-ultimate.bin`, версия `1.4.10-hunter-ultimate`.
- Размер **1,901,968 байт**; штатный app-раздел 4 194 304 байт; запас 2,292,336 байт.
- SHA-256: `7dbdeb54ac5f1706709fdc01f26109d3d3d2f1bf523d2eb4c2f89752e1e0afe8`.
- AxeForge v1.4.10 commit `e84c651c36a4b5f91c537577704245ded032592d`; ESP-IDF **v5.3.2**, `9d7f2d69f50d1288526d4f1027108e314e8c879f`; Xtensa GCC 13.2.0_20240530, ESP32-S3.
- `sdkconfig.defaults;sdkconfig.defaults.gamma`, `CONFIG_AF_BOARD_BITAXE_GAMMA=y`, сгенерированный `AF_NUM_ASICS=1`, BM1370, tag `AXEFORGE-BOARD:gamma;`.
- Получен чистый checkout, применены overlay и все патчи. Побайтово совпал **331 исходный файл** с рабочим upstream: `reports/reproducibility.log`.
- Сборка начата с `ninja -C upstream/build_gamma -t clean`; `bash scripts/build.sh` выполнен до exit 0. Обнаруженный при чистой сборке отсутствующий include настроек Guardian исправлен, сборка продолжена до успешной линковки. Ранние printf/Xtensa и esp_timer ошибки также исправлены; не обходились отключением compiler checks.
- Итоговые build/image checks: exit 0, предупреждений компилятора в итоговых прогонах нет. `reports/ultimate-clean-build-attempt.log` сохраняет неудачную попытку; `reports/build.log` и `reports/ultimate-build-command.log` — успешное завершение.
- Source manifest до/после сборки совпал. Проверены присутствие нативных ELF-символов, формат app ESP32-S3, app descriptor/version/board tag, сегменты, границы, XOR и appended SHA-256, отсутствие хвостовых данных. `esptool.py --chip esp32s3 image_info` PASS. Файловый SHA независимо совпал у Python hashlib, sha256sum и OpenSSL.
- ELF/map/sdkconfig/board header, логи и полный исходник предоставляются вместе с релизом. Ни factory, ни bootloader, ни partition-table binary не предлагаются для OTA.

## Результаты проверок

| Проверка | Фактический результат |
|---|---|
| Штатные host-тесты AxeForge | **157 checks, 0 failed**, ASan/UBSan; штатная host board fixture, не реальный Gamma |
| Native math/intelligence/hunter | PASS, ASan/UBSan и `-Wall -Wextra -Werror`; пропуски/веса/NTP/NVS reserve и ошибки, stale sensors/counters, безопасный rollback/fan floor, task failure |
| Stratum ledger | PASS: исходная сложность, неизвестные/повторные/поздние ACK, ACK-before-send, disconnect, timeout, send failure, защита candidate pending от ordinary bursts |
| V1 wire | PASS, production helper + реальный cJSON: uint32 ID/границы/недопустимые значения, JSON escaping/serialization, allocation failures |
| ASIC UART | PASS, ASan/UBSan: все разбиения кадра, back-to-back, шум, неверный CRC, каждый повреждённый payload bit, overlapping preamble. Потоки синтетические; правило CRC сверено с закреплённым официальным ESP-Miner |
| Send/pause concurrency | PASS: извлечённый production-код, детерминированные C++ потоки, публикация Work до send, ожидание in-flight send, запрет delayed builder после pause, повторная проверка power/pool; timeout теста 15 s |
| Target | PASS: Genesis/границы и **10 007** фиксированных/seeded random compact значений против независимой Python 256-bit integer reference, zero/sign/overflow и BTC pow-limit |
| Benchmark Lab | PASS на симулированном времени: 6 этапов, 2 повтора каждого интервала, исключённый прогрев, sample thresholds, late-ACK attribution, abort/restore, conservative CI/repeat spread. Это не физический 3,5-часовой benchmark |
| Guardian | PASS с HTTP/NVS/allocator fakes: default off, TLS+no redirects, 404/offline/NTP/OOM, неверный/deep/truncated/oversized JSON, read deadline, retry throttling, смена кандидата/disable race, expiry. Реальный HTTPS Genesis endpoint проверен только с Linux, не ESP32 |
| OTA/NVS failures | PASS, production handler/branch + fakes: abandoned upload, временные stalls, OOM, dropped connection, wrong size, cleanup и отсутствие reboot/boot selection при ошибке; saved pools query/read/allocation failure без erase |
| API | PASS штатный api_contract и 3 новых endpoint; реальный JSON host-модулей валидирован OpenAPI; штатный api_guard/Origin/CSRF/2FA wrapper сохранён |
| JavaScript/Python/generators | PASS node syntax, py_compile, точная регенерация итогового HTML |
| Chromium | PASS exit 0: все расширенные assertions, 320/375/390/430/768 px |
| WebKit | PASS exit 0: те же assertions на реальном Linux WebKit engine. Host preflight обойдён после установки недостающих runtime libs; функциональные assertions не пропускались |

Браузерные проверки включают реальные clicks четырёх вкладок/подразделов, все 13 физических цветных шкал, touch layout/CSV/месячный архив/пропуски/выброс, profile staging без записи, 2FA cancellation/network recovery, запрет незагруженных и duplicate saves, отказ API, backup/restore fixture, анимацию на одной странице/reduced-motion/hidden pause, Benchmark Lab и независимый Guardian. Скриншоты в `screenshots/`; fixture не является реальным майнером и не доказывает каждую штатную аппаратную кнопку.

Команды: `AXEFORGE_HOST_SYSROOT=/workspace/toolchains/host-sysroot bash scripts/test.sh`; `python3 tests/browser.py`; `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 BROWSER=webkit python3 tests/browser.py`; `bash scripts/build.sh`; `python3 scripts/stack_report.py`. В CI headers/libs устанавливаются штатными пакетами без AXEFORGE_HOST_SYSROOT. Точные логи: `reports/ultimate-host-tests.log`, `reports/browser-ultimate-*.log`, build/image/metadata/size/stack reports.

## Память и неизменяемые условия

- Linker DIRAM: 176 427 / 341 760 байт, остаток 165 333. Отдельное IRAM окно 16 383 / 16 384, как видно в полном map/size; это не показатель свободного heap после старта.
- Наибольшие статические frames в проверенных единицах Xtensa: Hunter 1312, Intelligence 1648, Guardian 1200, miner 2384, pools 2144 байт. Это отдельные frames, не сумма call chain и не RTOS high-water measurement; HTTP stack штатно 8192.
- Runtime free heap/PSRAM/task high-water/NVS occupancy после загрузки **не измерены**. Новые модули проверяют ошибки выделения/запуска/записи; резерв NVS и отдельные namespaces не означают доказанное наличие места на конкретном майнере.
- Штатные partitions/default configs/Gamma board/OTA Guard сравнены с pinned upstream. Не менялись bootloader source, разметка, hard cutoffs ASIC 68°C/VRM 85°C, пределы 800 MHz/1300 mV и wallet/pool defaults. Прошивается только app; сохранение NVS подтверждено анализом/моделями, реальный OTA ещё не выполнялся.

## Эффект и пределы доказательств

Исправления устраняют подтверждённые причины потерь UART кадров/некорректного учёта/гонок. Ожидаемый эффект — меньше программных потерь полезной работы и более честная диагностика. **Измеренный прирост TH/s, accepted work/day или вероятности блока отсутствует.** Проверенная пользователем точка 786 MHz / 1170 mV / ~1,55 TH/s не является нашим замером.

- Полный live V1/TLS/SV2 transport lifecycle, реальные pools/ASIC/reconnect under load, физические UART timing/CRC и reboot/power-loss/OTA **NOT RUN**. Конечные аппаратные job slots не различают произвольно задержанные старые кадры после reuse; software header hash verification сохранена. Исчерпание extranonce контролируется для текущего эквивалентного шаблона, не глобально через все template cycles/reboots.
- Причина исторического 3933.24 TH/s без raw trace не доказана. Счётчик baseline синхронизирован, недостоверный замер логируется и не загрязняет EMA/tuner/history; реальные error counters не скрываются.
- Benchmark не повышает voltage/frequency, version rolling штатный; результаты не применяются автоматически. Эксперименты выключены по умолчанию. First hardware trial — ранее проверенные настройки, лимит25 W, наблюдение.
- Pool stats накоплены по слоту с загрузки и могут включать смену адреса; рекомендации текущему серверу по такой истории не выдаются. Азия-пулы исследованы по официальным источникам, не измерены из Уссурийска; defaults/порядок не изменены. Автопереключения нет.
- Coin templates не доказывают поддержку любого адреса/Stratum/альтернативной сети. Автоматическая network-specific проверка всех монет не реализована; payout guard сохраняется.
- Local target hit, pool ACK и HTTPS explorer observation различаются. Explorer не является собственной Bitcoin consensus validation, может ошибаться/быть недоступным и не доказывает reward. Нет guaranteed delivery при разрыве и повторной отправки другому пулу.
- WebKit Linux не равен Safari/iOS/Low Power Mode. Реальные iPhone OTA, тепловые/электрические защиты, длительная стабильность и все пункты HARDWARE-TEST-PLAN.md **NOT RUN**.
- CI workflow подготовлен, но удалённый GitHub Actions запуск/публикация не выполнялись: нет подключённого собственного remote/доступа. Локальные файлы полностью предоставлены.

Подробности: CHANGELOG.md, INSTALL-IPHONE.md, HARDWARE-TEST-PLAN.md, POOL-ARCHITECTURE.md и тематические reports/*AUDIT*/integration-audit.md. Аппаратный план не выдаётся за выполненные испытания.
