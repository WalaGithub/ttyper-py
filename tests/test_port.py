"""Ports of the original Rust unit tests, plus a few logic checks."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.style import Style  # noqa: E402

from ttyper.cli import Options  # noqa: E402
from ttyper.config import Config, parse_color, parse_style  # noqa: E402
from ttyper.render import (  # noqa: E402
    Status,
    split_current_word,
    split_typed_word,
)
from ttyper.results import Results  # noqa: E402
from ttyper.test import Test, TestWord  # noqa: E402


# -- config.rs tests --------------------------------------------------------
def test_deserializes_basic_colors():
    assert parse_color("black") == "black"
    assert parse_color("000000") == "#000000"
    assert parse_color("ffffff") == "#ffffff"
    assert parse_color("FFFFFF") == "#ffffff"


def test_deserializes_styles():
    assert parse_style("none") == Style()
    assert parse_style("none:none") == Style()
    assert parse_style("none:none;") == Style()
    assert parse_style("black") == Style(color="black")
    assert parse_style("black:white") == Style(color="black", bgcolor="white")
    assert parse_style("none;bold") == Style(bold=True)
    assert parse_style("none;bold;italic;underlined;") == Style(
        bold=True, italic=True, underline=True
    )
    assert parse_style("00ff00:000000;bold;dim;italic;slow_blink") == Style(
        color="#00ff00", bgcolor="#000000", bold=True, dim=True, italic=True, blink=True
    )


# -- ui.rs split tests ------------------------------------------------------
def _word(text, progress):
    w = TestWord(text)
    w.progress = progress
    return w


def test_typed_words_split():
    cases = [
        ("monkeytype", "monkeytype", [("monkeytype", Status.CORRECT)]),
        ("monkeytype", "monkeXtype",
         [("monke", Status.CORRECT), ("y", Status.INCORRECT), ("type", Status.CORRECT)]),
        ("monkeytype", "monkeas",
         [("monke", Status.CORRECT), ("yt", Status.INCORRECT), ("ype", Status.UNTYPED)]),
    ]
    for text, progress, expected in cases:
        assert split_typed_word(_word(text, progress)) == expected


def test_current_word_split():
    cases = [
        ("monkeytype", "monkeytype", [("monkeytype", Status.CURRENT_CORRECT)]),
        ("monkeytype", "monke",
         [("monke", Status.CURRENT_CORRECT), ("y", Status.CURSOR), ("type", Status.CURRENT_UNTYPED)]),
        ("monkeytype", "monkeXt",
         [("monke", Status.CURRENT_CORRECT), ("y", Status.CURRENT_INCORRECT),
          ("t", Status.CURRENT_CORRECT), ("y", Status.CURSOR), ("pe", Status.CURRENT_UNTYPED)]),
    ]
    for text, progress, expected in cases:
        assert split_current_word(_word(text, progress)) == expected


# -- main.rs gen_contents tests ---------------------------------------------
def test_gen_contents_empty_file_returns_empty_vec():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "empty.txt"
        path.write_text("")
        assert Options(contents=path).gen_contents() == []


def test_gen_contents_nonempty_file_returns_words():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "words.txt"
        path.write_text("hello world rust\n")
        assert Options(contents=path).gen_contents()


# -- test state-machine behavior --------------------------------------------
def test_full_correct_run_completes_and_scores_100():
    test = Test(["ab", "cd"])
    for ch in "ab cd":
        test.handle_key("space" if ch == " " else ch)
    assert test.complete
    results = Results.from_test(test)
    assert results.accuracy.overall.value() == 1.0
    assert results.missed_words == []


def test_incorrect_word_is_missed():
    test = Test(["ab", "cd"])
    for ch in "ax cd":  # 'x' wrong in first word
        test.handle_key("space" if ch == " " else ch)
    results = Results.from_test(test)
    assert "ab" in results.missed_words


def test_sudden_death_resets_on_error():
    test = Test(["ab", "cd"], sudden_death_enabled=True)
    test.handle_key("a")
    test.handle_key("x")  # wrong -> reset
    assert test.words[0].progress == ""
    assert test.current_word == 0


def test_list_languages_includes_builtins():
    langs = Options().languages()
    assert "english200" in langs
    assert "rust" in langs


if __name__ == "__main__":
    import traceback

    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception:
                failures += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    sys.exit(1 if failures else 0)
