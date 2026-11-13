# Проверенные источники для Gamma 601

Дата чтения:2026-11-12. Закреплённые commits, URL, repository license metadata и выбранные строки находятся в competitor-evidence.json. Это выборочная проверка конкретных вопросов, не повторный полный аудит.

- **bitaxeorg/ESP-Miner**: bm_hashrate.c подтверждает32-bit counter и2^32 hashes/count; stratum_socket.c использует TCP_NODELAY, keepalive60/10/3 и раздельные send/receive timeouts. Существующая математика AxeForge соответствует. В2.0 добавлен keepalive через API ESP-IDF60/20/3; регистры не переносились.
- **IsSasoriDev/AxeForge**: актуальный HEAD совпадает с закреплённым e84c651. Штатные self-test, monitor, PSU diagnostics, autotuner, OTA Writer и rollback guard сохраняются. Нового управляющего контура нет.
- **heliospool/HexOS**: Stratum использует ограниченные transport timeouts и обработку смены extranonce. Его драйвер/структуры отличаются; перенос wire/parser кода без совместимости не выполнялся. Наши session/unique-work/CRC проверки из Ultimate1 сохранены.
- **shufps/ESP-Miner-NerdQAxePlus**: Stratum manager защищает операции PThreadGuard и разделяет extranonce текущей/следующей работы; BM1370 использует nonce-total register0x8c. Gamma AxeForge уже использует0x8c. Присутствующие в других ветвях ASIC0x90 не переносились на Gamma.
- **DCentralTech/DCENT_OS**: изучены Rust Stratum client и BM1370 driver. Видны bounded exponential reconnect backoff и отдельные драйверные контракты. Rust/MCP/подписанная OTA и другая архитектура не интегрировались в ESP-IDF AxeForge. Действующий ESP32 код не переписывался.

Все пять repository metadata показывали GPL-3.0; это не автоматически подтверждает лицензию любого вложенного файла. Код конкурентов не копировался: изменения2.0 написаны для существующего AxeForge; ссылки служат доказательствами формата счётчиков/подходов. Лицензия исходной интеграции GPL-3.0 сохранена.

Фактическая частота в API — запрограммированная PLL/частота штатного драйвера, не независимое аппаратное измерение. Без Gamma нельзя измерить UART latency, task high-water, утечки24/7, прирост accepted work или доказать причину конкретного реального лога. Не менялись baud, BM1370 register setup, рабочие MHz/mV пользователя, аппаратные cutoffs или partitions.
