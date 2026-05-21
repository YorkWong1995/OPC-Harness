from pathlib import Path

from opc.tools.tool_registry import _TOOL_REGISTRY, get_tool, load_plugin_tools


def _remove_tool(name: str) -> None:
    _TOOL_REGISTRY.pop(name, None)


def test_plugin_without_manifest_is_not_loaded(tmp_path: Path):
    plugins = tmp_path / "opc_plugins"
    plugins.mkdir()
    (plugins / "loose.py").write_text(
        "from opc.tools.tool_registry import register_tool\n"
        "@register_tool(name='loose_tool', description='x', input_schema={'type': 'object'}, permission='read')\n"
        "def loose_tool():\n    return 'x'\n",
        encoding="utf-8",
    )

    loaded = load_plugin_tools(plugins_dir=plugins)
    assert loaded == []
    assert get_tool("loose_tool") is None
    _remove_tool("loose_tool")


def test_plugin_with_manifest_and_permission_is_loaded(tmp_path: Path):
    plugins = tmp_path / "opc_plugins"
    plugins.mkdir()
    (plugins / "opc-plugin.toml").write_text(
        "[[plugin]]\nmodule = 'safe.py'\npermissions = ['read']\n",
        encoding="utf-8",
    )
    (plugins / "safe.py").write_text(
        "from opc.tools.tool_registry import register_tool\n"
        "@register_tool(name='safe_plugin_tool', description='x', input_schema={'type': 'object'}, permission='read')\n"
        "def safe_plugin_tool():\n    return 'x'\n",
        encoding="utf-8",
    )

    loaded = load_plugin_tools(plugins_dir=plugins)
    assert loaded == [plugins / "safe.py"]
    assert get_tool("safe_plugin_tool") is not None
    _remove_tool("safe_plugin_tool")


def test_plugin_permission_mismatch_removes_registered_tool(tmp_path: Path):
    plugins = tmp_path / "opc_plugins"
    plugins.mkdir()
    (plugins / "opc-plugin.toml").write_text(
        "[[plugin]]\nmodule = 'unsafe.py'\npermissions = ['read']\n",
        encoding="utf-8",
    )
    (plugins / "unsafe.py").write_text(
        "from opc.tools.tool_registry import register_tool\n"
        "@register_tool(name='unsafe_plugin_tool', description='x', input_schema={'type': 'object'}, permission='write')\n"
        "def unsafe_plugin_tool():\n    return 'x'\n",
        encoding="utf-8",
    )

    loaded = load_plugin_tools(plugins_dir=plugins)
    assert loaded == [plugins / "unsafe.py"]
    assert get_tool("unsafe_plugin_tool") is None
    _remove_tool("unsafe_plugin_tool")
