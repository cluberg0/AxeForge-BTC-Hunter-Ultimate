# AxeForge FASTSEARCH FIXED · Gamma 601

Исправление FASTSEARCH для Bitaxe Gamma 601, ESP32-S3, один BM1370. Основа: [AxeForge v1.4.10](https://github.com/IsSasoriDev/AxeForge/tree/v1.4.10), commit `e84c651c36a4b5f91c537577704245ded032592d`, GPL-3.0.

При достижении программного бюджета мощности поиск прекращает разгон и перебирает ранее измеренные кандидаты по производительности. Нужен запас по **пиковой** мощности не менее `max(0.5 W, 2% effectivePower)`, актуальные данные (не старше суток), подходящие температура и питание. Применение сохраняет порядок напряжение/частота. Кандидат проходит 120 секунд прогрева и 300 секунд измерения; проверяются ASIC-ошибки, производительность, датчики, питание и мощность. Неудачный кандидат исключается. Успешный переходит в HOLD с непрерывными защитными проверками. В HOLD возможен только повторно проверенный переход к меньшей частоте. Каждая пара частота/напряжение пробуется для закрепления один раз за поиск.

Физический предел мощности имеет отдельную причину `hardware_power`; перегрев, ток, питание, датчики, PLL и watchdog сохраняют аварийное поведение. Если кандидатов нет, применяется безопасный откат. Частота и напряжение кандидата не повышаются относительно точки, завершившей поиск. При смене режима допускается до двух секунд для обновления старого общего процента ASIC-ошибок; полное контрольное измерение всё равно проверяет ошибки. Остальные защиты активны постоянно.

Короткие пробы хранятся в RAM; в NVS записываются только полностью проверенные режимы. Сохранённые режимы после загрузки также требуют повторной проверки. Ошибка записи/commit не останавливает исправный ASIC: API сообщает `persisted:false` и `storageError`. Ошибки чтения и повреждённые данные также сообщаются явно. NVS не стирается; Wi-Fi, пулы и кошелёк не меняются. Сохраняются ручная настройка и один автоматический тюнер.

API `totalSteps` считает все испытания, `trials` хранит последние 16 по порядку; интерфейс использует этот счётчик вместо обнулённого счётчика штатного тюнера.

## Воспроизведение

Нужны ESP-IDF **5.3.2**, host g++, Node.js, mbedTLS/cJSON, PyYAML/jsonschema и Playwright. Существующий workflow [single-tuner-v2.yml](.github/workflows/single-tuner-v2.yml) выполняет весь конвейер и публикует OTA-артефакт; отдельный дублирующий workflow не добавлен.

```sh
unzip -q AxeForge-ONESEARCH-build.zip -d project
cd project
bash scripts/prepare.sh
python3 ../fastsearch_overlay.py .
python3 ../one_tuner_overlay.py .
python3 ../single_tuner_ui.py .
python3 ../single_tuner_js.py .
python3 ../single_tuner_backend.py .
python3 ../one_tuner_recovery_v3.py .
python3 ../one_tuner_nvs_v3.py .
python3 ../single_tuner_version.py .
python3 ../single_tuner_validate.py .
python3 ../single_tuner_browser_test.py .
python3 ../fastsearch_regression.py .
bash scripts/test.sh
python3 tests/browser.py
BROWSER=webkit python3 tests/browser.py
# После активации ESP-IDF 5.3.2:
bash scripts/build.sh
python3 verify_image.py upstream/build_gamma/axeforge.bin
```

`one_tuner_nvs_v3.py` применяет [fastsearch_fix.patch](fastsearch_fix.patch) к точным V3-исходникам и синхронизирует модуль для native-тестов с модулем реальной прошивки. `fastsearch_regression.py` добавляет регрессии к production-code harness из пакета. `upstream/` — воспроизводимая производная, не отдельная копия исходников в Git.

## OTA

Готовый файл релиза: **`axeforge-gamma-FASTSEARCH-FIXED-OTA.bin`**, версия `1.4.10-FASTSEARCH-FIXED`. Это app image для OTA, а не полный flash image; ZIP, bootloader и partition table в OTA загружать не нужно. Контрольная сумма приложена к релизу. Установка через «Система → OTA» сохраняет настройки. Для отката используйте ранее работавший OTA BIN тем же способом.

Программные и браузерные тесты, сборка и проверка образа не являются испытанием на физическом устройстве. Физическая стабильность и круглосуточная работа в этой сессии не проверялись.
