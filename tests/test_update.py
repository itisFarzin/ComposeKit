import httpx
import pytest
from typing import Any
from packaging.version import Version
from unittest.mock import AsyncMock, MagicMock, patch
from composekit.update import (
    Config,
    parse_image,
    extract_version,
    parse_version,
    find_versions,
    update,
)


def test_config_default(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config()
    assert config["containers_folder"] == "containers"
    assert config["limit"] == 40
    assert config["timeout"] == 10
    monkeypatch.setenv("LIMIT", "123")
    assert config["limit"] == "123"


@pytest.mark.parametrize(
    "image,registry,user,name,version",
    [
        ("nginx", None, "_", "nginx", "latest"),
        ("user/nginx", None, "user", "nginx", "latest"),
        (
            "registry.com/user/nginx:1.2.3",
            "registry.com",
            "user",
            "nginx",
            "1.2.3",
        ),
        ("ghcr.io/org/image:0.1.0", "ghcr.io", "org", "image", "0.1.0"),
    ],
)
def test_parse_image(
    image: str, registry: str, user: str, name: str, version: str
) -> None:
    result = parse_image(image)
    assert result is not None
    r, u, i, v = result
    assert r == registry
    assert u == user
    assert i == name
    assert v == version


def test_parse_image_invalid() -> None:
    assert parse_image("too/many/segments/for/image") is None


@pytest.mark.parametrize(
    "version_str,pattern,expected",
    [
        ("v1.2.3", None, "v1.2.3"),
        ("2026.1.20-abcdef", r"^(\d+\.\d+\.\d+)-\w+$", "2026.1.20"),
        ("1.2.3-beta", r"(\d+\.\d+\.\d+)", "1.2.3"),
        ("no-match", r"\d+\.\d+\.\d+", None),
    ],
)
def test_extract_version(
    version_str: str, pattern: str | None, expected: str | None
) -> None:
    assert extract_version(version_str, pattern) == expected


@pytest.mark.parametrize(
    "version_str,expected",
    [
        ("1.2.3", Version("1.2.3")),
        ("v1.0.0", Version("1.0.0")),
        ("2.0.0a1", None),
        (None, None),
        ("not-a-version", None),
    ],
)
def test_parse_version(
    version_str: str | None, expected: Version | None
) -> None:
    result = parse_version(version_str)
    if expected is None:
        assert result is None
    else:
        assert result == expected


@pytest.mark.asyncio
async def test_find_versions_mocked() -> None:
    config = MagicMock()
    config.__getitem__.side_effect = lambda key: {"limit": 2}[key]
    container: dict[str, Any] = {}
    registry = None
    user = "user"
    image = "image"
    with patch(
        "composekit.update.list_tags", new_callable=AsyncMock
    ) as mock_list_tags:
        mock_list_tags.return_value = ["1.0.0", "1.1.0", "1.2.0"]
        async with httpx.AsyncClient() as client:
            result = await find_versions(
                config, container, client, registry, user, image
            )
            assert result == ["1.1.0", "1.2.0"] or result[-2:] == [
                "1.1.0",
                "1.2.0",
            ]


@pytest.mark.asyncio
async def test_update_new_version() -> None:
    config = MagicMock()
    config.__getitem__.side_effect = lambda key: {
        "limit": 10,
        "timeout": 5,
        "user/image": {"update": True},
        "user": {},
        "image": {},
    }[key]
    container = {"image": "user/image:1.0.0"}
    with patch(
        "composekit.update.find_versions", new_callable=AsyncMock
    ) as mock_find:
        mock_find.return_value = ["1.0.1", "1.0.2"]
        result = await update(config, container, AsyncMock())
        assert result is not None
        full_image, image, newest_version = result
        assert newest_version == "1.0.2"
        assert full_image.endswith("user/image")
        assert image == "image"


@pytest.mark.asyncio
async def test_update_disabled() -> None:
    config = MagicMock()
    config.__getitem__.side_effect = lambda key: {
        "limit": 10,
        "timeout": 5,
        "user/image": {"update": False},
    }[key]
    container = {"image": "user/image:1.0.0"}
    result = await update(config, container, AsyncMock())
    assert result is None
