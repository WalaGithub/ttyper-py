"""Command-line parsing and test-content generation.

Port of the resource/option handling in the original Rust `src/main.rs`.
Languages are resolved in priority order: an explicit ``--language-file``, then
a file under the user config language dir, then a bundled resource.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from itertools import cycle, islice
from pathlib import Path

from .config import Config

RESOURCES_DIR = Path(__file__).parent / "resources"
LANGUAGE_RESOURCES = RESOURCES_DIR / "language"


@dataclass
class Options:
    contents: Path | None = None
    debug: bool = False
    words: int = 50
    config: Path | None = None
    language_file: Path | None = None
    language: str | None = None
    list_languages: bool = False
    no_backtrack: bool = False
    sudden_death: bool = False
    no_backspace: bool = False

    # -- directories ---------------------------------------------------------
    def config_dir(self) -> Path:
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        elif sys.platform.startswith("win"):
            base = Path(os.environ.get("APPDATA", Path.home()))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "ttyper"

    def language_dir(self) -> Path:
        return self.config_dir() / "language"

    def config_path(self) -> Path:
        return self.config if self.config else self.config_dir() / "config.toml"

    def load_config(self) -> Config:
        return Config.load(self.config_path())

    # -- languages -----------------------------------------------------------
    def languages(self) -> list[str]:
        builtin = sorted(p.name for p in LANGUAGE_RESOURCES.iterdir() if p.is_file())
        configured: list[str] = []
        lang_dir = self.language_dir()
        if lang_dir.is_dir():
            configured = sorted(p.name for p in lang_dir.iterdir() if p.is_file())
        return builtin + configured

    def _read_language(self) -> bytes | None:
        lang_name = self.language or self.load_config().default_language
        if self.language_file and self.language_file.is_file():
            return self.language_file.read_bytes()
        configured = self.language_dir() / lang_name
        if configured.is_file():
            return configured.read_bytes()
        builtin = LANGUAGE_RESOURCES / lang_name
        if builtin.is_file():
            return builtin.read_bytes()
        return None

    # -- content generation --------------------------------------------------
    def gen_contents(self) -> list[str] | None:
        if self.contents is not None:
            if str(self.contents) == "-":
                return [line.rstrip("\n") for line in sys.stdin]
            return self.contents.read_text(encoding="utf-8").splitlines()

        data = self._read_language()
        if data is None:
            return None

        language = data.decode("utf-8").splitlines()
        random.shuffle(language)
        contents = list(islice(cycle(language), self.words)) if language else []
        random.shuffle(contents)
        return contents


def parse_args(argv: list[str] | None = None) -> tuple[Options, str | None]:
    """Parse argv into :class:`Options`.

    Returns ``(options, completions_shell)``; ``completions_shell`` is set when
    the ``completions`` subcommand was used.
    """
    parser = argparse.ArgumentParser(
        prog="ttyper", description="Terminal-based typing test."
    )
    parser.add_argument("contents", nargs="?", type=Path, metavar="PATH",
                        help='Read test contents from the specified file, or "-" for stdin')
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-w", "--words", type=int, default=50, metavar="N",
                        help="Specify word count")
    parser.add_argument("-c", "--config", type=Path, metavar="PATH",
                        help="Use config file")
    parser.add_argument("--language-file", type=Path, metavar="PATH",
                        help="Specify test language in file")
    parser.add_argument("-l", "--language", metavar="LANG",
                        help="Specify test language")
    parser.add_argument("--list-languages", action="store_true",
                        help="List installed languages")
    parser.add_argument("--no-backtrack", action="store_true",
                        help="Disable backtracking to completed words")
    parser.add_argument("--sudden-death", action="store_true",
                        help="Enable sudden death mode to restart on first error")
    parser.add_argument("--no-backspace", action="store_true",
                        help="Disable backspace")

    sub = parser.add_subparsers(dest="command")
    completions = sub.add_parser("completions", help="Generate shell completions")
    completions.add_argument("shell", help="Shell to generate completions for")

    ns = parser.parse_args(argv)
    if ns.words <= 0:
        parser.error("word count must be a positive integer")

    shell = ns.shell if ns.command == "completions" else None
    opt = Options(
        contents=ns.contents,
        debug=ns.debug,
        words=ns.words,
        config=ns.config,
        language_file=ns.language_file,
        language=ns.language,
        list_languages=ns.list_languages,
        no_backtrack=ns.no_backtrack,
        sudden_death=ns.sudden_death,
        no_backspace=ns.no_backspace,
    )
    return opt, shell
