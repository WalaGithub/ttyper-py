"""Entry point: ``python -m ttyper`` / the ``ttyper`` console script."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from .cli import parse_args

    opt, completions_shell = parse_args(argv)

    if completions_shell is not None:
        print(
            f"Shell completions for {completions_shell!r} are not implemented "
            "in the Python port.",
            file=sys.stderr,
        )
        return 0

    if opt.list_languages:
        for name in opt.languages():
            print(name)
        return 0

    contents = opt.gen_contents()
    if contents is None:
        print(
            "Couldn't get test contents. Make sure the specified language "
            "actually exists.",
            file=sys.stderr,
        )
        return 1
    if not contents:
        print(
            "Error: the provided file or language contains no words to type.\n"
            "If you specified a file, make sure it isn't empty.",
            file=sys.stderr,
        )
        return 1

    config = opt.load_config()
    if opt.debug:
        print(opt, file=sys.stderr)
        print(config, file=sys.stderr)

    from .app import TyperApp

    TyperApp(opt, config, contents).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
