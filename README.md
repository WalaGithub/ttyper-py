# ttyper (Python port)

A terminal-based typing test — a Python/[Textual](https://textual.textualize.io/)
reimplementation of [max-niederman/ttyper](https://github.com/max-niederman/ttyper)
(originally written in Rust with ratatui).

## Install

```sh
pip install -e .
# or just run from the source tree:
python -m ttyper
```

Requires Python 3.10+. Dependencies: `textual`, `rich` (and `tomli` on < 3.11).

## Usage

```sh
ttyper                      # 50 words from the default language (english200)
ttyper -w 100               # 100 words
ttyper -l english1000       # pick a bundled language
ttyper --list-languages     # list bundled + user-installed languages
ttyper path/to/file.txt     # type the contents of a file ("-" for stdin)
```

### Options

| Flag | Description |
| --- | --- |
| `-w, --words N` | Word count (default 50) |
| `-l, --language LANG` | Test language (bundled or under the config dir) |
| `--language-file PATH` | Use a specific language file |
| `-c, --config PATH` | Use a specific config file |
| `--list-languages` | List installed languages |
| `--no-backtrack` | Disable backtracking to completed words |
| `--sudden-death` | Restart the test on the first error |
| `--no-backspace` | Disable backspace |

### Controls

- Type to advance through the prompt; `space`/`enter` commit a word.
- `Ctrl-W` / `Ctrl-Backspace` delete the current word.
- `Esc` ends the test early and shows results.
- At the results screen: `r` for a new test, `p` to drill missed words, `q` to quit.
- `Ctrl-C` exits anywhere.

## Configuration

A TOML config at `<config-dir>/ttyper/config.toml` (e.g.
`~/.config/ttyper/config.toml` on Linux, `~/Library/Application Support/ttyper/`
on macOS). Custom languages go in `<config-dir>/ttyper/language/`.

```toml
default_language = "english1000"

[theme]
# style strings are "fg:bg;modifier;modifier"
prompt_correct = "green"
prompt_incorrect = "red;bold"
input_border = "00ffff"
border_type = "rounded"
```

Colors are names (`red`, `lightblue`, …) or 6-digit hex (`00ff00`). Modifiers:
`bold`, `dim`, `italic`, `underlined`, `crossed_out`, `reversed`, `hidden`,
`slow_blink`, `rapid_blink`.

## Layout

| Module | Responsibility |
| --- | --- |
| `ttyper/test.py` | Test state machine (`Test`, `TestWord`, `TestEvent`) |
| `ttyper/results.py` | Timing & accuracy aggregation |
| `ttyper/config.py` | Config + theme / style-string parsing |
| `ttyper/render.py` | Per-character prompt styling |
| `ttyper/app.py` | Textual app and rendering |
| `ttyper/cli.py` | Argument parsing & content generation |

## Tests

```sh
python tests/test_port.py     # standalone runner
# or: pytest
```

These port the original Rust unit tests (style parsing, word splitting,
content generation) plus state-machine behavior checks.

## License

MIT, matching the original project.
