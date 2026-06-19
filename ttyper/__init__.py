"""ttyper — a terminal-based typing test (Python port).

Python reimplementation of max-niederman/ttyper, originally written in Rust.
"""

__all__ = ["main"]
__version__ = "1.6.0"


def main(argv: list[str] | None = None) -> int:
    from .__main__ import main as _main

    return _main(argv)
