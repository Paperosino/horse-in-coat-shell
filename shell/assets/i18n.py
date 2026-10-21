"""Use the shell's language and shared gettext catalog in desktop commands."""
from functools import lru_cache
import gettext
import json
import os
from pathlib import Path


def language():
    override = os.environ.get("HYPRSTACK_LANGUAGE")
    if override is not None:
        selected = override
    else:
        config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        try:
            selected = json.loads((config / "hics/shell.json").read_text()).get("general", {}).get("language", "ru_RU")
        except (OSError, ValueError, AttributeError):
            selected = "ru_RU"
    if not selected:
        selected = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG", "en_US")
    return "ru_RU" if str(selected).lower().startswith("ru") else "en_US"


@lru_cache(maxsize=2)
def catalog(lang):
    directory = Path(__file__).resolve().parents[2] / "translations"
    return gettext.translation("hyprstack", directory, languages=[lang], fallback=True)


def _(text):
    return catalog(language()).gettext(text)


def configure_argparse():
    """Translate argparse's headings and diagnostics with the shell catalog."""
    import argparse
    argparse._ = _
