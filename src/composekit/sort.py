#!/usr/bin/env python3

import argparse
import asyncio
from pathlib import Path

from .container import Container, load_containers
from .generate import Config

try:
    import yaml
    from git import Repo

    from composekit.utils import iter_container_files, open_repo
except ImportError as err:
    raise RuntimeError(
        "ERROR: Missing required packages. See the README."
    ) from err


async def process_file(
    path: Path,
    repo: Repo | None,
    git_lock: asyncio.Lock,
) -> None:
    with open(path) as file:
        containers = load_containers(yaml.safe_load_all(file))

    sorted_containers: list[dict[str, object]] = []
    changed = False

    for container in containers:
        data = container.to_dict()
        sorted_dict = {k: data[k] for k in Container.fields() if k in data}
        sorted_containers.append(sorted_dict)
        changed = changed or list(data.keys()) != list(sorted_dict.keys())

    if changed:
        async with git_lock:
            with open(path, "w") as file:
                yaml.dump_all(sorted_containers, file, sort_keys=False)

            if repo is not None:
                _ = repo.index.add(path)
                _ = repo.index.commit(f"chore({path.stem}): sort keys")


def main(args: argparse.Namespace) -> None:
    async def process() -> None:
        config = Config()
        if args.config:
            config.load(*args.config)

        if args.containers:
            config["containers_folder"] = args.containers

        repo = open_repo() if args.commit else None
        git_lock = asyncio.Lock()

        containers_folder = str(config["containers_folder"])
        paths = iter_container_files(containers_folder)

        await asyncio.gather(
            *(process_file(path, repo, git_lock) for path in paths)
        )

    asyncio.run(process())
