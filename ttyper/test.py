"""Core typing-test state machine.

Port of the original Rust `src/test/mod.rs`. A :class:`Test` owns a list of
:class:`TestWord`s and advances through them as keys are fed in via
:meth:`Test.handle_key`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass
class TestEvent:
    """A single keypress recorded during a test.

    ``correct`` is ``True``/``False`` for evaluated keypresses, or ``None`` for
    keypresses that don't count toward accuracy (e.g. CTRL-W word deletion).
    """

    time: float
    key: str
    correct: bool | None


def is_missed_word_event(event: TestEvent) -> bool:
    return event.correct is not True


@dataclass
class TestWord:
    text: str
    progress: str = ""
    events: list[TestEvent] = field(default_factory=list)


class Test:
    def __init__(
        self,
        words: list[str],
        backtracking_enabled: bool = True,
        sudden_death_enabled: bool = False,
        backspace_enabled: bool = True,
    ) -> None:
        self.words: list[TestWord] = [TestWord(w) for w in words]
        self.current_word: int = 0
        self.complete: bool = False
        self.backtracking_enabled = backtracking_enabled
        self.sudden_death_enabled = sudden_death_enabled
        self.backspace_enabled = backspace_enabled

    # -- key handling --------------------------------------------------------
    def handle_key(self, key: str, *, ctrl: bool = False) -> None:
        """Advance the test by one keypress.

        ``key`` is a normalized key name: a single character for printable
        input, or ``"space"``, ``"enter"``, ``"backspace"``. ``ctrl`` marks a
        CTRL modifier (used for CTRL-W / CTRL-H word deletion).
        """
        if ctrl and key in ("h", "w"):
            self._handle_ctrl_delete(key)
            return

        if key in ("space", "enter"):
            self._handle_word_break(key)
        elif key == "backspace":
            self._handle_backspace(key)
        elif len(key) == 1:
            self._handle_char(key)

    def _handle_word_break(self, key: str) -> None:
        word = self.words[self.current_word]
        # Mid-word space (target text itself contains a space at this position).
        if _char_at(word.text, len(word.progress)) == " ":
            word.progress += " "
            word.events.append(TestEvent(monotonic(), key, True))
        elif word.progress or not word.text:
            correct = word.text == word.progress
            if self.sudden_death_enabled and not correct:
                self._reset()
            else:
                word.events.append(TestEvent(monotonic(), key, correct))
                self._next_word()

    def _handle_backspace(self, key: str) -> None:
        word = self.words[self.current_word]
        if not word.progress and self.backtracking_enabled and self.backspace_enabled:
            self._last_word()
        elif self.backspace_enabled:
            word.events.append(
                TestEvent(monotonic(), key, not word.text.startswith(word.progress))
            )
            word.progress = word.progress[:-1]

    def _handle_ctrl_delete(self, key: str) -> None:
        # CTRL-Backspace and CTRL-W: delete the whole current word.
        if not self.words[self.current_word].progress:
            self._last_word()
        word = self.words[self.current_word]
        word.events.append(TestEvent(monotonic(), key, None))
        word.progress = ""

    def _handle_char(self, key: str) -> None:
        word = self.words[self.current_word]
        word.progress += key
        correct = word.text.startswith(word.progress)
        if self.sudden_death_enabled and not correct:
            self._reset()
        else:
            word.events.append(TestEvent(monotonic(), key, correct))
            if word.progress == word.text and self.current_word == len(self.words) - 1:
                self.complete = True
                self.current_word = 0

    # -- navigation ----------------------------------------------------------
    def _last_word(self) -> None:
        if self.current_word != 0:
            self.current_word -= 1

    def _next_word(self) -> None:
        if self.current_word == len(self.words) - 1:
            self.complete = True
            self.current_word = 0
        else:
            self.current_word += 1

    def _reset(self) -> None:
        for word in self.words:
            word.progress = ""
            word.events.clear()
        self.current_word = 0
        self.complete = False


def _char_at(s: str, index: int) -> str | None:
    return s[index] if 0 <= index < len(s) else None
