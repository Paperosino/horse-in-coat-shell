# Источники встроенных палитр

Именованные цвета в `presets.json` взяты из перечисленных ниже проектов.
Семантические роли интерфейса могут корректировать контраст для читаемости,
а `palette_<name>` сохраняют исходные RGB. Цвета ANSI используют терминальную
палитру проекта, если она есть, либо его именованные оттенки. Изменение акцента
не меняет ANSI. Светлые поверхности Monokai и Vesper адаптированы Hyprstack:
исходные проекты предоставляют только тёмные темы.

| Схема | Источник |
| --- | --- |
| Catppuccin Mocha / Latte | [Палитра Catppuccin](https://github.com/catppuccin/palette/blob/main/palette.json) |
| Gruvbox Medium | [Именованные цвета Gruvbox](https://github.com/morhetz/gruvbox/blob/master/colors/gruvbox.vim) |
| Kanagawa Wave / Lotus | [Палитра Kanagawa](https://github.com/rebelot/kanagawa.nvim/blob/master/lua/kanagawa/colors.lua) и [Терминальные цвета](https://github.com/rebelot/kanagawa.nvim/blob/master/lua/kanagawa/themes.lua) |
| Everforest Medium | [Палитры Everforest](https://github.com/sainnhe/everforest/blob/master/autoload/everforest.vim) |
| Rosé Pine / Dawn | [Палитра Rosé Pine](https://github.com/rose-pine/neovim/blob/main/lua/rose-pine/palette.lua) |
| Tokyo Night / Day | [Палитра Night](https://github.com/folke/tokyonight.nvim/blob/main/extras/lua/tokyonight_night.lua) и [Палитра Day](https://github.com/folke/tokyonight.nvim/blob/main/extras/lua/tokyonight_day.lua) |
| Dracula / Alucard | [Открытые палитры Dracula](https://github.com/dracula/dracula-theme#color-palette-oss) |
| Nord | [16 цветов Nord](https://github.com/nordtheme/nord/blob/develop/src/nord.scss) |
| Solarized | [Палитра Solarized и цвета ANSI](https://github.com/altercation/solarized#the-values) |
| Atom One Dark / Light | [One Dark](https://github.com/atom/one-dark-syntax/blob/master/styles/colors.less) и [One Light](https://github.com/atom/one-light-syntax/blob/master/styles/colors.less) |
| GitHub Dark / Light | [Тема GitHub](https://github.com/primer/github-vscode-theme/blob/main/src/colors.js), с использованием закреплённой `@primer/primitives` 7.10.0 шкал палитры и цветов ANSI |
| Ayu Dark / Light | [Определения палитры Ayu](https://github.com/ayu-theme/ayu-colors/tree/master/themes), готовые цвета из опубликованного проектом `ayu` 9.1.0 пакета |
| Nightfox / Dayfox | [Палитра Nightfox](https://github.com/EdenEast/nightfox.nvim/blob/main/lua/nightfox/palette/nightfox.lua), [Палитра Dayfox](https://github.com/EdenEast/nightfox.nvim/blob/main/lua/nightfox/palette/dayfox.lua) и функция расчёта оттенков проекта |
| Monokai | [Тема Monokai для VS Code](https://github.com/microsoft/vscode/blob/main/extensions/theme-monokai/themes/monokai-color-theme.json) |
| Horizon / Horizon Bright | [Исходные цвета Horizon](https://github.com/jolaleye/horizon-theme-vscode/blob/master/src/dark/globals.json) и [Horizon Bright](https://github.com/jolaleye/horizon-theme-vscode/blob/master/themes/horizon-bright.json) |
| Oxocarbon Dark / Light | [Палитра Oxocarbon](https://github.com/nyoom-engineering/oxocarbon.nvim/blob/main/lua/oxocarbon/init.lua), с использованием нейтральных оттенков HSLuv |
| PaperColor Dark / Light | [Палитра PaperColor](https://github.com/NLKNguyen/papercolor-theme/blob/master/colors/PaperColor.vim) |
| Vesper | [Тема Vesper](https://github.com/raunofreiberg/vesper/blob/main/themes/Vesper-dark-color-theme.json) |
