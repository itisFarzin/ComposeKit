#!/usr/bin/env python3

import os
import re
import sys
import asyncio
import logging
from typing import Any
from pathlib import Path
from composekit.utils.oci_api import list_tags

try:
    import httpx
    import yaml
    from git import Repo
    from packaging.version import InvalidVersion, Version
except ImportError:
    raise RuntimeError("ERROR: Missing required packages. See the README.")

logging.basicConfig(
    stream=sys.stdout, format="%(levelname)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)


class Config:
    config: dict[str, Any]
    config_paths = ["config/update.yaml", "config/update.private.yaml"]
    default_values: dict[str, str | int | bool] = {
        "containers_folder": "containers",
        "limit": 40,
        "timeout": 10,
    }

    def __init__(self) -> None:
        self.config = {}
        for config_path in self.config_paths:
            self._load_config(config_path)

    def _load_config(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            return

        with open(file_path, "r") as file:
            self.config.update(yaml.safe_load(file) or {})

    def __getitem__(self, key: str) -> Any:
        return (
            os.getenv(key.upper())
            or self.config.get(key.lower())
            or self.default_values.get(key)
        )


def extract_version(version: str, pattern: str | None) -> str | None:
    if not pattern:
        return version

    match = re.search(pattern, version)
    if match and match.groups():
        return match.group(1)

    return None


def parse_image(image: str) -> tuple[str | None, str, str, str] | None:
    registry = None
    user = "_"
    version_segments = image.split(":")
    version = version_segments.pop() if len(version_segments) > 1 else "latest"
    image = version_segments[0]
    image_segments = image.split("/")

    if len(image_segments) == 1:
        image = image_segments[0]
    elif len(image_segments) == 2:
        part, image = image_segments
        if "." in part:
            registry = part
        else:
            user = part
    elif len(image_segments) == 3:
        registry, user, image = image_segments
    else:
        logging.warning(f"{image}: Image is invalid.")
        return None

    return registry, user, image, version


def parse_version(version: str | None) -> Version | None:
    if not version:
        return None

    try:
        parsed_version = Version(version)
        if not parsed_version.is_prerelease:
            return parsed_version
    except InvalidVersion:
        pass

    return None


async def find_versions(
    config: Config,
    container: dict[str, Any],
    client: httpx.AsyncClient,
    registry: str | None,
    user: str | None,
    image: str,
) -> list[str]:
    limit = int(config["limit"])
    full_image = "/".join(filter(None, [registry, user, image]))

    try:
        user = "library" if user == "_" else user
        if tags := await list_tags(
            client,
            registry,
            f"{user}/{image}",
            container.get("username"),
            container.get("password"),
        ):
            return tags[-limit:]

        raise Exception("No tags found.")
    except Exception as e:
        logging.error(f"{full_image}: {e}")

    return []


async def update(
    config: Config,
    container: dict[str, Any],
    client: httpx.AsyncClient,
) -> tuple[str, str, str] | None:
    if not (result := parse_image(str(container["image"]))):
        return None

    registry, user, image, version = result
    full_image = "/".join(filter(None, [registry, user, image]))

    container = next(
        (
            _data
            for item in [
                full_image,
                f"{user}/{image}",
                image,
            ]
            if (_data := config[item]) and isinstance(_data, dict)
        ),
        {},
    )

    if container.get("update") is False:
        logging.info(f"{full_image}: Update is disabled.")
        return None

    version_regex = container.get("version_regex")

    if not (
        current_version := parse_version(
            extract_version(version, version_regex)
        )
    ):
        logging.error(
            f"{full_image}: Could not parse the version '{version}'."
        )
        return None

    if not (
        raw_versions := await find_versions(
            config, container, client, registry, user, image
        )
    ):
        return None

    versions = [
        (v, version)
        for version in raw_versions
        if (v := parse_version(extract_version(version, version_regex)))
        and v > current_version
    ]

    if not versions:
        return None

    newest_version = max(versions, key=lambda p: p[0], default=(None, None))[1]
    if not newest_version:
        return None

    return full_image, image, newest_version


async def process_file(
    path: Path,
    client: httpx.AsyncClient,
    config: Config,
    repo: Repo,
    git_lock: asyncio.Lock,
) -> None:
    with open(path, "r") as file:
        containers: list[dict[str, Any]] = list(yaml.safe_load_all(file))

    for container in containers:
        if not (result := await update(config, container, client)):
            continue

        full_image, image, newest_version = result
        container["image"] = f"{full_image}:{newest_version}"

        async with git_lock:
            with open(path, "w") as file:
                yaml.dump_all(containers, file, sort_keys=False)

            repo.index.add(path)
            repo.index.commit(
                f"refactor({path.stem}): update {image} to {newest_version}"
            )

        logging.info(f"{full_image}: Updated to {newest_version}.")


async def main() -> None:
    config = Config()
    repo = Repo(".")
    # Discard any changes
    repo.index.reset(working_tree=True)
    git_lock = asyncio.Lock()

    containers_folder = str(config["containers_folder"])

    paths = (
        p
        for p in Path(containers_folder).iterdir()
        if p.is_file() and p.suffix in {".yml", ".yaml"}
    )

    async with httpx.AsyncClient(timeout=int(config["timeout"])) as client:
        await asyncio.gather(
            *(
                process_file(path, client, config, repo, git_lock)
                for path in paths
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
