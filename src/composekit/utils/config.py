import os
import yaml
from typing import Any, ClassVar


class Config:
    config: dict[str, Any]
    config_paths: ClassVar[tuple[str, ...]]
    default_values: ClassVar[dict[str, Any]]

    def __init__(self) -> None:
        self.config = {}
        for config_path in self.config_paths:
            self._load_config(config_path)

    def _load_config(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            return

        with open(file_path, "r") as file:
            self.config.update(yaml.safe_load(file) or {})

    def __setitem__(self, key: str, value: Any) -> None:
        self.config[key] = value

    def __getitem__(self, key: str) -> Any:
        return (
            os.getenv(key.upper())
            or self.config.get(key.lower())
            or self.default_values.get(key)
        )
