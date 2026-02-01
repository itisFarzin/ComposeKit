#!/usr/bin/env python3

import os
import shutil
from typing import Any
from pathlib import Path

try:
    import yaml
    from git import Repo
except ImportError:
    print(
        "ERROR: Missing the required package(s). Install them via:"
        "\npip install -r requirements.txt"
    )
    exit(1)


class Config(dict):
    config: dict[str, str | int | list]
    config_path = "config/generate.yaml"
    default_values: dict[str, str | int | bool] = {
        "containers_folder": "containers",
        "composes_folder": "composes",
        "network_name": "cloud",
        "network_driver": "bridge",
        "subnet": "172.20.0.0/24",
        "restart_policy": "unless-stopped",
        "use_full_directory": True,
        "capitalize_folder_name": False,
        "bind_path": "/home/docker/Docker",
        "output": "docker-compose.yaml",
    }

    def __init__(self):
        with open(self.config_path, "r") as file:
            self.config = yaml.safe_load(file)

    def __getitem__(self, key: str) -> Any:
        return (
            os.getenv(key.upper())
            or self.config.get(key.lower())
            or self.default_values.get(key)
        )


OPTIONS = (
    "network",
    "working_dir",
    "command",
    "network_mode",
    "user",
    "entrypoint",
    "cap_add",
    "cap_drop",
    "sysctls",
    "labels",
    "devices",
    "volumes",
    "tmpfs",
    "environment",
    "depends_on",
    "healthcheck",
    "ports",
    "shm_size",
)

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


def capitalize_name(name: str) -> str:
    return name[0].upper() + name[1:]


def is_custom_bind(volume: str):
    volume_segments = volume.split(":")
    if len(volume_segments) == 1:
        return True

    if len(volume_segments) == 2:
        mount_type = volume_segments[1].split(";")[0]
        return mount_type in MOUNT_OPTIONS

    return False


def handle_volumes(
    config: Config,
    container: dict[str, Any],
    name: str,
    volumes: list[str],
    used_volumes: list[str],
):
    folder = str(container.get("folder", name))
    if config["capitalize_folder_name"]:
        folder = capitalize_name(folder)

    bind_path = str(config["bind_path"])
    use_full_directory = bool(config["use_full_directory"])
    custom_binds = list(filter(is_custom_bind, volumes))
    result = []

    for volume in volumes:
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


def handle_devices(devices: list[str]):
    return [
        f"{device}:{device}" if ":" not in device else device
        for device in devices
    ]


def generate(name: str, container: dict[str, Any], config: Config):
    folder = str(container.get("folder", name))
    if config["capitalize_folder_name"]:
        folder = capitalize_name(folder)

    restart_policy = str(config["restart_policy"])
    network = str(config["network_name"])

    used_volumes: list[str] = []
    result = {
        "image": container["image"],
        "hostname": name,
        "container_name": name,
        "restart": container.get("restart", restart_policy),
    }

    for option in OPTIONS:
        if option not in container:
            continue

        value = container[option]

        match option:
            case "devices":
                result[option] = handle_devices(value)
            case "volumes":
                result[option] = handle_volumes(
                    config, container, name, value, used_volumes
                )
            case _:
                result[option] = value

    if "network_mode" not in container:
        result["networks"] = [network]

    return result


def main() -> None:
    repo = Repo(".")
    # Discard any changes
    repo.index.reset(working_tree=True)

    config = Config()

    containers_folder = str(config["containers_folder"])
    composes_folder = str(config["composes_folder"])
    network = str(config["network_name"])
    network_driver = str(config["network_driver"])
    subnet = str(config["subnet"])
    gateway = subnet.rsplit(".", 1)[0] + ".1"
    output = str(config["output"])

    main_template = yaml.safe_load(
        open("templates/main-compose.yaml")
        .read()
        .lstrip()
        .format(
            network=network,
            driver=network_driver,
            subnet=subnet,
            gateway=gateway,
        )
    )
    main_template["services"] = {}
    composes_template = open("templates/composes.yaml").read().lstrip()
    service_template = open("templates/services.yaml").read().lstrip()

    if os.path.exists(composes_folder):
        shutil.rmtree(composes_folder)

    os.mkdir(composes_folder)

    paths = sorted(
        p
        for p in Path(containers_folder).iterdir()
        if p.is_file() and p.suffix in {".yml", ".yaml"}
    )

    for path in paths:
        used_names: list[str] = []

        service: dict[str, dict] = yaml.safe_load(
            service_template.format(network=network)
        )
        service["services"] = {}

        with open(path, "r") as file:
            containers: list[dict[str, Any]] = list(yaml.safe_load_all(file))

        for container in containers:
            name = str(container.get("name", path.stem))
            if name in used_names:
                number = str(used_names.count(name) + 1)
                container["name"] = name = f"{name}_{number}"
                if container["folder"]:
                    container["folder"] += number

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

    repo.git.add(".")
    staged_count = len(repo.index.diff(repo.head.commit))
    if staged_count > 0:
        repo.index.commit(
            f"refactor(composes): update {staged_count} compose file(s)"
        )


if __name__ == "__main__":
    main()
