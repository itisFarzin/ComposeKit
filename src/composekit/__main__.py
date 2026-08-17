#!/usr/bin/env python3

import argparse

from composekit import generate, sort, update


def _add_common(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "-C",
        "--containers",
        help="Folder containing container definitions.",
    )
    _ = parser.add_argument(
        "-c",
        "--config",
        action="append",
        help="Config file(s) to load (repeatable).",
    )
    _ = parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit the resulting changes to the git repository.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="composekit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser(
        "generate", help="Create Docker Compose files."
    )
    _add_common(gen)
    _ = gen.add_argument(
        "-o", "--composes", help="Folder to write per-service composes into."
    )
    _ = gen.add_argument(
        "--output", help="Path of the aggregated main compose file."
    )
    gen.set_defaults(func=generate.main)

    upd = subparsers.add_parser("update", help="Update Docker images.")
    _add_common(upd)
    upd.set_defaults(func=update.main)

    srt = subparsers.add_parser(
        "sort", help="Sort keys in Docker Compose files."
    )
    _add_common(srt)
    srt.set_defaults(func=sort.main)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
