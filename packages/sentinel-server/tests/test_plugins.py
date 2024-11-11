import dataclasses
from importlib.metadata import EntryPoint
from unittest.mock import MagicMock

import pytest
from sentinel_core.plugins import ComponentDescriptor, Plugin

from sentinel_server.config import Configuration
from sentinel_server.plugins import PluginManager


@pytest.fixture
def mock_entry_points(
    mocker,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    mock_entry_point_1 = mocker.MagicMock(spec=EntryPoint)
    mock_entry_point_1.name = "plugin1"
    mock_entry_point_1.dist.name = "plugin1"
    mock_plugin_1 = mocker.MagicMock(spec=Plugin)
    mock_plugin_1.components = frozenset({mocker.MagicMock(spec=ComponentDescriptor)})
    mock_entry_point_1.load.return_value = mock_plugin_1

    mock_entry_point_2 = mocker.MagicMock(spec=EntryPoint)
    mock_entry_point_2.name = "plugin2"
    mock_entry_point_2.dist.name = "plugin2"
    mock_plugin_2 = mocker.MagicMock(spec=Plugin)
    mock_plugin_2.components = frozenset({mocker.MagicMock(spec=ComponentDescriptor)})
    mock_entry_point_2.load.return_value = mock_plugin_2

    mock_entry_point_4 = mocker.MagicMock(spec=EntryPoint)
    mock_entry_point_4.name = "plugin4"
    mock_entry_point_4.dist.name = "plugin4"
    mock_plugin_4 = mocker.MagicMock(spec=Plugin)
    mock_plugin_4.components = frozenset({mocker.MagicMock(spec=ComponentDescriptor)})
    mock_entry_point_4.load.return_value = mock_plugin_4

    mocker.patch(
        "importlib.metadata.entry_points",
        return_value=(mock_entry_point_1, mock_entry_point_2, mock_entry_point_4),
    )

    return (mock_entry_point_1, mock_entry_point_2, mock_entry_point_4)


@pytest.fixture
def plugin_manager(tmp_path) -> PluginManager:
    config_path = str(tmp_path / "config.toml")

    plugin_whitelist = {"plugin1", "plugin2", "plugin3"}
    config = Configuration(plugin_whitelist=plugin_whitelist)

    config.serialise(config_path)

    return PluginManager(
        whitelist=plugin_whitelist,
        config=config,
        config_path=config_path,
    )


def test_init_plugins(plugin_manager, mock_entry_points):
    plugin_manager.init_plugins()

    assert len(plugin_manager.plugin_descriptors) == 3

    assert plugin_manager.plugin_descriptors[0].name == "plugin1"
    assert plugin_manager.plugin_descriptors[0].entry_point == mock_entry_points[0]
    assert plugin_manager.plugin_descriptors[0].plugin is not None

    assert plugin_manager.plugin_descriptors[1].name == "plugin2"
    assert plugin_manager.plugin_descriptors[1].entry_point == mock_entry_points[1]
    assert plugin_manager.plugin_descriptors[1].plugin is not None

    assert plugin_manager.plugin_descriptors[2].name == "plugin4"
    assert plugin_manager.plugin_descriptors[2].entry_point == mock_entry_points[2]
    assert (
        plugin_manager.plugin_descriptors[2].plugin is None
    )  # Plugin is not in whitelist, so should not be loaded.


def test_add_to_whitelist_nonexisting(plugin_manager: PluginManager) -> None:
    assert plugin_manager.add_to_whitelist("plugin4")

    assert "plugin4" in plugin_manager.get_whitelist()
    assert "plugin4" in plugin_manager.config.plugin_whitelist
    assert plugin_manager.is_dirty

    loaded_config = Configuration.deserialise(plugin_manager.config_path)
    assert "plugin4" in loaded_config.plugin_whitelist


def test_add_to_whitelist_existing(plugin_manager: PluginManager) -> None:
    assert not plugin_manager.add_to_whitelist("plugin1")

    assert "plugin1" in plugin_manager.get_whitelist()
    assert "plugin1" in plugin_manager.config.plugin_whitelist
    assert not plugin_manager.is_dirty

    loaded_config = Configuration.deserialise(plugin_manager.config_path)
    assert "plugin1" in loaded_config.plugin_whitelist


def test_remove_from_whitelist_existing(plugin_manager: PluginManager) -> None:
    assert "plugin1" in plugin_manager.get_whitelist()
    assert plugin_manager.remove_from_whitelist("plugin1")

    assert "plugin1" not in plugin_manager.get_whitelist()
    assert "plugin1" not in plugin_manager.config.plugin_whitelist
    assert plugin_manager.is_dirty

    loaded_config = Configuration.deserialise(plugin_manager.config_path)
    assert "plugin1" not in loaded_config.plugin_whitelist


def test_remove_from_whitelist_nonexisting(plugin_manager: PluginManager) -> None:
    whitelist_before = set(plugin_manager.get_whitelist())
    config_before = dataclasses.replace(plugin_manager.config)

    assert not plugin_manager.remove_from_whitelist("plugin5")
    assert not plugin_manager.is_dirty

    # No changes should have been made to the whitelist.
    assert plugin_manager.get_whitelist() == whitelist_before
    assert plugin_manager.config == config_before

    loaded_config = Configuration.deserialise(plugin_manager.config_path)
    assert loaded_config == config_before


def test_find_plugin_desc_existing(plugin_manager, mock_entry_points):
    plugin_manager.init_plugins()

    plugin_desc = plugin_manager.find_plugin_desc(lambda desc: desc.name == "plugin1")
    assert plugin_desc is not None
    assert plugin_desc.name == "plugin1"
    assert plugin_desc.entry_point == mock_entry_points[0]
    assert plugin_desc.plugin is not None


def test_find_plugin_desc_nonexisting(plugin_manager, mock_entry_points):
    plugin_manager.init_plugins()

    plugin_desc = plugin_manager.find_plugin_desc(lambda desc: desc.name == "plugin5")
    assert plugin_desc is None


def test_find_plugin_existing(plugin_manager, mock_entry_points):
    plugin_manager.init_plugins()

    mock_plugin_desc_1 = plugin_manager.find_plugin_desc(
        lambda desc: desc.name == "plugin1"
    )
    mock_plugin_1 = mock_plugin_desc_1.plugin

    plugin, plugin_desc = plugin_manager.find_plugin(
        lambda plugin: plugin == mock_plugin_1
    )
    assert plugin == mock_plugin_1
    assert plugin_desc == mock_plugin_desc_1


def test_find_plugin_nonexisting(plugin_manager, mock_entry_points):
    plugin_manager.init_plugins()

    plugin, plugin_desc = plugin_manager.find_plugin(lambda plugin: False)
    assert plugin is None
    assert plugin_desc is None


def test_find_component_existing(plugin_manager, mock_entry_points):
    plugin_manager.init_plugins()

    mock_plugin_desc_1 = plugin_manager.find_plugin_desc(
        lambda desc: desc.name == "plugin1"
    )
    mock_plugin_1 = mock_plugin_desc_1.plugin
    mock_component = list(mock_plugin_1.components)[0]

    component, plugin_desc = plugin_manager.find_component(
        lambda component: component == mock_component
    )

    assert component == mock_component
    assert plugin_desc == mock_plugin_desc_1


def test_find_component_nonexisting(plugin_manager, mock_entry_points):
    plugin_manager.init_plugins()

    component, plugin_desc = plugin_manager.find_component(lambda component: False)

    assert component is None
    assert plugin_desc is None
