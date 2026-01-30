from composekit.generate import (
    Config,
    is_custom_bind,
    handle_volumes,
    handle_devices,
)


def test_is_custom_bind():
    result = is_custom_bind("/volume:rw;config")
    assert result is True


def test_handle_volumes():
    config = Config()
    volumes = ["/volume", "/volume2"]
    container = {}
    result = handle_volumes(config, container, "container", volumes, [])
    assert result == [
        "${BIND_PATH}/container/volume:/volume",
        "${BIND_PATH}/container/volume2:/volume2",
    ]


def test_handle_volumes_with_custom_binds():
    config = Config()
    volumes = ["/volume:/volume", "/volume2:/volume2"]
    container = {}
    result = handle_volumes(config, container, "container", volumes, [])
    assert result == ["/volume:/volume", "/volume2:/volume2"]


def test_handle_volumes_with_custom_binds_and_mount_options():
    config = Config()
    volumes = ["/volume:/volume:ro", "/volume2:/volume2:rw"]
    container = {}
    result = handle_volumes(config, container, "container", volumes, [])
    assert result == ["/volume:/volume:ro", "/volume2:/volume2:rw"]


def test_handle_volumes_with_mount_options_and_custom_name():
    config = Config()
    volumes = ["/volume:ro;config", "/volume2:rw;data"]
    container = {}
    result = handle_volumes(config, container, "container", volumes, [])
    assert result == [
        "${BIND_PATH}/container/config:/volume:ro",
        "${BIND_PATH}/container/data:/volume2:rw",
    ]


def test_handle_devices():
    devices = ["/device", "/device2:/device2"]
    result = handle_devices(devices)
    assert result == ["/device:/device", "/device2:/device2"]
