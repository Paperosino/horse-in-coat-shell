"""Adopt the hics directory names without discarding existing user settings."""
from pathlib import Path
import os

def migrate():
    home = Path.home()
    roots = [Path(os.environ.get(key, home / default)) for key, default in (
        ('XDG_CONFIG_HOME', '.config'), ('XDG_DATA_HOME', '.local/share'),
        ('XDG_STATE_HOME', '.local/state'), ('XDG_CACHE_HOME', '.cache'))]
    for root in roots:
        old, new = root / 'hyprstack', root / 'hics'
        if old.exists() and not new.exists() and not new.is_symlink():
            root.mkdir(parents=True, exist_ok=True)
            new.symlink_to(old.name, target_is_directory=True)
    old_install, new_install = roots[2] / 'hyprstack-install', roots[2] / 'hics-install'
    if old_install.exists() and not new_install.exists() and not new_install.is_symlink():
        new_install.symlink_to(old_install.name, target_is_directory=True)
    legacy_env = roots[0] / 'environment.d/90-hyprstack-appearance.conf'
    current_env = legacy_env.with_name('90-hics-appearance.conf')
    if legacy_env.is_file() and not current_env.exists():
        legacy_env.rename(current_env)
    # Old shell preferences name built-in schemes with the original prefix;
    # those IDs remain accepted by the theme service.
    config = roots[0] / 'hypr'
    if config.is_dir():
        for path in config.rglob('*.lua'):
            if path.is_symlink() or not path.is_file():
                continue
            text = path.read_text()
            revised = text.replace('runhics', 'hics')
            if revised != text:
                backup = path.with_suffix(path.suffix + '.before-hics')
                if not backup.exists():
                    backup.write_text(text)
                path.write_text(revised)

if __name__ == '__main__':
    migrate()
