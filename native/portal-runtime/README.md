# Экспериментальный runtime портала

Это runtime backend портала, разработанный в рамках кампании стабильности.
Пакет120 собирает его из закреплённых исходников и устанавливает отдельно от
системного backend; результаты проверки и установки фиксируются в журнале
кампании. Системный пакет портала и его файлы не заменяются.

`EventLoop` использует штатный `sd-event` и поддерживает подключение sdbus-c++
через `attachSdEventLoop`. Один поток владеет источниками; callbacks могут
удалять/заменять свой источник или владельца. Дескрипторы остаются собственностью
вызывающего кода. `nativeHandle()` не делает сторонний код потокобезопасным.

Проверки:

```sh
python3 -m unittest discover -s tests -p test_portal_eventloop.py -v
HICS_TEST_SANITIZERS=1 python3 -m unittest discover -s tests -p test_portal_eventloop.py -v
cmake -S native/portal-runtime -B build/portal-loop -G Ninja
cmake --build build/portal-loop
```

Требуются C++23, libsystemd, sdbus-c++ и dbus-daemon для тестов. Тесты создают
отдельную D-Bus шину и не меняют пользовательские/system службы. Четырнадцать
сценариев покрывают lifetime, повторный вход в callbacks, 2000 таймеров,
повторное использование fd, исключения на C boundary, запрет смены потока,
очистку 100 экземпляров настоящий отложенный D-Bus ответ и lifetime удержанного sdbus::Result.

## Воспроизводимость backend-прототипа

Основа `xdg-desktop-portal-hyprland` **v1.4.1**, официальный архив:
https://codeload.github.com/hyprwm/xdg-desktop-portal-hyprland/tar.gz/refs/tags/v1.4.1
SHA256 `3652c14f63a9666acea2c841e196782dbc0f74ea5b4783622dd04a32f08b709f`.
Патч `xdph-v1.4.1-experimental.patch` применяется с `patch -p1` к чистому
исходному дереву. Upstream CMake генерирует протоколы в source tree: собирайте
копию, сохраняйте pristine отдельно.

Точные дополнительные build inputs:

- hyprland-protocols commit `bd153e76f751f150a09328dbdeb5e4fab9d23622`,
  архив codeload SHA256 `f31112800ec83ec529d0d35699a3d20fa0ed3cbb97d344146340815fec5ac055`;
  распаковать в `subprojects/hyprland-protocols`.
- hyprwayland-scanner v0.4.6, архив codeload SHA256
  `05f55fd1a20d8ca81b5030980fdb7c87147749230145bdb3745af2741d617f5c`.
  В проверке устанавливался в отдельный prefix, без замены системного scanner.

CMake требует `-DHICS_PORTAL_RUNTIME_DIR=/absolute/path/to/native/portal-runtime`,
`-DSYSTEMD_SERVICES=OFF`. Проверенная конфигурация: RelWithDebInfo,
sdbus-c++ 2.3.1, libsystemd 262, hyprutils 0.14.2, hyprlang 0.6.8.

Пакет собирает backend скриптом `build_backend.py`: он скачивает эти три
закреплённых архива, проверяет SHA256 до безопасной распаковки и применения
патча, затем отдельно собирает scanner и backend. `hic-shell` устанавливает
backend в `/usr/share/hics/portal/` и выбирает его через systemd user drop-in;
системный `xdg-desktop-portal-hyprland` и share picker остаются установленными.
Запущенный backend не перезапускается при обновлении: новый применяется при
его следующем штатном запуске. При прямой D-Bus активации без systemd остаётся
системный backend; это отдельная конфигурация, не проверенная данным пакетом.

Патч заменяет poll/timer threads одним sd-event loop, присоединяет D-Bus,
PipeWire и Wayland, убирает fork/sleep аварийного завершения, освобождает
закрытые ScreenCast sessions и завершённые CreateSession requests. Frame timer
держит weak session; повторный Close не планирует второй callback на raw pointer.
Toplevel subscriptions сохраняют upstream reference counting на каждую сессию.

`Processes` теперь обеспечивает асинхронный picker: `posix_spawnp`, argv/env без
shell, pidfd, отдельная process group, максимум8 процессов и1MiB суммарного
stdout/stderr на процесс. Завершение по deadline/отмене: TERM, затем KILL через
500мс; callback вызывается после waitpid и снятия watches. Деструктор отменяет
работу и собирает прямых детей без пользовательских callbacks. При штатном
закрытии процесса оставшиеся члены его process group завершаются; это не sandbox
и не обещание контроля произвольно демонизирующего custom picker. Финальный
waitpid не имеет гарантированного срока при uninterruptible kernel sleep.

Дополнительные13 tests (`test_portal_process.py`) покрывают FailedToStart,
stdout/stderr/exit, TERM resistance, повторную отмену, закрытый stdin, лимит вывода, descriptor
inheritance, уничтожение из callback,8 параллельных детей с отказом9-му,
потомка с открытыми pipes и100 lifetimes без ростаfd/прямых zombie детей.
Проходят также ASan/UBSan/LSan; реальный backend целиком ещё не принят sanitizer.

Async SelectSources использует штатный `sdbus::Result`, weak session и один
ожидающий выбор на сессию. Request.Close и Session.Close отменяют picker.
Время picker ограничено5минутами, лишний запрос не заменяет активный.
Парсинг результата больше не использует бросающие stoi/stoull или pop_back на
непроверенной строке. Региональный выбор и испорченные restore/picker данные ещё
требуют отдельной матрицы; их нельзя считать принятыми по window capture.

**Границы:** Start ещё содержит синхронные пути. Гибель клиента при ожидающем
picker проверена, но конкурентные операции, все типы выбора и все варианты
teardown требуют дополнительной проверки.

VM проверки: `tests/integration_portal_session_churn.py` использует настоящий
frontend CreateSession/Close, фиксирует PID/starttime/hash backend, считает
зарегистрированные объекты, память, fd и потоки. Она не открывает picker и не
доказывает работоспособность захвата. Последнюю отдельно проверяет
`tests/integration_screencast_frames.py` через настоящий picker и PipeWire frames.
`tests/integration_portal_cancel.py` ждёт фактически mapped окно picker,
проверяет доступность D-Bus до/после Close, pidfd exit и reaping, отсутствие
оставшихся request/session объектов. Проверяются оба вида Close; реальные кадры
в этом тесте не запрашиваются. Все интеграции требуют явный флаг disposable VM. Churn поддерживает проверяемый root
`systemd-inhibit` ancestor, чтобы штатный сон не прерывал прогон; авторизация
не обходится. Пользовательский logind Inhibit из SSH может быть запрещён polkit.

API контракты сверены с первичными источниками:
https://www.freedesktop.org/software/systemd/man/latest/sd_event_add_io.html
https://www.freedesktop.org/software/systemd/man/latest/sd_event_add_time.html
https://kistler-group.github.io/sdbus-cpp/docs/using-sdbus-c++.html

## Полное завершение backend под ASan

Проверка выделена в `tests/integration_portal_backend_exit.py`. Сначала применить
экспериментальный патч к копии официального source tree, затем **только к отдельной
диагностической копии** применить `tests/fixtures/portal-backend-test-exit.patch`.
Он включает ASan/UBSan на backend target и тестовый D-Bus метод Exit. Обычный
патч/пакет этого метода не содержит. Собрать только target
`xdg-desktop-portal-hyprland`; picker остаётся системным.

Только в disposable VM нужен временный service override с Type=exec, пустым
BusName, Restart=no и отдельным исполняемым файлом:

```ini
[Service]
Type=exec
BusName=
Restart=no
ExecStart=
ExecStart=/var/tmp/hics-xdph118/asan-exit-v3
Environment=ASAN_OPTIONS=detect_leaks=1:halt_on_error=1:exitcode=95
Environment=LSAN_OPTIONS=
Environment=UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1
```

Не переносить эту конфигурацию в установленную службу. Type=dbus может закончить
lifetime службы при потере bus name раньше полного exit/LSan; первый такой прогон
имел обрезанный journal и не был принят. Controller теперь проверяет Type=exec,
Restart=no, реальную executable identity, ASan в maps, включённый leak detector
и отсутствие suppressions. Состояние `exited-awaiting-sanitizer-review` означает
лишь выход процесса: обязательны полный journal с `_PID` именно этого backend
и ExecMainStatus/Result systemd. Код0 самого controller не доказывает чистый ASan.

В этом сценарии обнаружен реальный heap-use-after-free: SOutput уничтожался после
`wl_display_disconnect`. Патч теперь освобождает outputs, mapping и protocol
wrappers до отключения display. Освобождаются также временные drmDevice сведения
через drmFreeDevice; ошибка drmGetDevice2 больше не передаёт nullptr в сравнение.
После этих исправлений idle-exit не воспроизводил UAF/DRM leak, но LSan сообщал
3677 байт/34 allocations через PipeWire module loading. Дальнейшая проверка и
изменение времени жизни libdbus описаны ниже; это не приёмка всего портала.

Контракты lifetime проверены по первичным исходникам:
https://wayland.pages.freedesktop.org/wayland.freedesktop.org/docs/html/apb.html
https://cgit.freedesktop.org/drm/libdrm/tree/xf86drm.c

`integration_portal_cancel.py --close disconnect` закрывает отдельное реальное
D-Bus-соединение приложения; наблюдатель использует другую connection и проверяет
cleanup исходного namespace. Это проверка исчезновения D-Bus peer, не имитация
SIGKILL полноценного приложения.

### Выход с ожидающим picker и открытой сессией трансляции

`integration_portal_backend_exit.py --with-picker` создаёт настоящую сессию,
ждёт mapped окно picker и запрашивает тестовый Exit без выбора источника. Он
проверяет исчезновение picker, но всё равно требует отдельного изучения ASan
journal. Так обнаружен дефект нового async-прототипа: captured sdbus::Result
уничтожался после IConnection. `Processes::shutdown()` теперь явно освобождает
детей, watches и closures до teardown D-Bus. Остановка идемпотентна, новые start
после неё запрещены. Вызывать её надо до разрушения внешних зависимостей callback;
одного автоматического деструктора supervisor недостаточно.

Для второго сценария используется `integration_screencast_frames.py
--backend-exit-after-frames /path/to/instrumented-backend`. Рядом со скриптом
должен лежать `integration_portal_backend_exit.py`. После12 реальных кадров и
проверки существования stream serial он вызывает Exit **до Session.Close**.
Consumer к этому моменту уже завершён; это открытая сессия/узел после кадров,
а не одновременно работающий бесконечный consumer. Такая проверка обнаружила
use-after-free в pwStreamStateChange: SSession уничтожался раньше PW streams.
Portal destructor теперь сначала завершает PW connection/streams, пока sessions
живы. Listener снимается до disconnect/destroy, Wayland frame callbacks и buffers
освобождаются явно. Частично созданный null stream тоже удаляется из списка.
Контракт listener проверен по https://docs.pipewire.org/group__pw__stream.html
и https://pipewire.pages.freedesktop.org/pipewire/page_spa_plugins.html.

Diagnostic frame run завершается статусом `backend-exited-awaiting-sanitizer-review`,
а не `passed`. PID/startticks фиксируются до получения кадров; helper обязан
завершить именно этот producer. InvocationID фиксируется отдельно: после выхода
frontend может активировать новый backend через D-Bus даже при Restart=no.
Статус нового процесса нельзя использовать как доказательство чистоты старого.
Во время проверки исправленного случая был получен LSan3685bytes/34allocs;
обычный Close+последующий Exit дал3677/34, без прежних SEGV/UAF в этих сценариях.
Это всё ещё не полная sanitizer acceptance.

### libdbus и завершение с работающим потребителем

PipeWire module-rt использует libdbus и закрывает свои соединения при выгрузке.
libdbus, однако, содержит глобальные кэши и блокировки; при выгрузке самой
библиотеки без shutdown ссылки на них исчезают. В отдельной VM при 100 циклах
raw probe получил 410800 байт / 3400 allocations, а probe с принадлежащей
процессу libdbus и диагностическим dbus_shutdown после уничтожения всех
контекстов прошёл LSan. Последний вызов допустим только в этом изолированном
однопроцессном fixture, где известны все пользователи libdbus.

Экспериментальный backend теперь явно связывает dbus-1 и инициализирует его
до остальных компонентов: библиотека и её глобальное состояние существуют
до выхода процесса, а повторная выгрузка module-rt не теряет ссылки на них.
Это удерживает ограниченное глобальное состояние libdbus до выхода процесса;
не вызываем dbus_shutdown в backend, поскольку другие библиотеки могут её
использовать. Зелёный LSan при живой libdbus сам по себе не доказывает, что
её доступные кэши освобождены. Семантика shutdown описана в
https://dbus.freedesktop.org/doc/api/html/group__DBusMemory.html.

Новый `--consumer-active-at-exit` в тесте кадров удерживает реальный consumer
в работе при штатном диагностическом Exit backend. В CachyOS software VM
получены 12 меняющихся кадров 1280×800, consumer оставался жив до и после
выхода backend, producer serial исчез, затем consumer штатно завершён. Тот же
instrumented backend завершился с systemd status 0, полный journal без отчётов
ASan/UBSan/LSan, без suppressions; это относится к проверенному пути, а не ко
всем устройствам и операциям портала. Пакетный кандидат использует тот же патч;
диагностический метод Exit в него не включается.
