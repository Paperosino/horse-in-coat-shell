# Logout coordination prototype

This is unfinished research, not an implementation of session logout. The
existing SessionManager still calls logind Terminate directly. Neither the
prototype inhibitor registry nor the dialog is connected to that path, and
no package release should claim safe logout based on these tests.

The isolated backend in `tests/fixtures/logout_inhibit_backend.py` implements
only logout inhibition. The real GTK portal installed on the test system
rejects logout inhibition with “Inhibiting other than idle not supported”.
The fixture demonstrates the XDG monitor query, replies, inhibitor lifetime,
client disconnect and cancellation, including with a GTK4 application. It is
not a replacement for the installed backend: idle, sleep and other inhibitor
flags, lock state, desktop compatibility and integration are still needed.

`LogoutBlockersWindow.qml` is an unconnected non-modal view. Its model contains
objects with `name` and `reason`; cancellation and force emit separate signals.
The view does not implement any termination. The window manager's floating
rule, actual blocker tracking, accessible keyboard/pointer behavior and live
coordinator integration must be verified before exposing it to users.

Acceptance requires exercising an actual logout with unsaved applications,
late and absent replies, multiple windows and workspaces, background clients,
locks, cancellation, a user-confirmed forced exit, and failure paths in both
an isolated nested compositor and a disposable VM. Do not force logout on a
timer. Do not stop unrelated host sessions or services during testing.

Run the non-graphical tests with:

```
python3 -m unittest discover -s tests -p 'test_logout_inhibit*.py' -v
```

Run the isolated GTK and dialog fixtures from an existing Wayland session with
`python3 tests/integration_logout_inhibitors.py --output NEW_DIRECTORY`.
These tests use a private runtime and buses; they do not test a real logout.
