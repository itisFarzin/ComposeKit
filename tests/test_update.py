import httpx
from composekit.update import (
    Config,
    parse_image,
    extract_version,
    find_versions,
)


def test_parse_image_ghcr():
    result = parse_image("ghcr.io/kozea/radicale:3.5.10")
    assert result is not None
    registry, user, image, version = result
    assert registry == "ghcr.io"
    assert user == "kozea"
    assert image == "radicale"
    assert version == "3.5.10"


def test_parse_image_codeberg():
    result = parse_image("codeberg.org/readeck/readeck:0.21.5")
    assert result is not None
    registry, user, image, version = result
    assert registry == "codeberg.org"
    assert user == "readeck"
    assert image == "readeck"
    assert version == "0.21.5"


def test_parse_image_siyuan():
    result = parse_image("b3log/siyuan:v3.5.2")
    assert result is not None
    registry, user, image, version = result
    assert registry is None
    assert user == "b3log"
    assert image == "siyuan"
    assert version == "v3.5.2"


def test_parse_image_npmplus():
    result = parse_image("zoeyvid/npmplus")
    assert result is not None
    registry, user, image, version = result
    assert registry is None
    assert user == "zoeyvid"
    assert image == "npmplus"
    assert version == "latest"


def test_parse_image_nginx():
    result = parse_image("nginx")
    assert result is not None
    registry, user, image, version = result
    assert registry is None
    assert user == "_"
    assert image == "nginx"
    assert version == "latest"


def test_extract_version():
    version = extract_version("2026.1.20-410996df9", r"^(\d+\.\d+\.\d+)-\w+$")
    assert version == "2026.1.20"


def test_extract_version_with_no_pattern():
    version = extract_version("v1.5.1", None)
    assert version == "v1.5.1"


async def test_find_versions_siyuan():
    config = Config()
    container = {}
    registry = None
    user = "b3log"
    image = "siyuan"
    async with httpx.AsyncClient(timeout=int(config["timeout"])) as client:
        result = await find_versions(
            config, container, client, registry, user, image
        )
        assert len(result) > 0
