# Текущее состояние проверки устойчивости HICS

Полная кампания не завершена. Подробные воспроизведения, причины ошибок,
коммиты и ограничения собраны в [журнале испытаний](RELIABILITY_CAMPAIGN.md).
Этот обзор отделяет проверенные сценарии от ещё открытых задач.

## Что установлено

- Fresh CachyOS ВМ: `hic-shell 1.1.1-117`; locked upgrade сохранил окно, UI, runner и207 bindings. Новый boot/login проверен по загруженным SHA/inode.
- Основная CachyOS ВМ: `hic-shell 1.1.1-117`; locked upgrade сохранил UI/runner/kitty и207 bindings. Новый boot/login и loaded SHA/inode проверены;120 settings cycles без ошибок QML.
- Рабочий хост: `hic-shell 1.1.1-117`; runner1183724, NRestarts0 и все5 текущих окон сохранены. Следующий normal login загрузит установленные файлы.
- Runtime117 сохраняет проверенный Qt6.12.0 из116 и добавляет события видеозахвата в QS0.3.2. Пакет117 проверен в обеих ВМ и установлен на хосте; обычный повторный вход нужен для загрузки новых образов.

## Приёмка117: PipeWire и захват экрана

Событийный индикатор переиспользует существующее PW-соединение вместо
пятисекундного pw-dump. Настоящие короткие захваты и потеря сервера проверены
в ВМ. Исправлена systemd lifetime связь внешнего capture backend, который
иначе оставался со старым core: после restart/SIGKILL сервера новый захват
снова работает.80 isolated modules/485tests проходят с6context skips;
4 новых native сценария отдельно чисты под ASan/UBSan/LSan. Пакет117 собран и установлен в fresh ВМ;60 циклов настроек прошли без
ошибок QML/рестартов.8 installed Qt gates пройдены после исправления IPC
пути вложенного тестового композитора; первый failed прогон сохранён. Пакет117 установлен также на хосте с сохранением сессии. [Подробности и открытые находки](PIPEWIRE_CAPTURE_TESTING.md).

## Последние проверки Qt (28 октября 2026)

Установленный116 проходит8 portal/input/audio/video/SQL gates в fresh ВМ,
обновление под блокировкой в обеих ВМ и120 открытий/закрытий настоящих настроек
в основной ВМ. После normal reboot/login в обеих ВМ проверены новые загруженные
QS/Qt/native images, first-frame ready,207binds, NRestarts0 и отсутствие ошибок
конфигурации/failed units.6 native EGL ASan/LSan процессов проверяют sharing,
рамку и сохранение исходного контекста;20 VideoOutput lifecycles с6 кадрами
каждый проходят ASan/LSan и проверку цветного render. CSD/frameless и тени
сравниваются попиксельно в GL/GLES, threaded Quick и масштабах125%/200%.

Общий79-модульный прогон на чистом2b7a11a:478 тестов,0failed modules,6 явных
пропусков. GPU recovery opt-in дополнительно проходит9 тестов, включая настоящий
30-секундный backoff. Failed-exec cleanup leak исправлен и проверен28 native
desktop tests,2 focused ASan desktop checks и50 watcher failed-exec teardown.
В одном сопоставимом120-cycle software-VM прогоне RSS после настроек составил
807036KiB против984920KiB у113; это наблюдение, не универсальный cold/GPU benchmark.
587-байтовый global Fontconfig LSan residual и аппаратная GPU-приёмка остаются
открытыми. Подробности — в последних разделах [журнала](RELIABILITY_CAMPAIGN.md).

## Регрессионный прогон кандидата 92

`unit-context92/manifest.json`: чистая revision `d298aab`, 68 модулей,
399 тестов, без ошибок и таймаутов; 5 пропусков из-за изоляции окружения.
Пропущенные случаи отдельно выполнены в нужном контексте: scopes 2/2,
network QML 2/2, broker runtime 8/8 (часть broker-тестов при этом повторена).
Это граница unit/integration покрытия, а не проверка каждой возможности DE.
Исправления HISTORY-001..003 появились после этого общего прогона. Для пакета93
отдельно проверены 17 старых архивов гостя, новый снимок и отказ на повреждениях;
это не повтор всей общей регрессии.

Полное декодирование медиа: 42 GIF/JPEG, 2508 кадров, и 18 MP4 без decoder errors.
Визуальная проверка всего содержимого и замена старого брендинга ещё открыты.

После reboot ВМ пакет93 также сообщает first-frame ready, NRestarts=0,
configerrors пуст. Наблюдение готовности выполнено на uptime26.94s — точная
задержка появления интерфейса не измерена; host disk cache не очищался.
Чистый профиль первого запуска этим reboot не проверен.

## Проверенные сценарии

| Область | Что подтверждено | Граница доказательства |
|---|---|---|
| Обновление | Обновление ВМ из безопасного режима сохраняет recovery UI, приложение, binds и конфигурацию Hyprland | Это не проверка всех вариантов обновления и отключения питания в транзакции |
| Возврат из safe mode | Пакет93 запускается кнопкой recovery UI, сообщает ready, обновляет рабочую точку; меню приложений ищет и закрывается Escape | Прогретый запуск, не холодный login и не проверка всех popup |
| Падения | Два намеренных SIGKILL переводят shell в safe mode; независимое приложение сохраняет PID/scope | Не воспроизведение естественного случайного падения |
| Откат | Реальный recovery UI запускает пробу; таймер возвращает содержимое и отсутствие файлов; экраны не меняются | Произвольное внутреннее состояние приложений не восстанавливается |
| Повреждения | Неверные типы/JSON, FIFO, ссылки, большой файл, повреждённая policy/journal не должны обрывать проверенные IPC-сценарии | Не исчерпывающий перебор всех файлов и полей |
| Отказ записи | Read-only CONFIG и частичный подставленный ENOSPC сохраняют journal для повтора | Не отказ любого block device |
| Полное хранилище | Настоящий tmpfs STATE 2 MiB: ENOSPC, доступный IPC, отсутствие цикла записей, восстановление того же процесса | Корневой раздел и `/run` одновременно не заполнялись |
| Расширения | Плохие preferences/manifests изолируются, traversal/download ограничены, ошибки обновления сохраняют версию | Legacy QML не является изолированным sandbox |
| Медиа | Полное декодирование GIF/JPEG/MP4 проверено отдельно | Читаемость файла не подтверждает актуальность брендинга или визуальную корректность |

Команды и fixtures находятся в `tests/`: `run_stability.py`,
`vm_package_upgrade.py`, `vm_recovery_cycle.py`, `vm_configuration_enospc.py`,
`test_configuration_watcher.py`, `integration_shell_recovery.py`.
VM-сценарии используют отдельный профиль и требуют тестового гостя; они не
предназначены для запуска разрушительных проверок на рабочем сеансе.

## Что ещё не позволяет объявить работу завершённой

- Повторить установку с нуля и полный пользовательский маршрут для итогового
  кандидата; проверить offline/прерванные установки и аварийное восстановление.
- Проверить все действия интерфейса, сочетания, виджеты, анимации, масштаб,
  несколько экранов, доступность и сохранение состояния при обновлениях моделей.
- Закрыть оставшиеся lifetime/permission сценарии порталов, IPC/D-Bus/Wayland,
  нагрузочные проверки, длительную работу и границы редактирования настроек.
- Проверить физическое оборудование: сеть/VPN, звук/микрофон, накопители,
  мониторы, VRR/HDR, Bluetooth, печать, планшеты, прошивки и датчики.
- Завершить визуальный аудит и перезапись остальных исторических демонстраций.
  `panel-tools.gif` заменён реальной записью пакета95, `dashboard.gif` — пакета102.
  Проверка всей медиатеки и записей тура ещё не завершена.
- Проверить финальные установленные артефакты и документацию после исправлений,
  не подменяя эту проверку зелёными unit-тестами.

## Повторная проверка: безопасный режим и откат (27 октября 2026)

Проверка исходников подтверждает существующие механизмы: ограниченный журнал
падений, отдельный recovery QML, рабочую стартовую точку, пробное применение
через независимый configuration guard и возврат по таймеру. Они не заменяются
новой параллельной системой настроек.

Исправлен ручной вход/выход из safe mode при повреждённом служебном журнале:
некорректный JSON/UTF-8, FIFO и symlink больше не блокируют команду.
Замена атомарная, внешний файл ссылки не читается и не изменяется. Если новую
запись сохранить нельзя, перезапуск службы не запрашивается. Повседневного
таймера, процесса или дополнительного чтения в обычном режиме не добавлено.

Приоритет дальнейшей приёмки:

1. Безопасность переходов обычный режим ↔ recovery при session lock и отказах
   systemd; независимость приложений и сохранение ввода/раскладки.
2. Откат незавершённой пробы после падения UI/guard, конфликт с более поздним
   редактированием, повреждение журнала и отказ записи.
3. Единый понятный маршрут восстановления в интерфейсе: причина ошибки,
   пробное восстановление, подтверждение, оставшееся время и повтор при отказе.
4. Затем остальные функции DE: каждую принимать по реальному действию,
   обработке ошибки, настройкам и доступности, а не по наличию страницы.

Этот раздел фиксирует аудит и начало исправлений, а не завершение всего DE.

Проверено после исправления: `test_shell_recovery.py` — 27/27,
`test_desktop_completion.py` — 32/32, `test_configuration_watcher.py` — 3/3.
`integration_shell_recovery.py` прошёл в отдельном вложенном Hyprland:
настоящий recovery QML прочитал рабочую точку, запустил защищённую пробу и
вернул реальные тестовые настройки. Рабочая конфигурация пользователя и
установленный на хосте пакет этой проверкой не изменялись.

В исходниках ручной переход переработан на IPC к владельцу UI и намеренный
exit75/76 с повторным запуском runner: внешнего systemctl restart больше нет.
29 recovery-тестов, 2 проверки сохранности процессов, 32 desktop-теста и
реальный IPC handler под Quickshell прошли. Проверка handler использует
подставное состояние lock; настоящий WlSessionLock/PAM и установленный новый
пакет остаются обязательной следующей проверкой. Пакет95 этого изменения не
содержит.


Пакет97 проверен в установленной CachyOS ВМ с настоящим session lock:
locked on/resume отвергнуты без изменения PID/журнала, после PAM unlock
три полных normal→recovery→normal цикла сохраняют runner9800, app2593 в
отдельном scope, 207binds, пустой configerrors и NRestarts=0. Последний normal
UI сообщает sessionHealth.ready=true. Гонка одновременных lock/transition,
отказы диска в момент смены режима и полный fresh install97 ещё открыты.
Выявленный устаревший generated shell.qml исправлен configure_file(COPYONLY);
root QML пакета97 побайтно сверен с исходником. Пакет96 не годится как
доказательство работоспособности новых переходов: handler в нём отсутствовал.

После пакета97 исправлена очистка runner при отказе записи extension marker:
сигналы, wakeup_fd и сокеты/pipe освобождаются даже при ошибке. SIGTERM/INT
получает приоритет над принятым mode transition. Проверены инъекция ENOSPC,
настоящий SIGTERM в момент commit и отсутствие FD leaks в этих сценариях.
Новая установка этих исправлений и реальный отказ хранилища ВМ не проверены.

Подготовка сеанса теперь отменяет ожидание помощников при stop с порцией
ожидания до250ms; незавершённые дети убиваются и reap до выхода runner.
5 startup-тестов, включая три настоящих долгоживущих процесса, прошли.
Обычный запуск не получает дополнительной задержки. Изменение пока только в
исходниках; проверка установленного пакета и остановки systemd во время
preflight остаётся открытой.

Дополнительный реальный preflight-тест обнаружил потомков, переживавших уже
завершившегося helper. Исправлен порядок ожидания/reap через pidfd + WNOWAIT:
до освобождения PID останавливается принадлежащая ему группа. Тест проверяет
3 managed потомка и сохранение3 detached процессов. Все6 startup-тестов и29
recovery-тестов прошли. Аппаратный startup и установленный новый пакет ещё не
проверены; пакет97 этого изменения не содержит.


Пакет98 включает последние runner cleanup/cancellation/descendant исправления.
Проверены locked upgrade с сохранением владельца блокировки и приложения,
побайтовое совпадение packaged runner/root QML с исходниками,6 startup-тестов
против установленного кода в госте (не только checkout). После PAM unlock
новый runner14832 сообщил first-frame ready,3 пары переходов normal/recovery
сохранили app2593,207binds и пустой configerrors. Evidence:
locked-upgrade98.json, startup98-installed.log, transition98-unlocked.json
в закрытом lab. Не проверены ещё systemd stop именно во время установленного
preflight, simultaneous lock/transition и fresh install98.

Подтверждены дополнительные проверки после установки98:

- Настоящий systemd stop отдельного unit с installed runner и injected
  preflight stalls:0.199s, Result=success/ExecMainStatus=0,3 helper+3 descendant
  завершены, основной сеанс и app сохранены. Event endpoint/GTK — fixtures.
- Настоящий WlSessionLock во вложенном Hyprland и конкурентные lock/transition
  IPC: наблюдались обе очередности победителя, нет покинутой блокировки после
  принятого выхода75/76. Production transition/requestLock взяты из исходников;
  authentication в этой изоляции подставная, не PAM.

Это закрывает указанные узкие сценарии; массовый race stress, реальный отказ
хранилища и чистая установка итогового кандидата всё ещё требуются.

Новая независимая CachyOS ВМ cachyos-fresh98 (SSH22281,2GiB) подтвердила
чистую пакетную установку98 через install.sh: до неё отсутствовали HICS,
Hyprland, Python и emoji font. Pacman загрузил зависимости, installer завершился
0 за50s;3105package files/0missing, system services enabled+active, mandatory
user units globally enabled, failed units нет. Первый графический вход и тур
на чистом профиле ещё не проверены. Исходная ВМ22280 продолжает существовать.

В чистом госте98 выполнен первый TTY/PAM login и hics-start: ready=true,
NRestarts=0, configerrors пуст, тур автоматически fullscreen на русском.
Проверены реальные поиск en_US, выбор и применение через встроенный polkit:
/etc/locale.conf стал en_US.UTF-8, тур перешёл к раскладкам. Через UI добавлена
Russian, применены us,ru/Alt+Shift; реальная клавиатура переключилась туда и
обратно во время тура. Evidence: first-login98.json, first-tour-keyboard98.json
и screenshots закрытого cachyos-fresh98 lab. Остальные7 страниц, завершение,
пропуск и повторный вход ещё требуют проверки. Убрана непереведённая None в
исходнике выбора сочетания; installed98 ещё со старой надписью.

Tour step4: настоящий display preview125% в fresh98 автоматически вернулся
к100% через15.4s. Найдено отставание UI модели (поле осталось125%); исправлено
событийным refresh мониторов на завершение пробы. Новый real-QML regression
падает без исправления и проходит с ним;13 display unit tests и6 интеграционных
сценариев прошли. Installed98 ещё без этого изменения. Требуют проверки:
стабилизированный layout125%/confirmation в туре и оставшиеся страницы тура.

В fresh98 тур проверен до step7: UI Stacking применился; Light/Dark меняют
scheme и GTK preferences;14 обоев скачаны, декодированы и проверены по
attribution hashes, выбор сохраняет реальный wallpaper path. Это не полнота
работы окон/внешних приложений. Открыты storage/features/ready и выход из тура.
Найден скрытый decode демонстрации под lock screen; source fix паузит player
по PerformancePolicy.locked/visible. Real-player regression падает без gate
(frames4→40) и проходит с ним (pause/resume). В installed98 этого fix ещё нет.

Первый нормальный маршрут всех10 страниц тура в fresh98 доведён до завершения.
Диски отображены согласно lsblk, configuration-history inspection открывается
и Back возвращает в тур. Finish сохраняет completed/autoShowfalse, снимает
submap и guard; панель возвращается. Super+Enter открыл Kitty в независимом
scope. После coordinated UI reload приложение живо, ready=true, configerrors
пуст, onboarding layer отсутствует. Evidence tour-finish98.json и screenshots.
Это не проверка каждого контрола, Skip и полного logout/login. Добавлен перевод
Estimate; после98 source fixes ещё не проверены новым установленным пакетом.

Гость fresh98/SSH22281 обновлён до99 при настоящем lock: процессы, приложение,
208binds и конфигурация сохранены. Исходный гость22280 по-прежнему98.
Пакет99 содержит последние QML/translation fixes; target i18n пересобран,
5 QML артефактов побайтно сверены. Отдельный installed QML probe реально
переводит Estimate→Оценка. Главный UI10609 ещё старый, поскольку владелец lock
сохранён: требуется нормальный unlock/transition и проверка исправлений там.

Main UI пакета99 загружен после PAM unlock (runner6340/UI13037, app10432 жив).
Установленная проверка обнаружила неполноту исправления масштаба: снимок модели
обновлялся, но Menu присваиванием active разрывал binding SelectRow. Для5
параметров дисплея включён controlled selection. Также очищается старая backend
ошибка при новом успешном состоянии службы. Настоящий DisplayPage/Menu test
падает без каждого fix отдельно и проходит с обоими;13 unit tests прошли.
Эти изменения ещё не в99. При125% confirmation доступен, обычное settings window
частично за правым краем: позиционирование при scale change требует проверки.

Начат следующий этап устойчивости запуска: session_runner при OSError записи
shell/extension startup journal выбирает независимый recovery entrypoint,
не запускает обычную подготовку и capture plugins. Safe entrypoint не меняет
настройки расширений и не требует записи extension marker. Проверка реального
runner с подставным shell-child покрывает ENOSPC и EROFS отдельно для обоих
журналов; это fault injection, не запуск QML на действительно заполненном диске.
Прошли 30 recovery, 6 startup, 2 session restart и 3 configuration watcher tests.
Изменения исходников не установлены. Открыты реальный VM disk-full запуск,
ошибка записи coordinated transition и сохранность runtime при недоступном
XDG_RUNTIME_DIR; текущий fallback их не решает. Новых таймеров/демонов нет.

Дальнейшая проверка закрыла часть этого gate: настоящий source runner, штатный
hics-shell wrapper и реальный recovery QML запускаются в CachyOS98 при tmpfs
2MiB, заполненном до ENOSPC, и при remount read-only (EROFS). В каждом случае
проверены первоначальный mapped window и две последовательные IPC-команды
on/resume. Ошибка commit теперь сохраняет безопасный переход в памяти runner,
а не завершает его; нормальный запуск при недоступном журнале не разрешается.
Тест tests/vm_recovery_storage.py использует приватные XDG/отключённые D-Bus,
fixture event socket и установленный compositor/runtime. Сохранились основной
runner14832 и Kitty2593; пробные процессы завершены, tmpfs размонтированы.
Evidence: cachyos/recovery-storage-transitions-source100.json во внешнем lab.
Это snapshot, не установленный пакет100, не полный PAM login и не физический
диск. Рендер Mesa в VGA VM имеет driver warnings; mapped window не доказывает
полную визуальную приёмку. Начальная ошибка расширения покрыта unit injection.
Прошли 31 recovery,6 startup,2 session restart tests;3 watcher ранее в этом
наборе правок. Недоступный runtime и восстановление всей системы остаются gate.

Итоговая evidence с SHA: recovery-storage-final-source100.json. После неё
изменён только поясняющий текст safe QML (расширения отключены именно в safe
mode, без обещания записи preferences на недоступный диск). Настоящая отдельная
QML/helper/guard integration прошла: checkpoint→preview→возврат исходных файлов.

Candidate100 установлен только в исходную CachyOS VM (98→100) под настоящим
lock: runner/UI/app/bindings/lock/configerrors сохранены. Новый installed-only
тест подтвердил runner hash и прошёл обе реальные tmpfs faults с IPC on/resume.
Evidence upgrade100.json и recovery-storage-installed100.json. Главный UI
продолжает старый код до штатного unlock/transition; fresh VM ещё99, хост78.

Source stacking исправляет положение обычных floats при уменьшении/переносе
logical output. Real integration падает на старом Lua и проходит на новом;
намеренно offscreen окна сохраняются, fullscreen/maximized late reservations
с четырёх сторон и output position200x100 проверены. Нет polling. Actual Nexus
с min-size constraints, snapped reflow и multi-monitor removal ещё не закрыты.
Source fix пока не установлен; пакет100 остаётся предыдущим кандидатом.

Source: actual SettingsWindow теперь учитывает layer reservations в minimum/
maximum size; native hics_workarea обновляет QML model после late panel commits.
Одноразовая коррекция resize ждёт конца транзакции и допустимого client size,
не вмешивается в drag/fullscreen/lock/offscreen. Компактный заголовок оставляет
scroll viewport; tall SelectRow раскрывает в поиске реальный control. Новая real
integration7 checks проходит, native100 counterfactual падает на late reservation.
Также прошли16 workarea checks,5 drag rounds и settings design integration.
Снимок settings-workarea-compact.png проверен. Ещё не упаковано/не установлено;
ASan/VM/multi-monitor/прочие hardware/functionality gates остаются открыты.

Candidate101 установлен в исходную CachyOS100→101 под lock; процесс-владелец
блокировки, app и bindings сохранены. После штатного PAM unlock installed-only
nested integration прошла7checks с реальными packaged QML/native modules и
проверкой .so mapping. Fixture теперь подключает production GSFLoader: отсутствие
его было видно на первом guest screenshot, исправленный capture проверен.
Evidence settings-workarea-installed101-fonts.json/png. Это не проверка полного
нового входа main session101; хост78/fresh guest99 не изменялись.

Main101 прошёл новый boot: inode/hash загруженного bars совпадает с installed,
первый кадр/normal state/207bindings подтверждены, рестартов и failed units нет.
Два прогона по120 быстрых open/close cycles прошли без падения/JS binding errors;
FD/thread counts стабильны. Это lifecycle с dwell0.3s, не приёмка всех actions.
Выявлен высокий расход RAM: RSS достигает примерно1.42/1.65GiB
(точные значения1490692/1731708KiB). Два диагностических malloc_trim освободили
примерно800MiB, UI сохранился; это не доказательство отсутствия live leak.
Никакая периодическая очистка/allocator policy не внедрена. Требуется A/B
allocation-policy и профилирование; portal registration/textinput warnings
также остаются открыты. Evidence cold-session101, settings-soak-*, malloc-trim-*.


Обновление102: объекты шрифтов и анимаций Tokens создаются только при первом
использовании. Geometry-only элементы их больше не выделяют. Сохраняются
screen-specific настройки, реакция на scale и QObject lifetime; реальный QML
тест падает до исправления и проходит после. Пройдены сборка зависимых модулей,
font builder/window tokens, settings design/workarea и font raster matrix.
Повторно прошли31recovery unit и независимая QML/helper/guard integration.
Новый boot102 подтвердил загруженный inode bars/config, normal mode, ready,
207bindings и отсутствие рестартов/failed units/configerrors.

Эксперименты glibc выполнены только в ВМ и затем удалены; стандартная политика
восстановлена. arena2 снижает RSS в отдельном software-rendering прогоне, но
слегка увеличивает измеренное CPU time; это недостаточное основание вводить
параметр всем пользователям. Ни allocator override, ни periodic trim не добавлены
в продукт. Детальные результаты и границы сравнения — в журнале кампании.

Текущий повтор configuration integration также прошёл: автоматический checkpoint,
preview и SIGKILL guard с восстановлением durable journal, подтверждение,
возврат по таймеру, slow/trickling IPC, quarantine malformed JSON, завершение
shell-child и реальные per-device/window Lua rules. Прошли3watcher unit tests.
Это приватные профили/nested compositor, рабочие настройки хоста не менялись.

Полный120-cycle lifecycle102 прошёл без падений/JS binding errors; allocator
по умолчанию. CPU процесса81.88s против86.17s в предыдущем default101,
open-map median326ms против386ms. Это один software-VM прогон, не общий
benchmark и не controls-ready latency. Конечный RSS1430552 против1433172KiB:
заметного выигрыша по удерживаемой памяти нет; эта проблема остаётся открытой.
Evidence settings-soak-lazy-tokens102.json/lazy-tokens-comparison102.json.


PORTAL-REGISTRY-001 воспроизведён без HICS на поставляемом Qt6.12: при активации
портала два Register от одного sender, первый успешен; при заранее работающем
портале — один. Новый диагностический тест возвращает2 при повторе, не маскирует
известную ошибку зелёным тестом. Исправление зависимости и проверка reconnect
ещё открыты; портал не отключался, изменение identity Quickshell не внедрялось.


Dashboard GIF заменён реальной записью установленного102: календарь и вкладка
производительности.188кадров/9.4s, полное decode и визуальная проверка; SHA и
ограничения в docs/media/dashboard.recording.json. Это не закрывает остальные
исторические GIF/видео. Неполное завершение recording wrapper и отображение
отсутствующего датчика как0°C добавлены как открытые находки.


CPU-SENSOR-001 исправлен в исходниках: отдельная доступность датчика, `—` в
дашборде/lock вместо ложных0°C. Реальный0не теряется. Backend transition test,
services build и реальная QML HeroCard integration прошли. Нет новых таймеров
или вечной progress animation. Пока не упаковано/не установлено; GPU availability
и физические датчики этим исправлением не проверены.


Кандидат103 установлен и загружен в основной ВМ. Lock-aware upgrade сохранил
UI/runner/app/207bindings/lock, затем проверены новый boot и загруженный services
inode/SHA. CPU unavailable `—` виден на реальном дашборде. GPU availability также
исправлена; real backend/helper/HeroCard fixture43→0→missing→37прошла,5helper
тестов и повтор CPU UI прошли. Физические GPU/датчики не проверены. Сетевой
placeholder после двух2000ms отсчётов исчезает, график обновляется — наблюдение
не подтвердилось как зависание. Исторические записи о неустановленном source
CPU fix относятся к предыдущему состоянию, не к установленному103.


Кандидат104: устранён ASan-подтверждённый use-after-free GPU sampler при удалении
из callback. Ответы ограничены4096bytes, привязаны к ID, строго валидируются;
поздние/лишние/повреждённые кадры не обновляют новый запрос. Исправлен shutdown
owner QProcess. Итоговый общий прогон9protocol tests с ASan/LSan и настоящим30s
backoff/recovery прошёл; также7native helper tests и4policy/controller tests; реальные QML
GPU/quality fixtures тоже прошли. Это не доказательство отсутствия всех утечек.
Пакет установлен под lock с сохранениемUI/app/binds; installed helper/legacy/tagged
сценарий и новый boot104проверены, services inode/SHA совпадает с пакетом,
normal/ready,207bindings,0restarts/failed units/configerrors. Рабочий хост78и
fresh guest99не менялись. Детали и границы — в журнале GPU-IPC-001..003.


Кандидат105: устранён ASan-подтверждённый use-after-free в обработчике ответов
GameMode/power helper. Ответы и данные retiring process ограничены, acquisition
имеет4s deadline, старый helper отключается от нового состояния и получает EOF
для освобождения leases. Уведомления RuntimePerformance объединяются после
целостного обновления; синхронный gameChanged сохраняет guards lifetime.
8ASan/LSan protocol tests,5native/helper/controller lease tests (включая удаление
controller до late HoldProfile и явный ReleaseProfile(cookie0)),4policy tests и
реальная adaptive/thermal QML integration прошли. Это не физический power/GPU test.
Под lock установлен105с сохранениемUI/app/207bindings/lock; новый boot подтвердил
services inode/SHA пакета, normal/ready,0restarts/failed units/configerrors.
Рабочий хост78и fresh guest99не менялись. Остальные IPC readers/prefetch, Qt portal,
retained RAM и прочие gates остаются открыты. Общий unit прогон после серии описан ниже.


## Общий unit-прогон105

Чистый commit b94a733:72модуля,433теста, ни ошибок, ни тайм-аутов,6контекстных
пропусков. Manifest unit-context105/manifest.json во внешнем lab. Отдельно прошли
scopes2/2, broker8/8(включая user-systemd watchdog) и current-source network QML2/2.
Долгий GPU backoff подтверждён прежним ASan-прогоном; соответствующий source/test
между c7cf028и b94a733не менялся (diff проверен). Шесть пропусков основного прогона
не изображаются его выполненными тестами. Сетевой fixture дополнительно исправлен
для запуска именно copied current modules без activation/host service side effects.
Это широкая unit-регрессия, не приёмка всех функций DE или завершение кампании.

## Продолжение: IPC композитора и повторная проверка восстановления

В текущих исходниках укреплён `HyprExtras`: ограничены входные кадры событий
и ответы запросов; повреждённая строка отбрасывается до следующего перевода
строки, без публикации её содержимого в журнал. После разрыва event socket
восстанавливается с ограниченной экспоненциальной задержкой и обновляет
снимок настроек/устройств. В подключённом состоянии нового polling нет.

Завершение запроса безопасно при синхронном удалении владельца из callback:
сокет получает владельца приложения и удаляется после возврата в event loop.
ASan/LSan воспроизвёл ошибку на прежнем исходнике; исправленные исходники
прошли 6 протокольных тестов без подавления sanitizer-ошибок. Это проверка
изолированного настоящего C++ IPC, не естественное воспроизведение случайного
падения рабочего сеанса.

Повторно пройдены: recovery 31/31, configuration watcher 3/3, настоящий
recovery QML с helper/guard во вложенном Hyprland и проверкой отката реальных
тестовых файлов. Проверены оба формата описаний параметров Hyprland и возврат
типизированных Lua-настроек. Последний стенд теперь использует снимок текущих
библиотек, отдельные HOME/XDG и недоступные системную/пользовательскую шины.
Сборка модулей проекта прошла. Эти изменения ещё не установлены на рабочий
хост и не являются завершением общей кампании.

Приёмка IPC106 в ВМ: locked upgrade сохранил UI/runner/приложение и 207
bindings. После нормальной разблокировки и reboot проверены новые loaded
services по SHA/inode, ready=true, NRestarts=0 и отсутствие failed units.
Повторены настоящий ENOSPC2MiB и EROFS с установленным recovery UI:
startup/on/resume оставляют безопасный интерфейс; основной сеанс и отдельное
приложение сохраняются. Подробности и границы — в журнале кампании.

Кандидат107: исправлен подтверждённый ASan use-after-free модели клавиатур
при удалении владельца из синхронного обработчика изменения. Повторные
обновления сериализованы с объединением pending snapshot; обычный путь
синхронный, постоянных таймеров нет. 5 тестов/7 сценариев ASan/LSan и 6 IPC
тестов прошли; оба QML формата параметров и сборка успешны. Установка под
lock сохранила процессы; после PAM unlock пройдены три recovery/resume цикла
с сохранением приложения. Новый boot107 подтверждён по loaded inode/SHA,
health=true, NRestarts=0, 207bindings и отсутствию failed units/configerrors.
Хост остаётся78. Порталы Qt, retained RAM, fresh install итогового кандидата,
полный визуальный/аппаратный аудит и остальные перечисленные gates открыты.

Кандидат108: устранены три подтверждённых sanitizer сценария падения
DesktopIntegration при удалении из changed/operationSucceeded/microphoneChanged.
Уведомления состояния объединены через event loop, активные helper-процессы
убираются асинхронно; новых постоянных таймеров нет. 28 native тестов с
ASan/UBSan/LSan и полный current-source QML fixture прошли. Последний выявил
и помог исправить выход animated notification viewport за доступную область;
проверка теперь покадровая. Multimedia HW probing отдельно выявил driver/DBus
allocations при завершении: этот аппаратный leak gate открыт, для lifecycle
fixture аппаратные codec backends отключены, production настройки не менялись.
Установка108 под lock сохранила UI/runner/app/207bindings; новый boot проверен
по loaded SHA/inode, ready=true, NRestarts=0 и отсутствию failed units/configerrors.
Известные Qt portal registration/text-input warnings остаются открытыми.
