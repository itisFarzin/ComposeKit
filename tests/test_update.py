import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from packaging.version import Version

from composekit.container import Container
from composekit.update import (
    extract_version,
    find_versions,
    parse_image,
    parse_version,
    update,
)


class TestParse(unittest.TestCase):
    def test_parse_image(self) -> None:
        cases = [
            ("nginx", None, None, "nginx", "latest"),
            ("user/nginx", None, "user", "nginx", "latest"),
            (
                "registry.com/user/nginx:1.2.3",
                "registry.com",
                "user",
                "nginx",
                "1.2.3",
            ),
            ("ghcr.io/org/image:0.1.0", "ghcr.io", "org", "image", "0.1.0"),
        ]
        for image, registry, user, name, version in cases:
            with self.subTest(image=image):
                result = parse_image(image)
                if result is None:
                    self.fail("expected parse result")
                r, u, i, v = result
                self.assertEqual(r, registry)
                self.assertEqual(u, user)
                self.assertEqual(i, name)
                self.assertEqual(v, version)

    def test_parse_image_invalid(self) -> None:
        self.assertIsNone(parse_image("too/many/segments/for/image"))

    def test_extract_version(self) -> None:
        cases = [
            ("v1.2.3", None, "v1.2.3"),
            ("2026.1.20-abcdef", r"^(\d+\.\d+\.\d+)-\w+$", "2026.1.20"),
            ("1.2.3-beta", r"(\d+\.\d+\.\d+)", "1.2.3"),
            ("no-match", r"\d+\.\d+\.\d+", None),
        ]
        for version_str, pattern, expected in cases:
            with self.subTest(version_str=version_str):
                self.assertEqual(
                    extract_version(version_str, pattern), expected
                )

    def test_parse_version(self) -> None:
        cases = [
            ("1.2.3", Version("1.2.3")),
            ("v1.0.0", Version("1.0.0")),
            ("2.0.0a1", None),
            (None, None),
            ("not-a-version", None),
        ]
        for version_str, expected in cases:
            with self.subTest(version_str=version_str):
                result = parse_version(version_str)
                if expected is None:
                    self.assertIsNone(result)
                else:
                    self.assertEqual(result, expected)


class TestUpdate(unittest.IsolatedAsyncioTestCase):
    async def test_find_versions_mocked(self) -> None:
        def get_config(key: str) -> object:
            return {"limit": 2}[key]

        config = MagicMock()
        config.__getitem__.side_effect = get_config
        options: dict[str, object] = {}
        registry = None
        user = "user"
        image = "image"
        with patch(
            "composekit.update.list_tags", new_callable=AsyncMock
        ) as mock_list_tags:
            mock_list_tags.return_value = ["1.0.0", "1.1.0", "1.2.0"]
            async with httpx.AsyncClient() as client:
                result = await find_versions(
                    config, options, client, registry, user, image
                )
                self.assertTrue(
                    result == ["1.1.0", "1.2.0"]
                    or result[-2:] == ["1.1.0", "1.2.0"]
                )

    async def test_update_new_version(self) -> None:
        def get_config(key: str) -> object:
            return {
                "default_registry": "docker.io",
                "limit": 10,
                "timeout": 5,
                "user/image": {"update": True},
                "user": dict[str, object](),
                "image": dict[str, object](),
            }[key]

        config = MagicMock()
        config.__getitem__.side_effect = get_config
        container = Container(image="user/image:1.0.0")
        with patch(
            "composekit.update.find_versions", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = ["1.0.1", "1.0.2"]
            result = await update(config, container, AsyncMock())
            if result is None:
                self.fail("expected update result")
            full_image, image, newest_version = result
            self.assertEqual(newest_version, "1.0.2")
            self.assertTrue(full_image.endswith("user/image"))
            self.assertEqual(image, "image")

    async def test_update_accepts_container(self) -> None:
        def get_config(key: str) -> object:
            return {
                "default_registry": "docker.io",
                "limit": 10,
                "timeout": 5,
                "user/image": {"update": True},
                "user": dict[str, object](),
                "image": dict[str, object](),
            }[key]

        config = MagicMock()
        config.__getitem__.side_effect = get_config
        container = Container(image="user/image:1.0.0")
        with patch(
            "composekit.update.find_versions", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = ["1.0.1", "1.0.2"]
            result = await update(config, container, AsyncMock())
            if result is None:
                self.fail("expected update result")
            self.assertEqual(result[2], "1.0.2")

    async def test_update_disabled(self) -> None:
        def get_config(key: str) -> object:
            return {
                "default_registry": "docker.io",
                "limit": 10,
                "timeout": 5,
                "user/image": {"update": False},
            }[key]

        config = MagicMock()
        config.__getitem__.side_effect = get_config
        container = Container(image="user/image:1.0.0")
        result = await update(config, container, AsyncMock())
        self.assertIsNone(result)
