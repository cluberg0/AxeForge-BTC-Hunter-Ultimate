# AxeForge BTC HUNTER ULTIMATE2.0 — Gamma601

Полная app OTA для ESP32-S3/одного BM1370, построенная поверх существующей Ultimate1.0. Upstream: AxeForge1.4.10 commit `e84c651c36a4b5f91c537577704245ded032592d`; ESP-IDF **v5.3.2** commit `9d7f2d69f50d1288526d4f1027108e314e8c879f`. GPL-3.0, LICENSE. Аппаратного Gamma в среде нет: программная валидация не равна испытаниям устройства.

## Что изменено

См.CHANGELOG.md. Удалены native Weather/Open-Meteo и Mempool опросы, market polling/пауза по цене и unattended external OTA. NTP, ручной тариф/энергия, ручная OTA и все аппаратные защиты сохранены. Farm работает по запросу. Guardian explorer — явно запрашиваемая дополнительная диагностика; отправка кандидата от него не зависит.

Stratum получил TCP keepalive, разные idle bounds active/standby, корректный reconnect backoff и failback anti-flap. API `/api/network` не создаёт задачи/соединения: GET читает event counters, POST сохраняет ручное UTC-смещение. Исходные API и их поля сохранены; поля старых выключенных сервисов остаются для backup/совместимости.

Частотой/напряжением управляет штатный tuner. Нативные история/две проверенные стабильные точки/безопасный fallback остаются тем же модулем. Профили18/22/25W; TURBO30W заблокирован без реальной аппаратной проверки. Старые настройки NVS не стираются; effective automatic tuning ceiling<=25W, даже если ранее сохранён30W. Рабочая пользовательская точка786MHz/1170mV не заменяется нашим новым default.

## Сборка

Linux: Git, Python/venv, g++/make, CMake3.x/Ninja, Node; mbedTLS/cJSON headers/libs, PyYAML/jsonschema; Playwright Chromium/WebKit+runtime dependencies. Сборщик нужен разработчику, не владельцу iPhone.

```sh
bash scripts/bootstrap-idf.sh
export IDF_TOOLS_PATH="$PWD/.tools/idf-tools"
source .tools/esp-idf/export.sh
bash scripts/prepare.sh
bash scripts/test.sh
python3 tests/browser.py
BROWSER=webkit python3 tests/browser.py
bash scripts/build.sh
python3 scripts/stack_report.py
(cd dist/v2 && sha256sum -c SHA256SUMS.txt)
```

Для уже установленного IDF активируйте своё окружение ровно5.3.2. `prepare.sh` требует отсутствующего upstream, сверяет pinned commit и применяет все патчи. Удалённый CI настроен в .github/workflows/build.yml, но не запускался/не публиковался в этой сессии.

Выход: `dist/v2/axeforge-gamma-BTC-HUNTER-ultimate-2.0.bin`. Build script проверяет stock board/partitions/limits, совпадение source inputs до/после, ELF symbols, отсутствие Weather/Mempool/price worker symbols, image/board tag/size/XOR/SHA. Логи в reports и reports/v2. ELF/map и конфигурация включены в комплект; они не предназначены для OTA.

Генерация UI: `python3 prepare_ui.py && python3 hunter_ui.py && python3 v2_ui.py`. Все три стадии обязательны; результат хранится в overlay/main/web/index.html. `upstream/` — воспроизводимая производная. История/изменения находятся в собственной Git-ветке ultimate-2.0; официальный репозиторий не изменялся.

## Установка/проверка

INSTALL-IPHONE.md — OTA и ручной откат; HARDWARE-TEST-PLAN.md — не выполненные аппаратные испытания; TEST-REPORT.md — сборка/SHA/тесты/ограничения/сравнение с Ultimate1.0. Зарезервирован прежний скомпилированный Ultimate1.0 в backup/, но он не становится заведомо рабочим на вашем устройстве только по программным проверкам.

После удаления Open-Meteo часы больше не узнают timezone по городу: в «Часы» задайте UTC offset, Уссурийск600мин. Город/Wi-Fi/кошелёк/пулы/разгон сохранены. Первое испытание под наблюдением:25W, автономные опции off, OTA Guard on. Реальный рост useful work/day и24/7 стабильность без устройства не измерены.

Упаковка локального полного комплекта: `python3 scripts/package_release.py` (требует уже проверенного backup1.0 и логов). Побайтовая воспроизводимость на другой машине/дате не заявляется: ESP-IDF включает дату/время сборки, ELF содержит пути. Manifest фиксирует точные входные исходники данного артефакта.
