# BTC Hunter ULTIMATE 2.0

База: commit237d3f7, Ultimate1.0; готовый прежний OTA сохранён в dist/v2/backup.

В работе: отключение native Weather/Mempool/автозапросов, NTP сохранить; Stratum standby timeout/TCP keepalive/backoff/anti-flap; диагностика; UI и 4 профиля; новые host/browser проверки; сборка ESP-IDF5.3.2 и комплект OTA.

Не менять частоту/напряжение рабочего устройства, защиты, bootloader/partitions или NVS пользовательских настроек. Физического Gamma нет; агентам задачи не выдаются. Старые результаты/патчи повторно используются.

Этап1: native Weather/Mempool отключены, NTP и ручной UTC сохранены; Stratum policy/diagnostics/anti-flap, единый tuner25W и UI4профиля реализованы. Host157 + новые ASan/UBSan policy/event diagnostics/NTP/counter/guards/API4 PASS. Проверки Chromium/WebKit и сборка2.0 выполняются.
