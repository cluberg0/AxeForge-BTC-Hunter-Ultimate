# AxeForge BTC HUNTER — TURBO1000 UNLOCK, Gamma601

Полная app OTA для ESP32-S3/одного BM1370, построенная поверх существующей Ultimate1.0. Upstream: AxeForge1.4.10 commit `e84c651c36a4b5f91c537577704245ded032592d`; ESP-IDF **v5.3.2** commit `9d7f2d69f50d1288526d4f1027108e314e8c879f`. GPL-3.0, LICENSE. Аппаратного Gamma в среде нет: программная валидация не равна испытаниям устройства.

## Что изменено

См.CHANGELOG.md. Удалены native Weather/Open-Meteo и Mempool опросы, market polling/пауза по цене и unattended external OTA. NTP, ручной тариф/энергия, ручная OTA и все аппаратные защиты сохранены. Farm работает по запросу. Guardian explorer — явно запрашиваемая дополнительная диагностика; отправка кандидата от него не зависит.

Stratum получил TCP keepalive, разные idle bounds active/standby, корректный reconnect backoff и failback anti-flap. API `/api/network` не создаёт задачи/соединения: GET читает event counters, POST сохраняет ручное UTC-смещение. Исходные API и их поля сохранены; поля старых выключенных сервисов остаются для backup/совместимости.

Частотой/напряжением управляет штатная задача tuner. Штатный потолок800MHz и профили18/22/25W сохранены. Расширенный программный режим Gamma/BM1370 разрешает ручные частоты и исследование до1000MHz при<=1300mV и пользовательском лимите<=30W. Профиль experimental в gamma.toml не является измеренным аппаратным запасом.

«Разгон» → «Включить расширенный разгон» → ввести OVERCLOCK. Разрешение сохраняется в штатном settings.overclock; само включение ничего не выставляет на максимум и не запускает эксперимент. Задайте реальные паспортные данные БП, предел поиска и мощности; сохраните параметры. «Подтвердить и начать» требует TURBO1000; «Перезапуск поиска» использует тот же stock tuner phase. Нужны30минут свежей стабильной штатной точки и достаточная принятая работа V1.

Нет фиксированного25W в TURBO. Бюджет=min(пользовательский<=30W, min(паспортныеW,5V×A)−max(2W,10%)−1.5W, min(A−0.5A,6.5A)×min(VIN,5V)−1.5W). Дополнительно−10% при просадке/нагреве/неоценённом PSU. При5V/6A/30W получается25.5W, при40W/8A —30W до динамического снижения. Показаны причина, reserve и оценка. TPS Pout+штатные5W не являются калиброванным измерением входа;1.5W — программный резерв погрешности, не доказательство точности. Номинал вводит пользователь, его нельзя увеличить в настройках вместо замены БП.

PLL-сетка исследования12.5MHz; дробные точки округлены в legacy uint16 метках(813→812.5MHz), native API отдельно показывает вычисленную PLL после команды драйверу. На каждой точке прогрев/измерение120+300s, повтор60+300s, затем поиск минимального стабильного напряжения шагом10mV с повтором. Выбор по стабильному аппаратному хешрейту с долей ACK, accepted-work estimate показывается отдельно. Ни высокую частоту, ни случайный всплеск шар приростом не считаем.

При выключении — штатные525MHz/1150mV. После boot разрешение/БП/предел сохраняются, поиск не запускается; сохранённая частота>800 возвращается к штатной стартовой точке до нового ручного решения. Все Wi-Fi/wallet/pool settings и flash layout сохранены. GPIO/аварийные68/80°C ASIC,85/100°C VRM и штатный электрический cut-off не повышены; исследовательские65/75°C строже.

## Сборка

Linux: Git, Python/venv, g++/make, CMake3.x/Ninja, Node; mbedTLS/cJSON headers/libs, PyYAML/jsonschema; Playwright Chromium/WebKit+runtime dependencies. Сборщик нужен разработчику, не владельцу iPhone.

```sh
bash scripts/bootstrap-idf.sh
export IDF_TOOLS_PATH="$PWD/.tools/idf-tools"
source .tools/esp-idf/export.sh
[ -d upstream ] || bash scripts/prepare.sh
bash scripts/test.sh
python3 tests/browser.py
BROWSER=webkit python3 tests/browser.py
bash scripts/build.sh
python3 scripts/stack_report.py
(cd dist/unlock && sha256sum -c SHA256SUMS.txt)
```

Для уже установленного IDF активируйте своё окружение ровно5.3.2. Полный source ZIP уже содержит patched upstream; для Git checkout без него `prepare.sh` требует отсутствующего upstream, сверяет pinned commit и применяет все патчи. Удалённый CI настроен в .github/workflows/build.yml, но не запускался/не публиковался в этой сессии.

Выход: `dist/unlock/axeforge-gamma-BTC-HUNTER-TURBO1000-UNLOCK.bin`. Build script проверяет stock board/partitions/limits, совпадение source inputs до/после, ELF symbols, отсутствие Weather/Mempool/price worker symbols, image/board tag/size/XOR/SHA. Логи в reports и reports/unlock. ELF/map и конфигурация включены в комплект; они не предназначены для OTA.

Генерация UI: `python3 prepare_ui.py && python3 hunter_ui.py && python3 v2_ui.py && python3 turbo_ui.py`. Все четыре стадии обязательны; результат хранится в overlay/main/web/index.html. `upstream/` — воспроизводимая производная. История/изменения находятся в собственной Git-ветке turbo1000-unlock; официальный репозиторий не изменялся.

## Установка/проверка

INSTALL-IPHONE.md — OTA и ручной откат; HARDWARE-TEST-PLAN.md — не выполненные аппаратные испытания; TEST-REPORT.md — сборка/SHA/тесты/ограничения/сравнение с Ultimate2.0. Зарезервирован прежний скомпилированный TURBO1000 в backup/, но он не становится заведомо рабочим на вашем устройстве только по программным проверкам.

После удаления Open-Meteo часы больше не узнают timezone по городу: в «Часы» задайте UTC offset, Уссурийск600мин. Город/Wi-Fi/кошелёк/пулы/разгон сохранены. Первое испытание под наблюдением:25W, автономные опции off, OTA Guard on. Реальный рост useful work/day и24/7 стабильность без устройства не измерены.

Упаковка локального полного комплекта: `python3 scripts/package_release.py` (требует уже проверенного backup TURBO1000 и логов). Побайтовая воспроизводимость на другой машине/дате не заявляется: ESP-IDF включает дату/время сборки, ELF содержит пути. Manifest фиксирует точные входные исходники данного артефакта.

GitHub: https://github.com/cluberg0/AxeForge-BTC-Hunter-Ultimate/tree/turbo1000-unlock (приватный репозиторий пользователя). Программные тесты/образ проверены локально; hardware/24h improvement не измерены.
