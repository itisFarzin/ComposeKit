from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields

Volume = str | dict[str, object]


@dataclass
class Container:
    image: str
    folder: str | None = None
    name: str | None = None
    restart: str | None = None
    privileged: bool | None = None
    network: str | None = None
    network_mode: str | None = None
    working_dir: str | None = None
    command: str | None = None
    entrypoint: str | None = None
    user: str | None = None
    shm_size: str | None = None
    cap_add: list[str] | None = None
    cap_drop: list[str] | None = None
    group_add: list[str] | None = None
    sysctls: list[str] | None = None
    devices: list[str] | None = None
    volumes: list[Volume] | None = None
    tmpfs: list[str] | None = None
    environment: list[str] | None = None
    ports: list[str] | None = None
    depends_on: list[str] | None = None
    labels: list[str] | dict[str, str] | None = None
    healthcheck: dict[str, object] | None = None

    @classmethod
    def fields(cls) -> list[str]:
        return list(field.name for field in fields(cls))

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Container:
        image = data.get("image")
        if not isinstance(image, str):
            raise TypeError("image must be a string")

        container = cls(image=image)
        for key, value in data.items():
            if key == "image":
                continue

            if key in cls.fields():
                setattr(container, key, value)

        return container

    def to_dict(self) -> dict[str, object]:
        return {
            key: getattr(self, key)
            for key in self.fields()
            if getattr(self, key) is not None
        }


def load_containers(documents: Iterable[object]) -> list[Container]:
    containers: list[Container] = []
    for document in documents:
        if not isinstance(document, Mapping):
            raise TypeError("container entry must be a mapping")

        data: dict[str, object] = {}
        for key, value in document.items():
            value: str | list[str]
            if not isinstance(key, str):
                raise TypeError("container keys must be strings")

            data[key] = value

        containers.append(Container.from_dict(data))

    return containers
