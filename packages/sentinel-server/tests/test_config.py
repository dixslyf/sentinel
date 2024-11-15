import pathlib

from sentinel_server.config import Configuration, get_config


def test_serialise_and_deserialise(tmp_path: pathlib.Path):
    """
    Tests that deserialisation returns the serialiased configuration.
    """
    config = Configuration(
        db_url="sqlite:///test/db.sqlite3", plugin_whitelist={"plugin1", "plugin2"}
    )

    config_path = tmp_path / "config.toml"
    config.serialise(str(config_path))

    loaded_config = Configuration.deserialise(str(config_path))

    assert config == loaded_config


def test_get_config_existing_file(tmp_path: pathlib.Path):
    """
    Tests `get_config()` when the configuration file exists.
    `get_config()` should simply load the configuration file into a `Configuration`.
    """
    config = Configuration(
        db_url="sqlite:///test/db.sqlite3", plugin_whitelist={"plugin1", "plugin2"}
    )

    config_path = tmp_path / "config.toml"
    config.serialise(str(config_path))

    loaded_config = get_config(str(config_path))

    assert config == loaded_config


def test_get_config_non_existing_file(tmp_path: pathlib.Path):
    """
    Tests `get_config()` when the configuration file does not exist.
    `get_config()` should create and return a default configuration,
    and save it to the given path.
    """
    config_path = tmp_path / "config.toml"
    config = get_config(str(config_path))

    default_config = Configuration()

    assert config == default_config

    # Check that the saved configuration is the same as the created one.
    loaded_config = Configuration.deserialise(str(config_path))
    assert config == loaded_config
