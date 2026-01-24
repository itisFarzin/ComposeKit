from generate import Config, handle_volumes, is_valid_volume


def test_is_valid_volume():
    result = is_valid_volume("/volume:rw;config")
    assert result is True


def test_handle_volumes():
    config = Config()
    volumes = ["/volume", "/volume2"]
    result = handle_volumes(config, {}, "container", volumes, [])
    assert result == [
        "${BIND_PATH}/container/volume:/volume",
        "${BIND_PATH}/container/volume2:/volume2",
    ]


def test_handle_volumes_with_custom_binds():
    config = Config()
    volumes = ["/volume:/volume", "/volume2:/volume2"]
    result = handle_volumes(config, {}, "container", volumes, [])
    assert result == ["/volume:/volume", "/volume2:/volume2"]


def test_handle_volumes_with_custom_binds_and_mount_options():
    config = Config()
    volumes = ["/volume:/volume:ro", "/volume2:/volume2:rw"]
    result = handle_volumes(config, {}, "container", volumes, [])
    assert result == ["/volume:/volume:ro", "/volume2:/volume2:rw"]


def test_handle_volumes_with_mount_options_and_custom_name():
    config = Config()
    volumes = ["/volume:ro;config", "/volume2:rw;data"]
    result = handle_volumes(config, {}, "container", volumes, [])
    assert result == [
        "${BIND_PATH}/container/config:/volume:ro",
        "${BIND_PATH}/container/data:/volume2:rw",
    ]
