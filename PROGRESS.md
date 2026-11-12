# BTC HUNTER ULTIMATE — финальный статус

## Выполнено
- Архив сохранён в Git, собственная ветка ru-fix10. Pinned upstream e84c651c36a4b5f91c537577704245ded032592d, ESP-IDF v5.3.2.
- Исправлены ledger/ID/session/JSON, Work publication/pause, UART partial frames/CRC5/init RX, counter reset/freshness, NVS/OOM/OTA stalls, архив и UI/2FA.
- Добавлены повторный Benchmark Lab, optional default-off Guardian HTTPS, 13 физических шкал, pool/Asia/Core/CKPool документация и аппаратный план.
- Финальные host 157/ASan/UBSan/API/JSON/OTA/NVS/pause/target 10007/UART/Chromium/WebKit PASS. Генераторы HTML byte-exact; чистое применение воспроизводит 331 исходный файл.
- Полная сборка ESP32-S3 Gamma успешно завершена; ошибки include/printf исправлены без ослабления checks. ELF/map/size/target stack/image/esptool/symbols PASS.
- OTA 1 901 968 байт, штатный app 4 MiB. SHA256 7dbdeb54ac5f1706709fdc01f26109d3d3d2f1bf523d2eb4c2f89752e1e0afe8, три независимых инструмента совпали.

## Осталось
- Программная работа завершена. Итоговые файлы упакованы для скачивания; аппаратные испытания остаются по отдельному плану.

## Ограничения/решения
- Физического Bitaxe нет: аппаратные ASIC/heap/стабильность/OTA/Safari испытания NOT RUN. Прирост производительности не измерен и не заявляется.
- Штатные partition/bootloader/защиты/default wallet/pool/NVS сохранены. Экспериментальные функции default-off, автоOC/автопереключения нет.
- Guardian — стороннее наблюдение, не consensus/reward proof; полный live Stratum lifecycle не испытан. Полные ограничения в TEST-REPORT.md.
- Итог: axeforge-gamma-BTC-HUNTER-ultimate.bin, источники, логи, ELF/map, CHANGELOG/TEST-REPORT/HARDWARE-TEST-PLAN/INSTALL-IPHONE.
