#!/usr/bin/env python3

import argparse
import asyncio
import logging
import re
import sys
from operator import itemgetter
from pathlib import Path
from typing import ClassVar

try:
    import httpx
    import yaml
    from git import Repo
    from packaging.version import InvalidVersion, Version

    from composekit.container import Container, load_containers
    from composekit.utils import Config as _Config
    from composekit.utils import iter_container_files, list_tags, open_repo
except ImportError as err:
    raise RuntimeError(
        "ERROR: Missing required packages. See the README."
    ) from err

logging.basicConfig(
    stream=sys.stdout, format="%(levelname)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)


class Config(_Config):
    config_paths = ("config/update.yaml", "config/update.private.yaml")
    default_values: ClassVar[dict[str, object]] = {
        "containers_folder": "containers",
        "default_registry": "docker.io",
        "limit": 40,
        "timeout": 10,
    }


def extract_version(version: str, pattern: str | None) -> str | None:
    if pattern is None:
        return version

    match = re.search(pattern, version)
    if match is not None and len(match.groups()) > 0:
        return match.group(1)

    return None


def parse_image(image: str) -> tuple[str | None, str | None, str, str] | None:
    registry = None
    user = None
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
    if version is None:
        return None

    try:
        parsed_version = Version(version)
        if not parsed_version.is_prerelease:
            return parsed_version
    except InvalidVersion:
        pass

    return None


def get_update_options(
    config: Config, full_image: str, user: str | None, image: str
) -> dict[str, object]:
    for item in (full_image, f"{user}/{image}", image):
        config_data = config[item]
        if isinstance(config_data, dict):
            return {
                key: value
                for key, value in config_data.items()
                if isinstance(key, str)
            }

    return {}


async def find_versions(
    config: Config,
    options: dict[str, object],
    client: httpx.AsyncClient,
    registry: str | None,
    user: str | None,
    image: str,
) -> list[str]:
    limit_config = options.get("limit", config["limit"])
    limit = (
        limit_config
        if isinstance(limit_config, int)
        else int(limit_config)
        if isinstance(limit_config, str) and limit_config.isdigit()
        else 10
    )
    full_image = "/".join(filter(None, [registry, user, image]))

    try:
        user = "library" if user is None else user
        username = options.get("username")
        password = options.get("password")
        tags = await list_tags(
            client,
            registry,
            f"{user}/{image}",
            username if isinstance(username, str) else None,
            password if isinstance(password, str) else None,
        )
        if len(tags) == 0:
            raise Exception("No tags found.")

        return tags[-limit:]
    except Exception as e:
        logging.error(f"{full_image}: {e}")

    return []


async def update(
    config: Config,
    container: Container,
    client: httpx.AsyncClient,
) -> tuple[str, str, str] | None:
    result = parse_image(container.image)
    if result is None:
        return None

    registry, user, image, version = result
    full_image = "/".join(filter(None, [registry, user, image]))
    if registry in (None, ""):
        registry = str(config["default_registry"])

    options = get_update_options(config, full_image, user, image)

    if options.get("update") is False:
        logging.info(f"{full_image}: Update is disabled.")
        return None

    version_regex_config = options.get("version_regex")
    version_regex = (
        version_regex_config if isinstance(version_regex_config, str) else None
    )

    if not isinstance(
        current_version := parse_version(
            extract_version(version, version_regex)
        ),
        Version,
    ):
        logging.error(
            f"{full_image}: Could not parse the version '{version}'."
        )
        return None

    raw_versions = await find_versions(
        config, options, client, registry, user, image
    )

    versions: list[tuple[Version, str]] = [
        (v, version)
        for version in raw_versions
        if isinstance(
            v := parse_version(extract_version(version, version_regex)),
            Version,
        )
        and v > current_version
    ]

    newest_version = max(versions, key=itemgetter(0), default=(None, None))[1]
    if newest_version is None:
        return None

    return full_image, image, newest_version


async def process_file(
    path: Path,
    client: httpx.AsyncClient,
    config: Config,
    repo: Repo | None,
    git_lock: asyncio.Lock,
) -> None:
    with open(path) as file:
        containers = load_containers(yaml.safe_load_all(file))

    for container in containers:
        result = await update(config, container, client)
        if result is None:
            continue

        full_image, image, newest_version = result
        container.image = f"{full_image}:{newest_version}"

        async with git_lock:
            with open(path, "w") as file:
                yaml.dump_all(
                    [item.to_dict() for item in containers],
                    file,
                    sort_keys=False,
                )

            if repo is not None:
                _ = repo.index.add(path)
                _ = repo.index.commit(
                    f"chore({path.stem}): update {image} to {newest_version}"
                )

        logging.info(f"{full_image}: Updated to {newest_version}.")


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
        timeout = (
            int(_value) if (_value := str(config["timeout"])).isdigit() else 10
        )
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            await asyncio.gather(
                *(
                    process_file(path, client, config, repo, git_lock)
                    for path in iter_container_files(containers_folder)
                )
            )

    asyncio.run(process())
