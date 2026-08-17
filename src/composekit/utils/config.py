import os
from typing import ClassVar

import yaml


class Config:
    config: dict[str, object]
    config_paths: ClassVar[tuple[str, ...]] = ()
    default_values: ClassVar[dict[str, object]] = {}

    def __init__(self) -> None:
        self.config = {}
        self.load(*self.config_paths)

    def load(self, *paths: str) -> None:
        for path in paths:
            if not os.path.exists(path):
                continue

            with open(path) as file:
                self.config.update(yaml.safe_load(file) or {})

    def __setitem__(self, key: str, value: object) -> None:
        self.config[key] = value

    def __getitem__(self, key: str) -> object | None:
        sources = (
            os.getenv(key.upper()),
            self.config.get(key.lower()),
            self.default_values.get(key),
        )
        for value in sources:
            if value is not None:
                return value
