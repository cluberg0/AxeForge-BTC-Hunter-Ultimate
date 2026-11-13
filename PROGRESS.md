# BTC HUNTER ULTIMATE2.0 — завершено

- База Ultimate1.0/237d3f7, код2.0 в commits33f8709/52f1722; отдельная ветка ultimate-2.0. Дополнительные агенты не запускались.
- Weather/Open-Meteo/Mempool/market HTTP polling отключены; NTP и manual UTC сохранены; auto external update/check off; Farm/Guardian только по запросу. Рабочие NVS settings не стирались.
- Исправлены Stratum standby/active timeout, TCP keepalive, IO-restart backoff bypass и healthy reset;30s failback/срочный failover. Добавлена event-based сеть без новой collecting task.
- Production counter reset теперь сбрасывает связанную error baseline. Синтетический одинаковый trace: Ultimate1 даёт 4294967247 ложныхerror units,2.0 даёт 0; ASIC 1431.656GH/s в обоих. Это не измеренный аппаратный прирост.
- Stock tuner единственный. Новый auto ceiling25W; сохранённые18/22/25/30W настройки не стираются. TURBO30W заблокирован до hardware validation. Stock hard protections/bootloader/flash/ASIC driver неизменны.
- Dark RU2.0 UI: real ASIC/accepted-work graph,4вкладки/13шкал/UTC/сеть;18/22/25W staging,30W blocked. Chromium+WebKit на320/375/390/430/768px PASS.
- Host157/ASan/UBSan/API4/UART/target10007/OTA/NVS/pause/counter/reconnect/services/clock/tuner-guard PASS. Fresh apply334source files byte-equal; UI generator chain byte-equal.
- ESP-IDF5.3.2/ESP32-S3/Gamma1BM1370 сборка, size/ELF/map/stack/image/esptool/markers/source manifest PASS, compiler warnings0.
- Итоговый OTA 1 905 696 байт, SHA256 bb59cc8762bc1e9962c6c96b093321a5b7a9caff5834e9f35962f4c001651f28. Предыдущий OTA и SHA сохранены в dist/v2/backup.
- TEST-REPORT/CHANGELOG/INSTALL-IPHONE/HARDWARE-TEST-PLAN/competitor evidence/исходники готовы; упаковка scripts/package_release.py.

Ограничения: физического Gamma нет; hardware UART/power/thermal/heap/high-water/24h/real OTA/Safari и full live Stratum lifecycle NOT RUN. Нет измеренного выигрыша useful work/day. Вся критическая отправка кандидатов независима от explorer; награда не подтверждается лишьpool ACK. Удалённый GitHub Actions не запускался.
