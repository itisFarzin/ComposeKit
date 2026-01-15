#!/usr/bin/env python3

import os
import re
import sys
import logging
import asyncio
from pathlib import Path

try:
    import yaml
    import httpx
    from git import Repo
    from packaging.version import Version, InvalidVersion
except ImportError:
    print(
        "ERROR: Missing the required package(s). Install them via:"
        "\npip install -r requirements.txt"
    )
    exit(1)

logging.basicConfig(
    stream=sys.stdout, format="%(levelname)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)


class Config:
    _config: dict[str, str | int | list]
    default_values = {
        "containers_folder": "containers",
        "page_size": 40,
    }

    def __init__(self):
        self._config = {}
        self._load_config("config/update.yaml")
        self._load_config("config/update.private.yaml")

    def _load_config(self, file_path: str):
        if not os.path.exists(file_path):
            return

        with open(file_path, "r") as file:
            self._config.update(yaml.safe_load(file) or {})

    def get(self, key: str):
        return (
            os.getenv(key.upper())
            or self._config.get(key.lower())
            or self.default_values.get(key.lower())
        )


def extract_version(version: str, pattern: str | None) -> str | None:
    if not pattern:
        return version

    match = re.search(pattern, version)
    if match and match.groups():
        return match.group(1)

    return None


def parse_version(version: str | None):
    if not version:
        return None

    try:
        parsed_version = Version(version)
        if not parsed_version.is_prerelease:
            return parsed_version
    except InvalidVersion:
        return None


async def main():
    config = Config()
    repo = Repo(".")
    # Discard any changes
    repo.git.reset("--hard")
    git_lock = asyncio.Lock()

    containers_folder: str = config.get("containers_folder")
    page_size = int(config.get("page_size"))

    async def update(
        container: dict[str, str | list],
        page_size: int,
        client: httpx.AsyncClient,
    ):
        image = container["image"]
        registry = None

        if len(parts := image.split(":")) != 2:
            parts.append("latest")

        image, version = parts

        if len(parts2 := image.split("/")) == 3:
            registry, user, image = parts2
        elif len(parts2) == 2:
            _var, image = parts2
            if "." in _var:
                registry = _var
                user = "_"
            else:
                user = _var
        elif len(parts2) == 1:
            image = parts2[0]
            user = "_"
        else:
            logging.warning(f"Image {image} is invalid.")
            # Skip the invalid image formats
            return

        full_image = "/".join(filter(None, [registry, user, image]))

        container = next(
            (
                _data
                for item in [
                    full_image,
                    f"{user}/{image}",
                    image,
                ]
                if (_data := config.get(item))
            ),
            {},
        )

        if container.get("update") is False:
            logging.info(f"Update for image {full_image} is disabled.")
            return

        version_regex = container.get("version_regex")

        if not (
            current_version := parse_version(
                extract_version(version, version_regex)
            )
        ):
            logging.warning(
                "Could not parse a comparable version from '{}' for image {}."
                " Skipping.".format(version, full_image)
            )
            return

        versions = None

        if registry in ("docker.io", None):
            user = "library" if user == "_" else user
            request = await client.get(
                f"https://hub.docker.com/v2/namespaces/{user}/repositories/"
                f"{image}/tags?page_size={page_size}"
            )
            result = request.json()

            versions = [
                version["name"] for version in result.get("results", {})
            ]
        elif registry == "ghcr.io":
            request = await client.get(
                f"https://ghcr.io/token?scope=repository:{user}/{image}:pull",
                auth=(
                    (container["user"], container["pat"])
                    if container.get("user") and container.get("pat")
                    else None
                ),
            )
            result = request.json()
            if not (token := result.get("token")):
                logging.warning(
                    f'{full_image}: {result["errors"][0]["message"]}'
                )
                return

            request = await client.get(
                f"https://ghcr.io/v2/{user}/{image}/tags/list",
                headers={"Authorization": f"Bearer {token}"},
            )
            result = request.json()
            if result.get("errors"):
                logging.warning(
                    f'{full_image}: {result["errors"][0]["message"]}'
                )
                return

            versions = result["tags"]

        if not versions:
            return

        versions = [
            (v, version)
            for version in versions
            if (v := parse_version(extract_version(version, version_regex)))
            and v > current_version
        ]

        if not versions:
            return

        newest_version = max(
            versions, key=lambda p: p[0], default=(None, None)
        )[1]
        if not newest_version:
            return

        return full_image, image, newest_version

    async def process_file(path, client):
        with open(path, "r") as file:
            containers: list[dict[str, str | list]] = list(
                yaml.safe_load_all(file)
            )

        for container in containers:
            if not (result := await update(container, page_size, client)):
                continue

            full_image, image, newest_version = result
            container["image"] = f"{full_image}:{newest_version}"

            async with git_lock:
                with open(path, "w") as file:
                    yaml.dump_all(containers, file, sort_keys=False)

                repo.index.add([str(path)])
                repo.git.commit(
                    "-m",
                    f"refactor({path.stem}):"
                    f" update {image} to {newest_version}",
                )

            logging.info(f"Updated {full_image} to {newest_version}.")

    paths = sorted(
        list(Path(containers_folder).glob("*.yaml"))
        + list(Path(containers_folder).glob("*.yml"))
    )

    async with httpx.AsyncClient() as client:
        await asyncio.gather(*[process_file(path, client) for path in paths])


if __name__ == "__main__":
    asyncio.run(main())
