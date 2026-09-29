"""Launch the tutor or run a packaged self-check."""

from __future__ import annotations

import argparse
from pathlib import Path

from study_tutor.config import configure_logging
from study_tutor.selfcheck import run_self_check


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="MBA Study Tutor")
    parser.add_argument(
        "--self-check",
        nargs="?",
        const="",
        default=None,
        metavar="RESULT_FILE",
        help="Check the local app pieces and write the result.",
    )
    args = parser.parse_args(argv)
    if args.self_check is not None:
        path = Path(args.self_check) if args.self_check else None
        raise SystemExit(run_self_check(path))
    configure_logging()
    from study_tutor.ui.app import run

    run()


if __name__ == "__main__":
    main()
