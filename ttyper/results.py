"""Aggregate timing and accuracy statistics from a finished :class:`Test`.

Port of the original Rust `src/test/results.rs`. Timing is stored as CPS
(clicks per second) rather than WPM; the UI multiplies by a constant to display
WPM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .test import Test, TestEvent, is_missed_word_event


@dataclass
class Fraction:
    numerator: int = 0
    denominator: int = 0

    def value(self) -> float:
        return self.numerator / self.denominator

    def __str__(self) -> str:
        return f"{self.numerator}/{self.denominator}"


@dataclass
class TimingData:
    overall_cps: float = -1.0
    per_event: list[float] = field(default_factory=list)
    per_key: dict[str, float] = field(default_factory=dict)


@dataclass
class AccuracyData:
    overall: Fraction = field(default_factory=Fraction)
    per_key: dict[str, Fraction] = field(default_factory=dict)


@dataclass
class Results:
    timing: TimingData
    accuracy: AccuracyData
    missed_words: list[str]

    @classmethod
    def from_test(cls, test: Test) -> "Results":
        events: list[TestEvent] = [e for w in test.words for e in w.events]
        return cls(
            timing=_calc_timing(events),
            accuracy=_calc_accuracy(events),
            missed_words=_calc_missed_words(test),
        )


def _calc_timing(events: list[TestEvent]) -> TimingData:
    timing = TimingData()
    # key -> [total_time, clicks] for averaging.
    keys: dict[str, list[float]] = {}

    for prev, cur in zip(events, events[1:]):
        dur = cur.time - prev.time
        if dur < 0:
            continue
        timing.per_event.append(dur)
        entry = keys.setdefault(cur.key, [0.0, 0])
        entry[0] += dur
        entry[1] += 1

    timing.per_key = {k: total / count for k, (total, count) in keys.items()}
    if timing.per_event:
        timing.overall_cps = len(timing.per_event) / sum(timing.per_event)
    return timing


def _calc_accuracy(events: list[TestEvent]) -> AccuracyData:
    acc = AccuracyData()
    for event in events:
        if event.correct is None:
            continue
        key = acc.per_key.setdefault(event.key, Fraction())
        acc.overall.denominator += 1
        key.denominator += 1
        if event.correct:
            acc.overall.numerator += 1
            key.numerator += 1
    return acc


def _calc_missed_words(test: Test) -> list[str]:
    return [
        word.text
        for word in test.words
        if any(is_missed_word_event(e) for e in word.events)
    ]
