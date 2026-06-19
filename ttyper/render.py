"""Turn test words into styled :class:`rich.text.Text` for the prompt.

Port of the span-splitting logic in the original Rust `src/ui.rs`. Each word is
broken into runs of equal status (correct / incorrect / untyped, plus the
current-word variants and the cursor) so the prompt can be colored per
character.
"""

from __future__ import annotations

from enum import Enum, auto

from rich.style import Style
from rich.text import Text

from .config import Theme
from .test import TestWord


class Status(Enum):
    CORRECT = auto()
    INCORRECT = auto()
    CURRENT_UNTYPED = auto()
    CURRENT_CORRECT = auto()
    CURRENT_INCORRECT = auto()
    CURSOR = auto()
    UNTYPED = auto()
    OVERTYPED = auto()


Part = tuple[str, Status]


def split_current_word(word: TestWord) -> list[Part]:
    parts: list[Part] = []
    cur_string = ""
    cur_status = Status.UNTYPED
    progress = list(word.progress)

    for i, tc in enumerate(word.text):
        p = progress[i] if i < len(progress) else None
        if p is None:
            status = Status.CURRENT_UNTYPED
        elif p == tc:
            status = Status.CURRENT_CORRECT
        else:
            status = Status.CURRENT_INCORRECT

        if status == cur_status:
            cur_string += tc
        else:
            if cur_string:
                parts.append((cur_string, cur_status))
                cur_string = ""
            cur_string += tc
            cur_status = status
            # The first CURRENT_UNTYPED character is the cursor.
            if status == Status.CURRENT_UNTYPED:
                parts.append((cur_string, Status.CURSOR))
                cur_string = ""

    if cur_string:
        parts.append((cur_string, cur_status))
    overtyped = "".join(progress[len(word.text):])
    if overtyped:
        parts.append((overtyped, Status.OVERTYPED))
    return parts


def split_typed_word(word: TestWord) -> list[Part]:
    parts: list[Part] = []
    cur_string = ""
    cur_status = Status.UNTYPED
    progress = list(word.progress)

    for i, tc in enumerate(word.text):
        p = progress[i] if i < len(progress) else None
        if p is None:
            status = Status.UNTYPED
        elif p == tc:
            status = Status.CORRECT
        else:
            status = Status.INCORRECT

        if status == cur_status:
            cur_string += tc
        else:
            if cur_string:
                parts.append((cur_string, cur_status))
                cur_string = ""
            cur_string += tc
            cur_status = status

    if cur_string:
        parts.append((cur_string, cur_status))
    overtyped = "".join(progress[len(word.text):])
    if overtyped:
        parts.append((overtyped, Status.OVERTYPED))
    return parts


def _style_for(status: Status, theme: Theme) -> Style:
    return {
        Status.CORRECT: theme.prompt_correct,
        Status.INCORRECT: theme.prompt_incorrect,
        Status.UNTYPED: theme.prompt_untyped,
        Status.CURRENT_UNTYPED: theme.prompt_current_untyped,
        Status.CURRENT_CORRECT: theme.prompt_current_correct,
        Status.CURRENT_INCORRECT: theme.prompt_current_incorrect,
        Status.CURSOR: theme.prompt_current_untyped + theme.prompt_cursor,
        Status.OVERTYPED: theme.prompt_incorrect,
    }[status]


def prompt_text(words: list[TestWord], current_word: int, theme: Theme) -> Text:
    """Build the full styled prompt for every word in the test."""
    text = Text()
    for i, word in enumerate(words):
        if i < current_word:
            parts = split_typed_word(word)
        elif i == current_word:
            parts = split_current_word(word)
        else:
            parts = [(word.text, Status.UNTYPED)]

        for part_text, status in parts:
            text.append(part_text, _style_for(status, theme))
        text.append(" ", theme.prompt_untyped)
    return text
