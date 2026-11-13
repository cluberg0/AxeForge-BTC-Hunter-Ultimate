# TURBO1000 — контрольная точка

База23724c5, веткаultimate-2.0-turbo1000. Новые агенты не запускались.

Выполнено: ручная непостоянная session в штатном tuner; потолок1000MHz, точные PLL ступени12.5MHz/200ms выше800 и tuner25MHz; stock800/1300 и hard68/85 сохранены. Map16 измеренных точек, fresh telemetry, accepted work, PSU/thermal/error/session guards, откат, API+UI3. Запрос30W -> effective<=25W (TPS estimate), <=23W при derating; reserve3W. Настройки/partitions/OTA guard неизменны.

Проверено: IDF5.3.2 build4 exit0, image1925072B, SHA f05a28224dd6be99775bb27dd5d1ea78c3dc9d2928406d2a0161df1e35cc2757. Полный scripts/test.sh PASS (stock157, ASan/UBSan, PLL7201, production tuner/board failure injection,5API,JS). Chromium+WebKit PASS. Clean pinned apply:338файлов совпали. Target stack frames получены; физический high-water не измерен.

Исправления: PLL failure не оставляет устаревшую частоту; voltage/clock writes прекращаются после ошибки, downclock до undervolt; power freshness не обновляется ошибочными reads; user stop не теряется при переходе hold; clock counter rebaseline grace10s только для counter.

Уточнение: legacy806.25MHz поддерживается приблизительно807.14, это не unsupported PLL. Предположение исправлено differential test.

Завершено: актуализированы README/CHANGELOG/TEST-REPORT/HARDWARE-TEST-PLAN/INSTALL-IPHONE и build-metadata; полный source/release ZIP с backup2.0 прошёл CRC и сверку вложенных BIN. Суммы SHA проверены hashlib/sha256sum/OpenSSL, source manifest совпадает; UI4-stage reproducible. Код3ebdc22, полный release в dist/turbo. Никакого hardware testing/performance claim; устройство не прошивалось.
