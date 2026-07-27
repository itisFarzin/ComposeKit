#!/usr/bin/env python3

import argparse
import os
import shutil
from collections.abc import Sequence
from importlib.resources import files
from typing import ClassVar

try:
    import yaml

    from composekit.container import Container, Volume, load_containers
    from composekit.utils import Config as _Config
    from composekit.utils import iter_container_files, open_repo
except ImportError as err:
    raise RuntimeError(
        "ERROR: Missing required packages. See the README."
    ) from err


class Config(_Config):
    config_paths = ("config/generate.yaml",)
    default_values: ClassVar[dict[str, object]] = {
        "containers_folder": "containers",
        "composes_folder": "composes",
        "network_name": "cloud",
        "network_driver": "bridge",
        "subnet": "172.20.0.0/24",
        "restart_policy": "unless-stopped",
        "use_full_directory": True,
        "capitalize_folder_name": "non_custom",
        "bind_path": "/home/docker/Docker",
        "output": "docker-compose.yaml",
    }


MOUNT_OPTIONS = {
    "rw",
    "ro",
    "nocopy",
    "z",
    "Z",
    "delegated",
    "cached",
    "readonly",
    "rshared",
    "rslave",
    "private",
    "rprivate",
    "slave",
}


def get_folder_name(name: str, container: Container, config: Config) -> str:
    folder = container.folder or name
    mode = config["capitalize_folder_name"]
    if mode == "full" or (mode == "non_custom" and not container.folder):
        folder = capitalize_name(folder)

    return folder


def capitalize_name(name: str) -> str:
    return name[0].upper() + name[1:]


def is_custom_bind(volume: Volume) -> bool:
    if isinstance(volume, dict):
        return True

    volume_segments = volume.split(":")
    if len(volume_segments) == 1:
        return True

    if len(volume_segments) == 2:
        mount_type = volume_segments[1].split(";")[0]
        return mount_type in MOUNT_OPTIONS

    return False


def handle_volumes(
    config: Config,
    folder: str,
    volumes: Sequence[Volume],
    used_volumes: list[str],
) -> list[Volume]:
    bind_path = str(config["bind_path"])
    use_full_directory = bool(config["use_full_directory"])
    custom_binds = list(filter(is_custom_bind, volumes))
    result: list[Volume] = []

    for volume in volumes:
        if isinstance(volume, dict):
            result.append(volume)
            continue

        custom_name = ""
        if ";" in volume:
            volume, custom_name = volume.split(";", 1)

        volume_segments = volume.rsplit(":")
        mount_option = (
            volume_segments.pop()
            if volume_segments[-1] in MOUNT_OPTIONS
            else None
        )

        if len(volume_segments) == 1:
            host_path = f"{bind_path}/{folder}"
            volume_name = custom_name or volume_segments[0].rsplit("/", 1)[-1]

            if volume_name in used_volumes:
                volume_name += str(used_volumes.count(volume_name) + 1)

            if not use_full_directory or len(custom_binds) != 1:
                host_path += f"/{volume_name}"

            volume_segments = [host_path, volume_segments[0]]

        if mount_option:
            volume_segments.append(mount_option)

        used_volumes.append(volume_segments[0].rsplit("/", 1)[-1])
        result.append(":".join(volume_segments))

    return result


def duplicate_entries(entries: list[str]) -> list[str]:
    return [
        f"{entry}:{entry}" if ":" not in entry else entry for entry in entries
    ]


def generate(
    name: str, container: Container, config: Config
) -> dict[str, object]:
    folder = get_folder_name(name, container, config)

    restart_policy = str(config["restart_policy"])
    network = str(config["network_name"])

    used_volumes: list[str] = []
    result: dict[str, object] = {
        "image": container.image,
        "hostname": name,
        "container_name": name,
        "restart": container.restart or restart_policy,
    }

    for option in Container.fields():
        if option in ("folder", "name", "image"):
            continue

        value = getattr(container, option)
        if value is None:
            continue

        match option:
            case "devices":
                result[option] = duplicate_entries(value)
            case "ports":
                result[option] = duplicate_entries(value)
            case "volumes":
                result[option] = handle_volumes(
                    config, folder, value, used_volumes
                )
            case _:
                result[option] = value

    if not container.network_mode:
        result["networks"] = [network]

    return result


def build_config(args: argparse.Namespace) -> Config:
    config = Config()
    if args.config:
        config.load(*args.config)

    overrides = {
        "containers_folder": args.containers,
        "composes_folder": args.composes,
        "output": args.output,
    }
    for key, value in overrides.items():
        if value:
            config[key] = value

    return config


def main(args: argparse.Namespace) -> None:
    config = build_config(args)

    containers_folder = str(config["containers_folder"])
    composes_folder = str(config["composes_folder"])
    network = str(config["network_name"])
    network_driver = str(config["network_driver"])
    subnet = str(config["subnet"])
    gateway = subnet.rsplit(".", 1)[0] + ".1"
    output = str(config["output"])

    templates = files("composekit.templates")

    main_template = yaml.safe_load(
        templates.joinpath("main-compose.yaml")
        .read_text()
        .lstrip()
        .format(
            network=network,
            driver=network_driver,
            subnet=subnet,
            gateway=gateway,
        )
    )
    main_template["services"] = dict[str, object]()

    composes_template = (
        templates.joinpath("composes.yaml").read_text().lstrip()
    )
    service_template = templates.joinpath("services.yaml").read_text().lstrip()

    if os.path.exists(composes_folder):
        shutil.rmtree(composes_folder)

    os.mkdir(composes_folder)

    paths = iter_container_files(containers_folder)
    for path in paths:
        used_names: list[str] = []

        service: dict[str, dict[str, object]] = yaml.safe_load(
            service_template.format(network=network)
        )
        service["services"] = dict[str, object]()

        with open(path) as file:
            containers = load_containers(yaml.safe_load_all(file))

        for container in containers:
            name = container.name or path.stem
            if name in used_names:
                number = str(used_names.count(name) + 1)
                container.name = name = f"{name}_{number}"
                if container.folder:
                    container.folder += number

            used_names.append(name)
            service["services"][name] = generate(name, container, config)
            main_template["services"][name] = yaml.safe_load(
                composes_template.format(
                    name=name, path=f"{composes_folder}/{path.name}"
                )
            )

        with open(f"{composes_folder}/{path.stem}.yaml", "w") as compose:
            yaml.dump(service, compose, sort_keys=False)

    with open(output, "w") as file:
        yaml.dump(main_template, file, sort_keys=False)

    if args.commit:
        repo = open_repo(reset=False)
        repo.add(".")
        staged_count = repo.staged_count()
        if staged_count > 0:
            repo.commit(
                f"chore(composes): update {staged_count} compose file(s)"
            )
