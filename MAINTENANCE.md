[На главную](README.md) · [Установка](INSTALL.md)

# Обновление и восстановление

## Обновление

### Arch Linux и производные

Для пакетной установки обновите исходники и запустите установщик:

```bash
cd /путь/к/hics
git pull --ff-only
./install.sh
```

Зависимости запуска и сборки устанавливаются из `PKGBUILD`. Пользовательские
настройки сохраняются, службы обновляются автоматически, открытые приложения
продолжают работать. Установка готового пакета:
`./install.sh --package /путь/к/hic-shell.pkg.tar.zst`.
Если изменился нативный плагин, после установки нужен новый сеанс Hyprland.
Для отката версии пакета установите сохранённый предыдущий пакет тем же способом.

### Ручная установка в `$HOME/.local` (прежний сценарий)

Завершите Hyprland, войдите в TTY (**Ctrl+Alt+F3**) и выполните без `sudo`:

```bash
cd /путь/к/hics
./update.sh
```

Скрипт получает исходники, проверяет ABI, собирает проект и обновляет файлы
с резервной копией. Личные Lua/JSON-настройки и тема сохраняются.
Если `update.sh` ещё нет в старом клоне, сначала выполните `git pull --ff-only`.

Опции: `--dry-run` — план изменений, `--jobs 1` — сборка с меньшим расходом памяти,
`--no-pull` — сборка текущих исходников. Свои изменения в Git сохраните
коммитом или через `git stash`.

После обновления войдите в Hyprland и выполните `hics-doctor`.
Для отката снова завершите сеанс и запустите:

```bash
./update.sh --rollback
```

Копии: `${XDG_STATE_HOME:-$HOME/.local/state}/hics-install/backups/`.
Откат не меняет системные пакеты; требуется Hyprland **0.56.2**.
Для конфигурации со ссылками на каталоги используйте свой менеджер dotfiles.

**Для установки пакетом** (`packaging/arch/build-package.sh`) обновление
выполняется повторным запуском того же сценария: пакет пересобирает
вложенный рантайм Quickshell/Qt под текущую системную Qt и упаковывает
его заново. Сценарий `update.sh` выше предназначен для установок
в `$HOME/.local` и для пакетной установки не используется.

### NixOS и Home Manager

Из каталога конфигурации NixOS, заменив `YOUR_HOST`:

```bash
nix flake update hics
sudo nixos-rebuild switch --flake .#YOUR_HOST
```

Войдите в новый сеанс. Встроенный Home Manager применится вместе с системой.
Для отдельного Home Manager обновите тот же вход в его flake и выполните
`home-manager switch --flake .#YOUR_USER`. `update.sh` на NixOS не используется.

Без Home Manager обновите пользовательскую конфигурацию по
[инструкции](INSTALL.md#config), затем верните личные Lua/JSON-файлы из копии.
Сборку CMake и копирование службы пропустите.

## Диагностика

```bash
hics-doctor
hyprctl configerrors
hics-doctor --json
journalctl --user -u hic-session.service -b
```

Для запуска оболочки с выводом ошибок в терминал:

```bash
hics-session stop
hics-shell
```

- **QML:** проверьте совместимость Qt/Quickshell и наличие модулей оболочки
  и `M3Shapes`. После обновления Qt пересоберите hics и, если нужно, Quickshell.
- **PAM:** проверьте пакет `hyprlock` и `/etc/pam.d/hyprlock`.
- **Polkit:** остановите сторонний агент авторизации.
- **Вложенный рантайм:** при установке пакетом Quickshell и Qt берутся из
  `/usr/share/hics/qs`; проверка версии:
  `LD_LIBRARY_PATH=/usr/share/hics/qs/lib /usr/share/hics/qs/bin/hics-qs --version`.

Перезапуск оболочки: `hics-session restart`.

## Восстановление прежнего окружения

На NixOS верните предыдущую ревизию конфигурации и примените её либо загрузите
прежнее поколение системы. Восстановите также конфигурацию Home Manager.
Изменяемые настройки пользователя возвращаются из резервной копии отдельно.

Без Home Manager завершите Hyprland и перейдите в TTY:

1. Найдите `hics-backup.*`, выведенный при установке.
2. Перенесите нынешние `hypr` и `hics` из `${XDG_CONFIG_HOME:-$HOME/.config}`
   в отдельный каталог и верните туда прежние каталоги или ссылки из копии.
3. Верните сохранённый `hic-session.service` в `systemd/user/`.
   Если прежней службы не было, удалите только установленную службу hic-session.
4. При наличии пользовательского systemd выполните `systemctl --user daemon-reload`
   и войдите в прежнее окружение.

## Удаление

На NixOS отключите `programs.hics.enable` в системной конфигурации
и Home Manager, удалите ненужные импорты и вход `hics`, примените изменения.

На Arch-based системах восстановите прежнюю конфигурацию по разделу выше.
Установленные CMake файлы перечислены в `build/install_manifest.txt` вашей сборки;
просмотрите список и удалите указанные файлы hics.

Пользовательские данные удаляются по желанию:

| Каталог | Содержимое |
| --- | --- |
| `${XDG_CONFIG_HOME:-$HOME/.config}/hics` | Настройки |
| `${XDG_STATE_HOME:-$HOME/.local/state}/hics` | Тема, обои, история и состояние |
| `${XDG_CACHE_HOME:-$HOME/.cache}/hics` | Кеш изображений |

## Проверка четырёх режимов

Нативный холст закреплён через `third_party/phantomat/UPSTREAM_REVISION`.
При обновлении сначала собирайте его против используемого ABI Hyprland и
проверяйте переходы tiling → stacking → scrolling → canvas → scrolling
в отдельном вложенном compositor-сеансе. Одновременно патчить drawTex двумя
обзорами нельзя: `overview_hooks(false)` передаёт рендер холсту,
Выход из холста освобождает его перед возвратом.
Не удаляйте синхронную функцию без замены протокола передачи рендера.

После сборки `python tests/integration_canvas.py --pointer` запускает отдельный
Wayland-сеанс с изолированными настройками и состоянием. Проверяет отсутствие
заголовков и миграции в стакинг, реальные значения масштаба, Ctrl+колесо и
перемещение камеры средней кнопкой через `/dev/uinput`, перезагрузку конфигурации
и восстановление плавающих/тайловых окон при выходе. Без `--pointer` проверка
не создаёт виртуальное устройство ввода. Скрипт закрывает только свои окна.

## Системный D-Bus backend

`native/system`: C++-демон `hics-systemd` и клиент `hics-systemctl`.
API `org.hics.System1` (`/org/hics/System1`): `Status(section)` и
`Apply(section, operation, json)`, JSON-ответы с кодами ошибок. Разделы: printers,
storage, datetime, power; printer-discovery выполняет ограниченный поиск CUPS.

Демон выводит UID из уникального имени D-Bus-отправителя. Операции разрешены
по спискам и проверяются до авторизации; административные изменения используют
Polkit. Команды оболочки, пути программ, пароли и UID из запроса не принимаются.
Задания печати фильтруются по имени пользователя; чужое задание отменить нельзя.
До 4 рабочих потоков, 16 ожидающих запросов, ограничение входного JSON и таймауты.
Монтирование/отключение делает нативный клиент от своего UID непосредственно
через UDisks2: запуск от root потерял бы пользователя и его каталог монтирования.

Проверки: `python -m unittest discover -s tests`; после сборки
`hics-systemctl status printers`, `storage`, `datetime`, `power`.
Изменения параметров ОС не выполняются при чтении и открытии страницы.
Поддержка печати использует libcups/IPP, времени — timedate1, питания —
PowerProfiles, дисков — UDisks2; настройки приложения settings-ui использованы
как ориентир по возможностям, без копирования его Python/sudo backend.

## Переход на имя hics

Публичные команды: `hics`, `hics-shell`, `hics-session`, `hics-doctor`,
`hics-systemctl`. Системный помощник — `hics-system.service`; он включается и запускается
при установке пакета, сохраняет D-Bus-активацию и перезапуск после сбоя.
Пользовательский `hic-session.service` включается для `graphical-session.target`;
при установке в действующем Hyprland сеансе оболочка запускается автоматически.
В TTY и других DE пакет не запускает оболочку. Палитры GTK 2/3/4, Qt 5/6,
KDE и портал настраиваются самой оболочкой при старте и смене темы;
установщик не изменяет пользовательские палитры. GTK и порталы входят
в обязательные зависимости Arch-пакета и устанавливаются пакетным менеджером.
Новые настройки и данные используют каталоги `hics` в соответствующих XDG-корнях.
При первом запуске существующие каталоги подключаются ссылками без удаления
данных. Старые команды запуска в личных Lua-файлах заменяются с сохранением
копии `.before-hics`.


## Сжатая память и адаптивная подкачка

В «Диски → Сжатие памяти» доступны системная стратегия, отсутствие подкачки,
ZRAM, ZSwap, совместный и умный режимы. Исходная стратегия — системная:
установка пакета не отключает существующие swap-устройства. Кнопка «Применить»
сохраняет системную конфигурацию через Polkit в `/etc/hics/memory.json`.
Отдельный C++-сервис `hics-memory.service` продолжает работать после выхода
из оболочки. Его состояние доступно через `hics-systemctl status memory`.

В умном режиме ОЗУ используется без подкачки до порога `ramThreshold`;
нагрузка считается по `MemAvailable`, исключая освобождаемый файловый кэш.
Затем подключается ZRAM ёмкостью `zramMiB`. При заполнении его логического
объёма до `zramThreshold` подключаются ZSwap и первый дисковый блок.
Пул ZSwap ядро выделяет динамически в пределах `poolPercent` процентов ОЗУ.
Дисковый резерв расширяется отдельными файлами по `chunkMiB` при заполнении
до `diskThreshold`, ограничен `diskMaxMiB`, 24 областями и запасом
свободного места `reserveMiB`. Активные файлы не растягиваются.
Файлы расположены в `/var/lib/hics-memory/swap`; на Btrfs это отдельный
подтом, исключённый из снимков родительского тома. Поддерживаются Btrfs,
ext4 и XFS; для создания swap-файлов нужен util-linux не ниже 2.41.

Обратный переход на ОЗУ включается отдельно: нагрузка должна оставаться ниже
первого порога минус `hysteresis` в течение `releaseSeconds`. Перед swapoff
проверяется запас ОЗУ: 125% используемой подкачки плюс 512 МиБ.
Низкая нагрузка оценивается с учётом возврата страниц из подкачки в ОЗУ,
чтобы само сжатие не вызывало циклическое отключение и повторное включение. При нехватке
памяти подкачка сохраняется; неактивные управляемые файлы удаляются после
успешного отключения. Изменение размера/алгоритма также требует безопасного
освобождения текущей подкачки. Контроллер проверяет состояние раз в 5 секунд;
умный режим не гарантирует защиту от мгновенного скачка выделения памяти.

Передача системного ZRAM0 требует отдельного переключателя. hics поддерживает
перехват только устройства от `systemd-zram-generator`; он безопасно отключает
его и записывает собственный drop-in `90-hics-memory.conf` с `zram-size = 0`.
При возврате к системной стратегии drop-in удаляется и штатный ZRAM0 запускается.
Другие внешние swap-разделы/файлы не изменяются: контроллер сообщает о конфликте.
ZSwap глобален и может дополнительно сжимать страницы для ZRAM; совместный режим
способен повысить затраты CPU. Дисковая подкачка наследует защиту своего файлового
раздела и не настраивается как образ для гибернации.

Проверки: `test_memory_controller.py`, `integration_memory_controller.py`.
Последний запускает настоящий код контроллера с путями ядра и командами,
перенаправленными исключительно в временной тестовой копии исходников;
у установленного привилегированного процесса таких переключателей нет.

## Проверки устойчивости нативных компонентов

CUPS сохраняет и восстанавливает локальные настройки потока для каждого запроса;
обнаружение принтеров использует тот же локальный планировщик. Восстановление
рабочей сессии отменяет запущенные команды и дожидается фоновой задачи при
уничтожении объекта. Ожидание Libreswan использует сигналы systemd на отдельном
соединении D-Bus; операцию можно отменить в разделе VPN. Установка VPN-плагина
выполняется в отдельной пользовательской службе: завершение оболочки отменяет
только ожидание результата, сохраняя пакетную транзакцию. Кнопка отмены
не предлагается для уже запущенной установки пакета.

Холст и обзор используют `libhics-render-dispatch.so`: общий диспетчер держит один
хук `drawTex`, переключая обработчики без переустановки трамплина. Библиотека
обязательна в нативном комплекте и проверяется перед развёртыванием. Макросы,
переопределявшие `private`/`protected`, удалены и из адаптера холста:
используются публичные методы либо узкие указатели на члены закреплённого ABI. Загрузчик
холста проверяет IPC, настроенные выходы, Lua-интеграцию и завершённую
инициализацию композитора вместо фиксированной задержки. После неудачного
`PLUGIN_INIT` автоматических повторных загрузок нет. Такие обновления следует
устанавливать из TTY после завершения Hyprland, как описано выше.

Ответы Requests и Lyrics ограничены 4 МиБ, временем простоя и общим временем
запроса. Поиск локальных текстов работает в отдельном пуле из одного потока,
не следует по символическим ссылкам и ограничивает число просмотренных записей
и время обхода. Завершение текущего файлового вызова зависит от файловой системы:
эти ограничения не являются жёстким таймаутом для зависшего сетевого диска.
Передача записей истории в `wl-copy` использует файл напрямую; редактор текста
принимает не более 1 МиБ, бинарные записи сохраняют отдельный лимит истории.
Геолокация погоды запрашивается по HTTPS.

Помощники Python остаются для операций с конфигурацией. Повторная миграция
пропускается по маркеру успешного выполнения; изменение основного Lua-конфига
повторно запускает проверку. Очередь FeatureBackend объединяет соседние чтения
и явно разрешённые серии изменений, сохраняя границы операций и обработчики
результатов. Передача сцен обзора использует один JSON и безопасную строку Lua;
неизменившиеся сцены повторно не отправляются. Старые URI QML, Lua-идентификаторы
и переменные окружения сохраняются как интерфейсы совместимости; публичные
параметры сборки используют `HICS_*`.

Регрессии: `test_bounded_network.py`, `test_cups_context.py`,
`test_workspace_tools.py`, `test_vpn_native.py`, `test_canvas_loader.py`,
`test_branding_fastpath.py`, `test_service_templates.py`.
Проверки реального исполнения: `integration_canvas.py`,
`integration_offscreen_capture.py`, `integration_backend_lifecycle.py`,
`integration_feature_coalescing.py`, `integration_lyrics_lifecycle.py`.
Последние графические проверки создают собственный вложенный композитор либо
используют offscreen; пользовательские окна и системные соединения не изменяют.

## Этап 1 оптимизации: брокер, аудио и ограничение памяти

Брокер сохраняет D-Bus-активацию (`Type=dbus`, `BusName`) и использует
`WatchdogSec=30`, `NotifyAccess=main`. Heartbeat отправляет таймер главного
потока; период определяется `sd_watchdog_enabled()`. Рабочие задачи не могут
маскировать зависание главного потока собственными heartbeat.

SIGTERM/SIGINT передаются в Qt через неблокирующий self-pipe. Обработчик сигнала
не вызывает Qt, mutex или ожидание потоков. При остановке новые запросы
отклоняются; ожидающие задания при получении рабочего потока возвращают ошибку
остановки. Брокер даёт
активным заданиям пять секунд; если они не завершились, заканчивает процесс
без разрушения Qt под работающими потоками. Внешние операции CUPS, системных
демонов и отдельных привилегированных workers могут продолжиться; запись
после такого обрыва нельзя автоматически повторять.

Допуск ограничен 16 незавершёнными запросами всего, двумя на UID и одним
на D-Bus-соединение. Token bucket допускает до 10 запросов/с на соединение
и 40 запросов/с на UID. Переподключение не сбрасывает квоту пользователя.
Таблицы учёта и кэш UID ограничены, завершённые отключившиеся клиенты удаляются.
C++-клиент повторяет только чтения, явно отклонённые как временно занятые,
с ограниченным backoff и jitter. Записи и неоднозначные ошибки D-Bus
автоматически не повторяются.

Аудиосборщик уже запускался по числу подписчиков. Исправлены пробуждение
PipeWire-loop через stop event и согласованность PCM-снимков: realtime-писатель
использует `try_lock`, не ожидает читателя и не выделяет память. Деструктор
дожидается worker до разрушения буфера. Сохранены исходный quantum и размер
анализа; искусственных задержек старта/остановки нет. Аудиовизуализатор остаётся
необязательной сборочной функцией `HICS_AUDIO_VISUALIZER`.

В текущем memory worker нет `m_free` или `releaseBlocks()`. Размеры ZRAM,
ZSwap и число swap-областей уже ограничены политикой. Дополнительно ограничены
чтения конфигурации/JSON-состояния (256 КиБ) и системных атрибутов (1 МиБ),
включая проверку фактически прочитанных байтов. Небольшие атрибуты читаются
короткими блоками без предварительного выделения всего лимита.

Проверки: `test_broker_runtime.py`, `test_audio_collector.py`,
`test_controller_io.py`, `integration_audio_shutdown.py`,
`integration_memory_controller.py`. Watchdog проверяется на собственной
временной пользовательской службе с изолированным D-Bus и backend-имитатором;
брокер основной системы не останавливается. Аудиопроверка использует отдельный
PipeWire-сервер и синтетический источник, не подключённый к устройствам пользователя.
В том же сценарии старый код зависает при остановке после заморозки сервера,
новый завершает её менее чем за миллисекунду на тестовой машине.

### Основания для корректировки рекомендаций (результаты этапов 2–5 ниже)

- Игровой режим: определять игры по явным правилам/идентификаторам приложений,
  событиям запуска и настоящему fullscreen. Нативный Wayland сам по себе
  не является признаком игры. Сохранять и восстанавливать пользовательские
  параметры; VRR — только по явному разрешению для конкретного монитора,
  с проверкой пользователем и возможностью отката. Отсутствие жалобы за пять
  секунд не доказывает отсутствие мерцания.
- Direct scanout и управление вводом: использовать API закреплённого Hyprland.
  `hs.*` относится к Hammerspoon/macOS. Чувствительность мыши не управляет
  batching ввода, а USB `power/control` не задаёт polling rate.
- Приоритеты и питание: отдельные области приложений/CPUWeight, поддерживаемый
  интерфейс power-profiles-daemon или GameMode с восстановлением состояния.
  Не ограничивать `user.slice` через CPUQuota: 100% означает один CPU,
  а не всю производительность системы. Отдельных процессов dock/dashboard
  у оболочки нет, применять квоты к отдельным виджетам невозможно.
- Кэш render-dispatch: хранить выбранный callback, не указатель на элемент
  изменяемого vector; пересчитывать выбор при изменениях регистрации.
  Кэш blur должен учитывать монитор, размер, содержимое/ревизию обоев,
  sigma и жизненный цикл GL. Для живых обоев одного имени файла недостаточно.
- Frame pacing: использовать синхронизацию Qt Quick/Wayland и частоту монитора.
  Не добавлять busy-wait или принудительные 60 FPS. Текстурные атласы сначала
  проверять профилированием существующего batching Qt; Canvas 2048×2048
  сам потребляет память и требует перерисовки.
- Шейдеры: использовать существующий QSB-пайплайн и подходящий runtime cache.
  `qmlcachegen` компилирует QML, не GPU pipeline; перенос пользовательского
  `~/.cache` в пакет не обеспечивает совместимость драйверов и Qt.
- Предзагрузка: только опциональная, с бюджетом CPU/памяти/IO и измерением
  запуска. Отдельные headless/minimized процессы не являются универсальной
  предзагрузкой; таймер не должен завершать приложение, которым уже пользуются.
- Термозащита/качество: применять существующие нативные метрики и hysteresis,
  учитывать типы датчиков. Снижение качества — отдельная согласованная политика,
  не запись поверх пользовательского предпочтения reduced motion.
- Память и сеть: не запускать периодический `drop_caches`/ручную compaction
  как универсальное ускорение. `TCP_NODELAY` задаётся на сокете приложения;
  `net.ipv4.tcp_nodelay` не является таким глобальным переключателем.
  Увеличение буферов само по себе не гарантирует меньшего пинга.
- Crash reporter: отдельный ограниченный C++-сборщик с защищённым StateDirectory,
  лимитами размера/числа отчётов и обработкой watchdog/timeout, а не только
  `SERVICE_RESULT=signal`. Основная диагностика уже остаётся в journal/coredump.

Проценты прироста FPS и миллисекунды снижения задержки из предварительных
примеров не являются результатами измерений этой оболочки. Дальнейшие изменения
принимаются по воспроизводимому профилированию без ухудшения обычного визуального режима.

## Этапы 2–5: проверенные оптимизации и игровые политики

Система → **Производительность и игры** объединяет настройки игрового режима,
адаптивных эффектов, температуры и предзагрузки. Настройки валидирует C++
`RuntimePerformance`; они атомарно сохраняются в `~/.config/hics/performance.json`.
Изменения через страницу применяются сразу; ручное редактирование JSON читается
при следующем запуске. Хелперы выбираются рядом с wrapper (`HICS_HELPER_DIR`),
в том числе для пользовательского/Nix-префикса.
Автоматические политики, предзагрузка, изменения scanout/tearing и запросы
производительного профиля изначально выключены. Обычный внешний вид сохраняется.
При выключенных политиках контроллер не запускает таймер измерений.

### Что внедрено

- Игры распознаются по явно заданным маскам application ID, с отдельным списком
  исключений. В Hyprland `fullscreen=1` означает maximized, а бит `2` —
  настоящий fullscreen. По умолчанию маски — `steam_app_*` и `gamescope`,
  а Steam/Lutris/Heroic как лаунчеры исключены. Потеря фокуса завершает
  автоматический режим; ручное отключение действует до смены игрового процесса.
- Применённые опции сохраняются и восстанавливаются. Изменение настроек во время
  игры возвращает переставшие использоваться опции; перезагрузка конфигурации
  обновляет базовый снимок перед повторным применением. Blur и тени имеют одного
  действующего владельца — `Effects`, без конкурирующей записи из `Colours`.
- Direct scanout: сохранить исходное значение / auto для игрового content type /
  разрешить полноэкранной игре. `general:allow_tearing` отдельно разрешается
  пользователем, не выдаётся за управление input batching или гарантию scanout.
  Это глобальное разрешение на время игрового режима, поэтому затрагивает и
  другие полноэкранные окна. Реальное включение scanout зависит от композитора,
  буфера, драйвера и вывода.
- VRR остаётся настройкой конкретного экрана с существующим подтверждением и
  возвратом по таймеру. Добавлен режим fullscreen games (`3`), уточнено отличие
  fullscreen (`2`) от постоянного включения (`1`). Автоматического «теста на
  отсутствие мерцания» нет; распознавание приложения оболочкой не подменяет
  content type, используемый самим Hyprland.
- `hics-game-lease` запрашивает GameMode через его PIDFD API или удержание
  `performance` через `HoldProfile`. Выбирается один поставщик политики питания,
  чтобы они не спорили за governor. Приоритеты процесса/IO и governor делегируются
  дополнительному пакету `gamemode`, а не дублируются через `renice`/общий cgroup.
  Хелпер освобождает запросы при EOF, завершении игры и завершении оболочки;
  отдельно обработан ответ на приобретение lease, пришедший уже после EOF.
  Ручная смена профиля имеет приоритет согласно контракту power-profiles-daemon.
- Предпочтения дока и живых обоев отдельно определяют поведение во время игры.
  Визуализатор не собирает аудио в игровом режиме; существующая подписка на
  аудиосервис освобождается при выгрузке его Loader.
- `drawTex` выбирает callback при изменении регистрации, а не перебирает
  участников на каждой текстуре. В кэше хранится значение callback, не указатель
  на элемент вектора. Единственный общий хук и передача его владельца сохранены.
- Стабильный overview больше не создаёт кадры с частотой монитора. Полная частота
  сохраняется для анимаций/перетаскивания, а последняя фаза обязательно рисуется.
  Коммиты клиентов и обоев продолжают вызывать обычный damage. Медленная проверка
  heartbeat не рисует кадр. Кэш blur сохраняется между входами; коммиты обоев,
  замена поверхностей/монитора, масштаб, размер, transform и формат цвета
  инвалидируют его. Живые обои продолжают обновляться по коммитам.
- Для окон `StyledWindow` C++-компонент `GraphicsCache` задаёт отдельные локальные
  Qt pipeline cache по логическому окну/экрану/API/версии Qt до инициализации
  scene graph. Явные настройки окружения и запрет shader cache соблюдаются.
  Проверка совместимости устройства и драйвера остаётся у Qt. Пользовательские
  кэши не копируются в пакет. QSB уже компилируется через `qt_add_shaders`.
- CPU-метрика читает только агрегатную строку `/proc/stat`, учитывает `steal`
  и не выдаёт статистику с момента загрузки за первый интервальный замер.
  GPU/sysfs-метрики и температуры получает спящий C++-хелпер; для NVIDIA — NVML, без нового `nvidia-smi` на
  каждый tick. Даже вызов драйвера изолирован от GUI: timeout 1,5 с, backoff 30 с,
  максимум один запрос. Резервный `nvidia-smi` ограничен 0,2 Гц и двумя секундами.
- Адаптивное качество: три высоких отсчёта для снижения, пять низких для
  восстановления, минимальная пауза между изменениями и настраиваемый нижний
  уровень. Уровни: обычный / меньшие тени / без blur и теней. Неизвестная нагрузка
  не считается высокой или низкой. Пользовательские reduced motion, контраст,
  значения внешнего вида и файлы этих предпочтений не перезаписываются.
- Температура: известные CPU/GPU hwmon и NVML, максимум корректных значений,
  отдельные пороги включения/возврата и три холодных отсчёта для восстановления.
  При нагреве приостанавливаются фоновые эффекты/обои и снимаются игровые
  запросы питания. Это уменьшает работу оболочки, но не гарантирует отсутствие
  троттлинга игры и не заменяет термозащиту ядра.
- Предзагрузка: локальные переходы application ID, максимум 256 записей,
  ограниченный файл истории с правами `0600`, явный allowlist, минимум совпадений,
  confidence, срок прогноза и cooldown. Учитываются CPU, `MemAvailable`, PSI
  памяти/IO, батарея, fullscreen, игра, блокировка и температура. Только
  `POSIX_FADV_WILLNEED` для ограниченного префикса исполняемого файла на известных
  локальных ФС; никаких запущенных приложений и последующего убийства их окон.
  Медленный поиск/открытие файла выполняет отдельный `hics-prefetch` с nice 19,
  idle IO, отменой через EOF и тайм-аутом со стороны контроллера. GUI и деструкторы
  не ждут заблокированного IO. Подсказанные ядру байты не выдаются за доказанный
  объём прогретых страниц или гарантированное ускорение приложения.
- `hics-crash-report` вызывается из `ExecStopPost` для неуспешного завершения,
  включая watchdog, timeout, signal, core-dump и exit-code. Частный systemd
  `StateDirectory=/var/lib/hics/crashes`, права `0700/0600`, не более 10 отчётов; при создании нового удаляются отчёты старше семи
  дней. Журнал/описание coredump — до 256 КиБ каждый, ограниченное время subprocess.
  Журнал фильтруется по unit и invocation, если он доступен; coredump — последний
  для unit за минуту (запись coredump может появиться позже). Дампы памяти не
  копируются, отчёты не отправляются. Ошибка сборщика не мешает рестарту брокера.

### Все 24 рекомендации: результат проверки

| № | Рекомендация | Решение |
|---|---|---|
| 1–3 | Watchdog, остановка аудио, лимиты D-Bus | Реализовано первым этапом; сохранено и повторно проверено |
| 4 | Crash reporter | Ограниченный C++-сборщик и ExecStopPost |
| 5 | Переполнение memory pool | Указанного пула нет; проверены размеры и ограничено чтение |
| 6 | Render-dispatch cache | Выбор callback только при изменениях |
| 7 | Blur cache | Повторное использование с событийной инвалидацией |
| 8 | Quantum 128 вместо 512 | Не применён: увеличивает частоту callback, требует накопления для анализа; выигрыш CPU/визуала не доказан |
| 9 | Lazy PipeWire | Уже реализовано подписками; без искусственных sleep |
| 10 | Frame pacing | Сохранена синхронизация Qt/Wayland и частота экрана, убраны лишние кадры overview; busy-wait исключён |
| 11–12 | Auto GameMode и эффекты | Настраиваемые политики и восстановление состояния |
| 13 | Приоритеты игры | GameMode PIDFD lease; без записи PID в произвольный cgroup |
| 14–15 | Scanout и VRR | Поддержанные настройки и явный выбор пользователя |
| 16 | Предиктор | Ограниченные подсказки page cache вместо запуска скрытых приложений |
| 17 | Input latency | Ошибочные записи sensitivity/USB power исключены; не являются input batching/polling rate |
| 18 | CPU governor | Системный поставщик политики с жизненным циклом lease; без глобальной CPUQuota |
| 19 | Thermal protection | C++-политика с гистерезисом и приостановкой фоновой работы |
| 20 | Texture atlas | Используется существующий atlas Qt, подтверждён при рендеринге иконок; отдельный Canvas исключён |
| 21 | Shader compilation/cache | Существующий QSB + отдельный runtime cache окон |
| 22 | Периодическая compaction/drop_caches | Исключено: системные задержки и повторный IO; управление остаётся ядру |
| 23 | Сетевой sysctl-тюнинг | Исключён: глобального tcp_nodelay нет, универсальное снижение ping не подтверждено |
| 24 | Adaptive quality | Опциональная нативная политика с бюджетом опроса и восстановлением |

### Документация, использованная при проверке

- [Qt Quick renderer: batching и texture atlas](https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph-renderer.html).
- [Qt graphics configuration: pipeline cache, время настройки и проверка совместимости](https://doc.qt.io/qt-6/qquickgraphicsconfiguration.html).
- [systemd.service: ExecStopPost, watchdog и результаты завершения](https://freedesktop.org/software/systemd/man/latest/systemd.service.html).
- [systemd resource control: CPUWeight и смысл CPUQuota](https://www.freedesktop.org/software/systemd/man/258/systemd.resource-control.html).
- [power-profiles-daemon: HoldProfile/ReleaseProfile и приоритет ручного выбора](https://freedesktop-team.pages.debian.net/power-profiles-daemon/gdbus-org.freedesktop.UPower.PowerProfiles.html).
- [GameMode 1.8.2: реализация PIDFD D-Bus API](https://github.com/FeralInteractive/gamemode/blob/1.8.2/daemon/gamemode-dbus.c).
- [NVML: lazy init и парные init/shutdown](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlInitializationAndCleanup.html).
- [Linux VM: стоимость compaction и drop_caches](https://docs.kernel.org/admin-guide/sysctl/vm.html).

Для Hyprland дополнительно проверены публичные `hyprctl descriptions -j` и
`getoption` именно установленной закреплённой версии. Код `hs.*` из примеров
не переносился: это Hammerspoon, а не API Hyprland.

### Воспроизводимые проверки

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/integration_performance_ui.py
python3 tests/integration_graphics_cache.py
python3 tests/integration_controls_ui.py
python3 tests/integration_settings_design.py
python3 tests/integration_canvas_input.py
python3 tests/benchmark_overview_idle.py --baseline /path/to/matching-old-native --seconds 10 --rounds 3
```

Тесты GameMode и питания используют частный D-Bus с имитаторами, включая поздний
ответ на запрос после EOF. Проверка GPU использует имитатор NVML с зависанием:
GUI heartbeat продолжает работать, запрос завершается по тайм-ауту и не создаёт
новый helper в backoff. Проверки графики запускают отдельные вложенные
композиторы и собственные приложения; рабочие плагины пользователя не заменяются.

### Измерения на рабочей машине (25 октября 2026)

- 10 чтений GPU: десять `nvidia-smi` — **0,146 с CPU** дочерних процессов,
  один native helper с десятью запросами — **0,018 с CPU**. Wall time:
  0,201 против 0,024 с. Это измерение конкретного пути опроса, а не ускорение
  всего рабочего стола в восемь раз. Команда:
  `python3 tests/benchmark_gpu_polling.py --samples 10`.
- Idle overview, три чередующихся прогона по десять секунд, одинаковый вложенный
  композитор: медианы **3,557% → 3,554% одного ядра**. Разница практически нулевая
  и не доказывает снижения общей CPU-нагрузки композитора в этом сценарии.
  Отдельно подтверждено прекращение синтетических кадров после перехода и
  однократное вычисление blur; эти изменения не выдаются за измеренный рост FPS.
- GPU fixture с зависшим NVML оставляет GUI heartbeat работающим; тайм-аут
  и backoff не запускают дополнительные helper-процессы. Синтетические high/low
  GPU/temperature проходят полный цикл снижения, термоограничения и возврата
  качества в `python3 tests/integration_adaptive_quality.py`.

Итоговая проверка: 251 unit/native-тест прошёл; дополнительно прошли вложенные
GUI/композиторные сценарии, адаптивный цикл high/low/thermal, GPU timeout/backoff,
отключение shader cache окружением и dock-pointer с исчезновением hover во время
удержания кнопки. Текущие настройки монитора и работающие плагины не менялись.

### Window modes, client decorations and GTK controls (package 51)

Application rules now select all modes or one of stacking, scrolling, tiling and
canvas. Named Hyprland rule handles are enabled/disabled when the mode changes;
there is no polling, configuration reload or generated IPC script on each focus.
Editing preserves rule priority; explicit up/down controls change it. Static
placement affects newly opened windows in the chosen mode. Dynamic appearance
updates existing matches and reverts when its rule becomes inactive.

The editor separates shell titlebars (`hyprbars:no_bar`) from compositor
`decorate`, borders, rounding, shadows, blur, animations and activation policy.
Appearance overrides support inheritance. Advanced matching includes modal/XWayland
conditions. Own-header and PiP presets retain literal application identity when
switching to regular-expression title matching. Code/Code OSS/VSCodium use client-header defaults; an explicit Show rule overrides
them for installations configured with native headers. Hiding a shell header
cannot remove a header painted inside an application's content.

Geometry calculations query the native decoration's actual visible height,
including user overrides and `decorate=false`. Older plugins lack the named
query and retain the existing fallback until the next login; unknown animation
operations are never invoked. Browser PiP titles are handled on map and on late
title changes, remain pinned/floating, preserve aspect ratio and receive no
extra shell header. A small live PiP registry raises them without stealing focus
when another window activates; closed windows are removed from the registry.

`hics/window-controls.json` defines physical left-to-right button order and side
for shell bars and GTK3/4. GTK receives settings.ini plus the desktop GSettings
button-layout property forwarded by the GTK settings portal. Flatpak private
settings follow the same preference without broader filesystem permissions.
The setting participates in configuration history and profiles. GTK can omit
unavailable actions or override decoration-layout inside an application; modal
file choosers do not necessarily provide minimize/maximize buttons.

Real GTK4 file-chooser rendering exposed a hard-coded light bottom border in
GTK's built-in `filechooser #pathbarbox` style. The generated palette overrides
that node's border specifically, along with header and table-header surfaces;
libadwaita also receives headerbar border/shade CSS variables. This preserves
transparent popup exteriors. Already-running GTK applications may require
reopening to reload their CSS providers.

Validation: native stacking screenshots cover server headers, Telegram,
Photocraft, GTK, Code, forced Code OSS headers and disabled decorations; scoped
rule handles are checked across mode transitions. A late browser title becomes
PiP. The settings test opens a populated editor and exercises its PiP preset.
GTK2/3 colours, GTK4/libadwaita button states, actual GTK3/4 file choosers and an
AdwToolbarView header are rendered; button layout and bright horizontal stripes
are checked with private settings and fixture files.

Primary references:
- https://wiki.hypr.land/configuring/core/rules/window-rules/
- https://docs.gtk.org/gtk3/property.Settings.gtk-decoration-layout.html
- Installed GTK 4.24.1 Default stylesheet resource, including `filechooser #pathbarbox`.

### Stacking drag crash and open-window rule picker (package 52)

The report copied to Documents (`hyprlandCrashReport3470459.txt`) aborts in the
stacking motion listener. A nested real-pointer reproducer with package 51
confirms the assertion `tried to lock a CWeakPointer over a CUniquePointer`.
Window decorations are unique-owned; their weak references must be borrowed on
the compositor event-loop thread, never promoted with `lock()`. The drag-height
lookup now uses that ownership model. A scoped reentrancy guard prevents nested
synthetic pointer events during dragBegin/focus/z-order changes from overwriting
the active transaction.

Native mouse bindings consume motion/release before public mouse signals.
The same handler therefore reconciles an active drag at the existing RENDER_PRE
stage, before GL drawing, and finalizes a completed drag once. It creates no
idle polling timer or synthetic frames. Saved maximize state is also restored
when a native/client move has already cleared its client flag. Click-only and
invalid-window exits clear transaction state so later frames do not repeat it.

Broad Helium/Brave/Vivaldi class-wide header suppression is removed. Browser
main windows keep the stacking header; only matched PiP windows lose it unless
a user explicitly overrides their application policy. The rules page provides
an explicit open-window picker with application and title labels. Picking a
normal window fills literal application matching; an optional switch includes
its exact title. PiP defaults to title matching so its rule does not affect the
browser's main window. Existing rule IDs and non-matching options are retained.

The recovery compositor intentionally uses its own generated configuration.
For this incident, US/RU and Alt+Shift were applied directly to that instance and
persisted in its runtime recoverycfg.lua, with a backup. Its normal user keyboard
configuration was already correct and was not replaced.

Regression: `tests/integration_stacking_drag.py` reproduces the abort with
`HICS_TEST_NATIVE_DIR=/usr/share/hics/native` before upgrading package 51. The
fixed variant exercises maximized server-header drag with PiP; setting
`HICS_TEST_DRAG_CSD=1` exercises a native mouse binding on a headerless window.
Only the nested test surface is resized in its parent, so recovery-mode tiling
cannot invalidate input coordinates. No host plugins are loaded/unloaded by
these tests. The settings test also checks normal-window and PiP selection.

### Fullscreen-to-maximized work area (package 53)

Stacking's maximize rectangle uses Hyprland's actual monitor reservations,
including all four dock edges, bar, extra panels and logical output scale.
Previously it was recomputed on fullscreen/monitor layout changes only. The
shell's layer surfaces can restore their exclusive zones later than fullscreen
exit; that late reservation is not necessarily a monitor layout event. A window
could consequently retain the fullscreen-sized rectangle behind the dock.

The existing native RENDER_PRE callback now compares reserved-area snapshots.
Only a change queues one coalesced event-loop callback, outside the rendering
transaction, to resize eligible maximized floats. The steady path performs no
allocations, Lua/IPC calls, window traversal or geometry updates; no recurring
timer or synthetic frames are added. Minimized, pinned, fullscreen and normal
windows are excluded. The saved normal rectangle remains untouched. Monitor
layout changes reuse the same Lua function and unchanged rectangles are skipped.

Fullscreen callbacks can see an old client state while the controller updates
its internal/client flags sequentially. The listener records fullscreen entry
and coalesces settlement per live window, cancelling on close. It handles direct
return to client-maximized state and a round trip inside one IPC request.

`tests/integration_stacking_workarea.py` creates real layer-shell reservations,
hides them in fullscreen and restores them 300ms after exit. Package 52's native
plugin reproduces bottom-dock overlap with this regression fixture. The fixed
plugin checks all four edges with server/client headers, combined bar reserves,
visible dock resizing, rapid fullscreen transitions and restore of the original
normal rectangle. The same cases pass with output scale 1.25. It uses private config and snapshots native binaries; the
host compositor's plugins are never reloaded by the test. Both stacking drag
regressions (five server-titlebar and five headerless drags with PiP) also pass.

## Время запуска оболочки

Подготовка сеанса запускает независимые проверки доступности, восстановления
конфигурации и экранов параллельно с восстановлением палитры. Все проверки
завершаются до запуска QML; защита отката не переносится на поздний таймер.
Повторный запуск уже работающего runner сначала проверяет блокировку и не
переприменяет тему. Неизменившиеся файлы палитры сохраняют inode и время изменения.

В журнале `hic-session.service` строка `hics startup: preparation …s` показывает
время подготовки. Следующая `Configuration Loaded` относится к загрузке QML,
а не гарантирует момент первого показанного кадра. `systemd-analyze --user blame`
для службы Type=simple не измеряет время до появления панели.

`python3 tests/benchmark_startup.py` сравнивает три запуска полного QML-интерфейса
в отдельном вложенном композиторе: первый с новым каталогом кэша, затем два
повторных. `--check-ui` дополнительно проверяет первое открытие отложенно
загружаемых настроек и тура. Обе D-Bus шины теста изолированы от оборудования;
результат не заменяет измерение настоящего входа в систему на холодном диске.

Для отдельных измерений нового QML-кэша и первого кадра используйте
`python3 tests/benchmark_startup.py --fresh-cache --evict-source --probe-frame`.
Выбрасываются только страницы временных копий ресурсов теста; библиотеки и
драйвер могут оставаться прогретыми. Это не замена настоящего входа после
перезагрузки. Событие `hics startup: first visible frame submitted` отделяет
передачу первого видимого кадра от `Configuration Loaded` и запуска фоновых
интеграций. Подробная методика — в `docs/UX_INTEGRATION_AUDIT.md`.
