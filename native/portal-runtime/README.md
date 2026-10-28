# Экспериментальный runtime портала

Это исследовательский код кампании стабильности, **не подключённый к пакету**.
Хост продолжает использовать принятую сборку 117. Патч предназначен только для
одноразовой CachyOS VM, не для установки поверх рабочего backend.

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
отдельную D-Bus шину и не меняют пользовательские/system службы. Тринадцать
сценариев покрывают lifetime, повторный вход в callbacks, 2000 таймеров,
повторное использование fd, исключения на C boundary, запрет смены потока,
очистку 100 экземпляров и настоящий отложенный D-Bus ответ.

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

Патч заменяет poll/timer threads одним sd-event loop, присоединяет D-Bus,
PipeWire и Wayland, убирает fork/sleep аварийного завершения, освобождает
закрытые ScreenCast sessions и завершённые CreateSession requests. Frame timer
держит weak session; повторный Close не планирует второй callback на raw pointer.
Toplevel subscriptions сохраняют upstream reference counting на каждую сессию.

**Границы:** selector всё ещё синхронный; отмена запроса, гибель клиента,
конкурентные операции и полный teardown ещё требуют доработки и проверки.
Перенос loop сам по себе не исправляет блокирующий `runSync`. Пока это не
основание выпускать пакет или заменять backend пользователя.

VM проверки: `tests/integration_portal_session_churn.py` использует настоящий
frontend CreateSession/Close, фиксирует PID/starttime/hash backend, считает
зарегистрированные объекты, память, fd и потоки. Она не открывает picker и не
доказывает работоспособность захвата. Последнюю отдельно проверяет
`tests/integration_screencast_frames.py` через настоящий picker и PipeWire frames.
Оба требуют явный флаг disposable VM. Churn поддерживает проверяемый root
`systemd-inhibit` ancestor, чтобы штатный сон не прерывал прогон; авторизация
не обходится. Пользовательский logind Inhibit из SSH может быть запрещён polkit.

API контракты сверены с первичными источниками:
https://www.freedesktop.org/software/systemd/man/latest/sd_event_add_io.html
https://www.freedesktop.org/software/systemd/man/latest/sd_event_add_time.html
https://kistler-group.github.io/sdbus-cpp/docs/using-sdbus-c++.html
