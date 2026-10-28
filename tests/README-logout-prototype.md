# Session logout tests

The hics logout controller queries the XDG Inhibit portal and asks mapped
Wayland/XWayland windows to close before requesting logind termination. Its
non-modal blocker window allows cancellation or explicit forced termination.
It never forces termination on a timer. A portal forwarding probe prevents a
missing or differently selected backend from being mistaken for no blockers.
Loss of either portal process stops ordinary logout.

The implementation covers XDG portal logout inhibitors and mapped windows.
It does not implement the GNOME or KDE session-manager protocols or XSMP;
background applications using only those protocols may not be detected.
Power-off and reboot still use their existing logind paths, independently of
this logout coordination. These are limitations, not equivalent KDE/GNOME
session-manager compatibility.

Run the private-bus tests with:

```
python3 -m unittest discover -s tests -p 'test_logout_*.py' -v
```

`integration_logout_inhibitors.py --output NEW_DIRECTORY` exercises the real
XDG frontend and GTK4 against private portal backends in nested Hyprland.
`integration_logout_flow.py --action save --with-inhibitor --output NEW_DIRECTORY`
exercises the real controller and compositor window dispatch with an unsaved
Qt editor and fake logind. Use `--action cancel` or `--action force`, optionally
`--pointer`, for the other actions. Additional switches simulate wrong portal
selection or portal process loss. These tests do not terminate a real session.
The test disables the parent-provided pointer in the nested compositor only;
its virtual pointer cannot affect the host session.
