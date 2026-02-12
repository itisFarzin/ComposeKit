from typing import Any
from unittest.mock import MagicMock
from composekit.generate import (
    Config,
    is_custom_bind,
    handle_volumes,
    duplicate_entries,
    capitalize_name,
    generate,
)


def test_is_custom_bind() -> None:
    assert is_custom_bind("/volume:rw;config") is True
    assert is_custom_bind("/volume:/container") is False
    assert is_custom_bind("/volume") is True


def make_mock_config(bind_path: str = "/bind") -> Config:
    config = MagicMock(spec=Config)
    config.__getitem__.side_effect = lambda key: {
        "bind_path": bind_path,
        "use_full_directory": True,
        "capitalize_folder_name": False,
        "restart_policy": "unless-stopped",
        "network_name": "cloud",
    }[key]
    return config


def test_handle_volumes_basic() -> None:
    config = make_mock_config()
    volumes = ["/volume", "/volume2"]
    container: dict[str, Any] = {}
    result = handle_volumes(config, container, "container", volumes, [])
    expected = [
        "/bind/container/volume:/volume",
        "/bind/container/volume2:/volume2",
    ]
    assert result == expected


def test_handle_volumes_with_custom_binds() -> None:
    config = make_mock_config()
    volumes = ["/volume:/volume", "/volume2:/volume2"]
    container: dict[str, Any] = {}
    result = handle_volumes(config, container, "container", volumes, [])
    assert result == ["/volume:/volume", "/volume2:/volume2"]


def test_handle_volumes_with_mount_options_and_custom_name() -> None:
    config = make_mock_config()
    volumes = ["/volume:ro;config", "/volume2:rw;data"]
    container: dict[str, Any] = {}
    result = handle_volumes(config, container, "container", volumes, [])
    assert result == [
        "/bind/container/config:/volume:ro",
        "/bind/container/data:/volume2:rw",
    ]


def test_duplicate_entries() -> None:
    devices = ["/device", "/device2:/device2"]
    result = duplicate_entries(devices)
    assert result == ["/device:/device", "/device2:/device2"]


def test_capitalize_name() -> None:
    assert capitalize_name("docker") == "Docker"
    assert capitalize_name("D") == "D"


def test_generate_minimal() -> None:
    config = make_mock_config()
    container = {"image": "nginx"}
    result = generate("web", container, config)
    assert result["image"] == "nginx"
    assert result["hostname"] == "web"
    assert result["container_name"] == "web"
    assert result["restart"] == "unless-stopped"
    assert result["networks"] == ["cloud"]
