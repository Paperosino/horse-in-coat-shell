# Встроенные цветовые схемы

В `presets.json` находятся 18 парных тёмных и светлых тем: Catppuccin, Gruvbox,
Kanagawa, Everforest, Rosé Pine, Tokyo Night, Dracula, Nord, Solarized, One,
GitHub, Ayu, Nightfox, Monokai, Horizon, Oxocarbon, PaperColor и Vesper.

Палитры включают исходные RGB, 16 цветов ANSI и варианты акцента.
Источники и адаптации — в [SOURCES.md](SOURCES.md).

Выбор темы и акцента: **Обои и оформление → Цвета** или CLI:

```sh
hics scheme list -n
hics scheme list -a
hics scheme set -n hics-kanagawa -a blue -m dark
```

Встроенные палитры обновляются вместе с оболочкой; свои и динамические схемы
сохраняют цвета. [Настройка тем и обоев](../../../CONFIGURATION.md#темы-и-обои).
