"""Textual TUI for the typing test.

The running test is a single re-rendered :class:`Prompt` widget; the results
screen is a mounted widget layout (two stat panels above a resizable WPM chart).
The chart is a :class:`textual_plotext.PlotextPlot`, which redraws itself to its
allocated size on resize — equivalent to ratatui's Braille line chart in the
original `src/ui.rs`, but without the content/size feedback that plagues an
auto-sized widget.
"""

from __future__ import annotations

import random

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from textual.app import App, ComposeResult
from textual import events
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static
from textual_plotext import PlotextPlot

from .cli import Options
from .config import Config, Theme
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


def _box(name: str):
    from rich import box as rich_box

    return {
        "square": rich_box.SQUARE,
        "rounded": rich_box.ROUNDED,
        "double": rich_box.DOUBLE,
        "heavy": rich_box.HEAVY,
    }.get(name, rich_box.ROUNDED)


# -- test view --------------------------------------------------------------
class Prompt(Static):
    """The running test: input box + colored prompt. Re-rendered per keypress."""

    def render(self) -> RenderableType:
        app: "TyperApp" = self.app  # type: ignore[assignment]
        test: Test = app.state  # type: ignore[assignment]
        theme = app.config.theme
        box = _box(_BORDER_BOX.get(theme.border_type, "rounded"))

        current = test.words[test.current_word].progress
        input_panel = Panel(
            Text(current, style=theme.prompt_current_untyped),
            title=Text("Input", style=theme.title),
            title_align="left",
            border_style=theme.input_border,
            box=box,
            height=3,
        )
        prompt_panel = Panel(
            prompt_text(test.words, test.current_word, theme),
            title=Text("Prompt", style=theme.title),
            title_align="left",
            border_style=theme.prompt_border,
            box=box,
        )
        return Group(input_panel, prompt_panel)


# -- results widgets --------------------------------------------------------
def _overview_panel(results: Results, theme: Theme, box) -> Panel:
    acc = results.accuracy.overall.value() if results.accuracy.overall.denominator else 0.0
    cps = results.timing.overall_cps if results.timing.overall_cps > 0 else 0.0
    text = Text(style=theme.results_overview)
    text.append(f"Adjusted WPM: {cps * WPM_PER_CPS * acc:.1f}\n")
    text.append(f"Accuracy: {acc * 100:.1f}%\n")
    text.append(f"Raw WPM: {cps * WPM_PER_CPS:.1f}\n")
    text.append(f"Correct Keypresses: {results.accuracy.overall}")
    return Panel(
        text, title=Text("Overview", style=theme.title), title_align="left",
        border_style=theme.results_overview_border, box=box,
    )


def _worst_keys_panel(results: Results, theme: Theme, box) -> Panel:
    text = Text(style=theme.results_worst_keys)
    worst = sorted(
        ((k, f) for k, f in results.accuracy.per_key.items() if len(k) == 1 and k.isprintable()),
        key=lambda kv: kv[1].value(),
    )
    shown = 0
    for key, frac in worst:
        pct = frac.value() * 100
        if pct == 100.0:
            continue
        text.append(f"- {key} at {pct:.1f}% accuracy\n")
        shown += 1
        if shown == 5:
            break
    return Panel(
        text, title=Text("Worst Keys", style=theme.title), title_align="left",
        border_style=theme.results_worst_keys_border, box=box,
    )


def _wpm_sma(results: Results) -> list[float]:
    per_event = results.timing.per_event
    if len(per_event) < WPM_SMA_WIDTH:
        return []
    return [
        WPM_SMA_WIDTH / sum(per_event[i : i + WPM_SMA_WIDTH]) * WPM_PER_CPS
        for i in range(len(per_event) - WPM_SMA_WIDTH + 1)
    ]


class WpmChart(PlotextPlot):
    """Resizable WPM line chart. Plotext re-rasterizes to the widget size."""

    def __init__(self, wpm: list[float]) -> None:
        super().__init__()
        self._wpm = wpm
        self.border_title = "Chart"
        self.border_subtitle = "WPM — 10-keypress rolling average"

    def on_mount(self) -> None:
        super().on_mount()
        plt = self.plt
        plt.plot(
            list(range(WPM_SMA_WIDTH, WPM_SMA_WIDTH + len(self._wpm))),
            self._wpm,
            marker="braille",
            color="cyan",
        )
        plt.xlabel("Keypresses")
        plt.ylabel("WPM")


# -- app --------------------------------------------------------------------
class TyperApp(App):
    CSS = """
    Prompt { padding: 1 2; }
    #results { padding: 1 2; }
    #results-top { height: auto; }
    .stat { width: 1fr; height: auto; }
    WpmChart { height: 1fr; border: round cyan; padding: 0 1; }
    #footer { height: 1; color: grey; text-style: italic; }
    """

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
        yield Container(id="root")

    async def on_mount(self) -> None:
        await self._mount_test()

    # -- screen swapping -----------------------------------------------------
    async def _mount_test(self) -> None:
        root = self.query_one("#root", Container)
        await root.remove_children()
        await root.mount(Prompt())

    async def _mount_results(self, results: Results) -> None:
        self.state = results
        theme = self.config.theme
        box = _box(_BORDER_BOX.get(theme.border_type, "rounded"))

        top = Horizontal(
            Static(_overview_panel(results, theme, box), classes="stat"),
            Static(_worst_keys_panel(results, theme, box), classes="stat"),
            id="results-top",
        )
        children: list = [top]
        wpm = _wpm_sma(results)
        if wpm:
            children.append(WpmChart(wpm))
        msg = (
            "Press 'q' to quit or 'r' for another test"
            if not results.missed_words
            else "Press 'q' to quit, 'r' for another test or 'p' to practice missed words"
        )
        children.append(Static(Text(msg, style=theme.results_restart_prompt), id="footer"))

        root = self.query_one("#root", Container)
        await root.remove_children()
        await root.mount(Vertical(*children, id="results"))

    # -- input ---------------------------------------------------------------
    async def on_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()

        if event.key == "ctrl+c":
            self.exit()
        elif isinstance(self.state, Test):
            await self._handle_test_key(event)
        else:
            await self._handle_results_key(event)

    async def _handle_test_key(self, event: events.Key) -> None:
        test: Test = self.state  # type: ignore[assignment]
        if event.key == "escape":
            await self._mount_results(Results.from_test(test))
            return

        if event.key in ("ctrl+w", "ctrl+h"):
            test.handle_key(event.key.split("+")[1], ctrl=True)
        elif event.key in ("space", "enter", "backspace"):
            test.handle_key(event.key)
        elif event.character and len(event.character) == 1 and event.character.isprintable():
            test.handle_key(event.character)

        if test.complete:
            await self._mount_results(Results.from_test(test))
        else:
            self.query_one(Prompt).refresh()

    async def _handle_results_key(self, event: events.Key) -> None:
        results: Results = self.state  # type: ignore[assignment]
        if event.key in ("q", "escape"):
            self.exit()
        elif event.key == "r":
            new_contents = self.opt.gen_contents()
            if new_contents:
                self.state = self._new_test(new_contents)
                await self._mount_test()
        elif event.key == "p" and results.missed_words:
            practice = [w for w in results.missed_words for _ in range(5)]
            random.shuffle(practice)
            self.state = self._new_test(practice)
            await self._mount_test()
