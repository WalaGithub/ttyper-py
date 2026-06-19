"""Configuration and theming.

Port of the original Rust `src/config.rs`. The config file is TOML; theme
entries are style strings of the form ``"fg:bg;mod1;mod2"`` where ``fg``/``bg``
are color names or 6-digit hex codes and ``mod*`` are Rich-compatible modifiers.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from rich.style import Style

_COLOR_NAMES = {
    "reset": "default",
    "black": "black",
    "white": "white",
    "red": "red",
    "green": "green",
    "yellow": "yellow",
    "blue": "blue",
    "magenta": "magenta",
    "cyan": "cyan",
    "gray": "grey70",
    "darkgray": "grey35",
    "lightred": "bright_red",
    "lightgreen": "bright_green",
    "lightyellow": "bright_yellow",
    "lightblue": "bright_blue",
    "lightmagenta": "bright_magenta",
    "lightcyan": "bright_cyan",
}

_MODIFIERS = {
    "bold": "bold",
    "crossed_out": "strike",
    "dim": "dim",
    "hidden": "conceal",
    "italic": "italic",
    "rapid_blink": "blink2",
    "slow_blink": "blink",
    "reversed": "reverse",
    "underlined": "underline",
}


def parse_color(value: str) -> str:
    value = value.lower()
    if value in _COLOR_NAMES:
        return _COLOR_NAMES[value]
    if len(value) == 6:
        int(value, 16)  # validate; raises ValueError on bad hex
        return f"#{value}"
    raise ValueError(f"invalid color: {value!r}")


def parse_style(value: str) -> Style:
    colors, _, modifiers = value.partition(";")
    fg, sep, bg = colors.partition(":")
    bg = bg if sep else "none"

    kwargs: dict[str, object] = {}
    if fg not in ("none", ""):
        kwargs["color"] = parse_color(fg)
    if bg not in ("none", ""):
        kwargs["bgcolor"] = parse_color(bg)

    for modifier in filter(None, modifiers.split(";")):
        if modifier not in _MODIFIERS:
            raise ValueError(f"invalid style modifier: {modifier!r}")
        kwargs[_MODIFIERS[modifier]] = True

    return Style(**kwargs)


@dataclass
class Theme:
    default: Style = field(default_factory=Style)
    title: Style = field(default_factory=lambda: Style(color="white", bold=True))

    # test widget
    input_border: Style = field(default_factory=lambda: Style(color="cyan"))
    prompt_border: Style = field(default_factory=lambda: Style(color="green"))
    border_type: str = "rounded"

    prompt_correct: Style = field(default_factory=lambda: Style(color="green"))
    prompt_incorrect: Style = field(default_factory=lambda: Style(color="red"))
    prompt_untyped: Style = field(default_factory=lambda: Style(color="grey70"))

    prompt_current_correct: Style = field(
        default_factory=lambda: Style(color="green", bold=True)
    )
    prompt_current_incorrect: Style = field(
        default_factory=lambda: Style(color="red", bold=True)
    )
    prompt_current_untyped: Style = field(
        default_factory=lambda: Style(color="blue", bold=True)
    )
    prompt_cursor: Style = field(default_factory=lambda: Style(underline=True))

    # results widget
    results_overview: Style = field(
        default_factory=lambda: Style(color="cyan", bold=True)
    )
    results_overview_border: Style = field(default_factory=lambda: Style(color="cyan"))
    results_worst_keys: Style = field(
        default_factory=lambda: Style(color="cyan", bold=True)
    )
    results_worst_keys_border: Style = field(
        default_factory=lambda: Style(color="cyan")
    )
    results_chart: Style = field(default_factory=lambda: Style(color="cyan"))
    results_chart_x: Style = field(default_factory=lambda: Style(color="cyan"))
    results_chart_y: Style = field(
        default_factory=lambda: Style(color="grey70", bold=True)
    )
    results_restart_prompt: Style = field(
        default_factory=lambda: Style(color="grey70", italic=True)
    )

    @classmethod
    def from_dict(cls, data: dict) -> "Theme":
        theme = cls()
        for name, raw in data.items():
            if not hasattr(theme, name):
                raise ValueError(f"unknown theme key: {name!r}")
            if name == "border_type":
                setattr(theme, name, raw)
            else:
                setattr(theme, name, parse_style(raw))
        return theme


@dataclass
class Config:
    default_language: str = "english200"
    theme: Theme = field(default_factory=Theme)

    @classmethod
    def load(cls, path: Path | None) -> "Config":
        if path is None or not path.is_file():
            return cls()
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        config = cls()
        if "default_language" in data:
            config.default_language = data["default_language"]
        if "theme" in data:
            config.theme = Theme.from_dict(data["theme"])
        return config
