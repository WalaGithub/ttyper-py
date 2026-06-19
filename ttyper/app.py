"""Textual TUI for the typing test.

The Textual equivalent of ratatui's immediate-mode rendering in the original
`src/ui.rs` / `src/main.rs`. A single :class:`View` widget renders either the
running test or the results, and the app routes every keypress into the test
state machine.
"""

from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from textual.app import App, ComposeResult
from textual import events
from textual.widgets import Static

from .cli import Options
from .config import Config
from .render import prompt_text
from .results import Results
from .test import Test

# Convert CPS (clicks per second) to WPM.
WPM_PER_CPS = 12.0
# Width of the moving-average window for the WPM chart.
WPM_SMA_WIDTH = 10

_BORDER_BOX = {
    "plain": "square",
    "rounded": "rounded",
    "double": "double",
    "thick": "heavy",
    "quadrantinside": "rounded",
    "quadrantoutside": "rounded",
}

# Braille cells pack a 2-wide x 4-tall grid of dots; this maps a
# (row-within-cell, column-within-cell) sub-pixel to its dot bit.
_BRAILLE_BASE = 0x2800
_BRAILLE_DOTS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)


def _braille_line_chart(values: list[float], width: int, height: int) -> list[str]:
    """Render ``values`` as a Braille line chart resampled to ``width`` cells.

    Returns ``height`` rows (top first). Like the original's Braille marker
    line: the data is resampled to the available width and consecutive points
    are joined vertically so the line stays continuous.
    """
    if not values or width < 1 or height < 1:
        return []

    sub_w = width * 2
    sub_h = height * 4
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    n = len(values)

    # Resample to one y (0 = bottom) per sub-pixel column.
    ys: list[int] = []
    for i in range(sub_w):
        pos = 0.0 if sub_w == 1 else i / (sub_w - 1) * (n - 1)
        low = int(pos)
        high = min(low + 1, n - 1)
        v = values[low] + (values[high] - values[low]) * (pos - low)
        ys.append(round((v - lo) / span * (sub_h - 1)))

    canvas = [[0] * width for _ in range(height)]

    def plot(sx: int, sy_from_bottom: int) -> None:
        sy = (sub_h - 1) - sy_from_bottom  # flip to top-origin
        cx, cy = sx // 2, sy // 4
        if 0 <= cx < width and 0 <= cy < height:
            canvas[cy][cx] |= _BRAILLE_DOTS[sy % 4][sx % 2]

    for i in range(sub_w):
        plot(i, ys[i])
        if i > 0:  # connect to previous point so the line is continuous
            a, b = ys[i - 1], ys[i]
            for yy in range(min(a, b), max(a, b) + 1):
                plot(i, yy)

    return ["".join(chr(_BRAILLE_BASE + cell) for cell in row) for row in canvas]


class View(Static):
    """Renders the current app state (test prompt or results)."""

    def render(self) -> RenderableType:
        app: "TyperApp" = self.app  # type: ignore[assignment]
        if isinstance(app.state, Results):
            return self._render_results(app.state, app.config)
        return self._render_test(app.state, app.config)

    def on_resize(self, event: events.Resize) -> None:
        # The chart is sized to the widget, so it must be redrawn on resize.
        self.refresh()

    # -- test ----------------------------------------------------------------
    def _render_test(self, test: Test, config: Config) -> RenderableType:
        theme = config.theme
        box = _BORDER_BOX.get(theme.border_type, "rounded")

        current = test.words[test.current_word].progress
        input_panel = Panel(
            Text(current, style=theme.prompt_current_untyped),
            title=Text("Input", style=theme.title),
            title_align="left",
            border_style=theme.input_border,
            box=_box(box),
            height=3,
        )
        prompt_panel = Panel(
            prompt_text(test.words, test.current_word, theme),
            title=Text("Prompt", style=theme.title),
            title_align="left",
            border_style=theme.prompt_border,
            box=_box(box),
        )
        return Group(input_panel, prompt_panel)

    # -- results -------------------------------------------------------------
    def _render_results(self, results: Results, config: Config) -> RenderableType:
        theme = config.theme
        box = _box(_BORDER_BOX.get(theme.border_type, "rounded"))
        acc = results.accuracy.overall.value() if results.accuracy.overall.denominator else 0.0
        cps = results.timing.overall_cps if results.timing.overall_cps > 0 else 0.0

        overview = Text(style=theme.results_overview)
        overview.append(f"Adjusted WPM: {cps * WPM_PER_CPS * acc:.1f}\n")
        overview.append(f"Accuracy: {acc * 100:.1f}%\n")
        overview.append(f"Raw WPM: {cps * WPM_PER_CPS:.1f}\n")
        overview.append(f"Correct Keypresses: {results.accuracy.overall}")
        overview_panel = Panel(
            overview, title=Text("Overview", style=theme.title), title_align="left",
            border_style=theme.results_overview_border, box=box,
        )

        worst = Text(style=theme.results_worst_keys)
        worst_keys = sorted(
            (
                (k, f)
                for k, f in results.accuracy.per_key.items()
                if len(k) == 1 and k.isprintable()
            ),
            key=lambda kv: kv[1].value(),
        )
        shown = 0
        for key, frac in worst_keys:
            pct = frac.value() * 100
            if pct == 100.0:
                continue
            worst.append(f"- {key} at {pct:.1f}% accuracy\n")
            shown += 1
            if shown == 5:
                break
        worst_panel = Panel(
            worst, title=Text("Worst Keys", style=theme.title), title_align="left",
            border_style=theme.results_worst_keys_border, box=box,
        )

        from rich.columns import Columns

        top = Columns([overview_panel, worst_panel], expand=True, equal=True)

        # WPM rolling-average chart, sized to the available width/height.
        per_event = results.timing.per_event
        chart: RenderableType = Text("")
        # Leave room for the top panels (~6), footer (1) and chart chrome (~4).
        chart_h = max(4, self.size.height - 13)
        # 5 cols for the y-axis label, 2 for the panel border.
        chart_w = max(10, self.size.width - 7)
        if len(per_event) >= WPM_SMA_WIDTH:
            wpm_sma = [
                WPM_SMA_WIDTH / sum(per_event[i : i + WPM_SMA_WIDTH]) * WPM_PER_CPS
                for i in range(len(per_event) - WPM_SMA_WIDTH + 1)
            ]
            rows = _braille_line_chart(wpm_sma, chart_w, chart_h)
            chart_body = Text(style=theme.results_chart)
            ymax, ymin = max(wpm_sma), min(wpm_sma)
            for i, row in enumerate(rows):
                if i == 0:
                    prefix = f"{ymax:>4.0f} "
                elif i == len(rows) - 1:
                    prefix = f"{ymin:>4.0f} "
                else:
                    prefix = "     "
                chart_body.append(prefix, style=theme.results_chart_y)
                chart_body.append(row + "\n")
            chart_body.append(
                "     WPM (10-keypress rolling average)", style=theme.results_chart_x
            )
            chart = Panel(
                chart_body, title=Text("Chart", style=theme.title), title_align="left",
                border_style=theme.results_chart, box=box,
            )

        msg = (
            "Press 'q' to quit or 'r' for another test"
            if not results.missed_words
            else "Press 'q' to quit, 'r' for another test or 'p' to practice missed words"
        )
        footer = Align.left(Text(msg, style=theme.results_restart_prompt))
        return Group(top, chart, footer)


def _box(name: str):
    from rich import box as rich_box

    return {
        "square": rich_box.SQUARE,
        "rounded": rich_box.ROUNDED,
        "double": rich_box.DOUBLE,
        "heavy": rich_box.HEAVY,
    }.get(name, rich_box.ROUNDED)


class TyperApp(App):
    CSS = "View { padding: 1 2; }"

    def __init__(self, opt: Options, config: Config, contents: list[str]) -> None:
        super().__init__()
        self.opt = opt
        self.config = config
        self.state: Test | Results = self._new_test(contents)

    def _new_test(self, contents: list[str]) -> Test:
        return Test(
            contents,
            backtracking_enabled=not self.opt.no_backtrack,
            sudden_death_enabled=self.opt.sudden_death,
            backspace_enabled=not self.opt.no_backspace,
        )

    def compose(self) -> ComposeResult:
        yield View()

    def _refresh(self) -> None:
        self.query_one(View).refresh()

    def on_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()

        if event.key == "ctrl+c":
            self.exit()
            return

        if isinstance(self.state, Test):
            self._handle_test_key(event)
        else:
            self._handle_results_key(event)
        self._refresh()

    def _handle_test_key(self, event: events.Key) -> None:
        test: Test = self.state  # type: ignore[assignment]
        if event.key == "escape":
            self.state = Results.from_test(test)
            return

        if event.key in ("ctrl+w", "ctrl+h"):
            test.handle_key(event.key.split("+")[1], ctrl=True)
        elif event.key == "space":
            test.handle_key("space")
        elif event.key == "enter":
            test.handle_key("enter")
        elif event.key == "backspace":
            test.handle_key("backspace")
        elif event.character and len(event.character) == 1 and event.character.isprintable():
            test.handle_key(event.character)

        if test.complete:
            self.state = Results.from_test(test)

    def _handle_results_key(self, event: events.Key) -> None:
        results: Results = self.state  # type: ignore[assignment]
        if event.key in ("q", "escape"):
            self.exit()
        elif event.key == "r":
            new_contents = self.opt.gen_contents()
            if new_contents:
                self.state = self._new_test(new_contents)
        elif event.key == "p" and results.missed_words:
            import random

            practice = [w for w in results.missed_words for _ in range(5)]
            random.shuffle(practice)
            self.state = self._new_test(practice)
