#!/usr/bin/env python3

import asyncio
from pathlib import Path
from typing import Any

from .generate import OPTIONS, Config

try:
    import yaml
    from git import Repo
except ImportError as err:
    raise RuntimeError(
        "ERROR: Missing required packages. See the README."
    ) from err


async def process_file(
    path: Path,
    repo: Repo,
    git_lock: asyncio.Lock,
) -> None:
    with open(path, "r") as file:
        containers: list[dict[str, Any]] = list(yaml.safe_load_all(file))

    for i, container in enumerate(containers):
        sorted_dict = {k: container[k] for k in OPTIONS if k in container}
        if list(container.keys()) == list(sorted_dict.keys()):
            continue

        containers[i] = sorted_dict
        async with git_lock:
            with open(path, "w") as file:
                yaml.dump_all(containers, file, sort_keys=False)

            repo.index.add(path)
            repo.index.commit(f"chore({path.stem}): sort keys\n\n[skip tests]")


def main() -> None:
    async def process() -> None:
        repo = Repo(".")
        # Discard any changes
        repo.index.reset(working_tree=True)
        git_lock = asyncio.Lock()

        config = Config()
        containers_folder = str(config["containers_folder"])

        paths = (
            p
            for p in Path(containers_folder).iterdir()
            if p.is_file() and p.suffix in {".yml", ".yaml"}
        )

        await asyncio.gather(
            *(process_file(path, repo, git_lock) for path in paths)
        )

    asyncio.run(process())


if __name__ == "__main__":
    main()
