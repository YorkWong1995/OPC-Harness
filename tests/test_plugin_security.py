from pathlib import Path

import pytest

from opc.project_types import load_project_type_registry
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


def _write_project_type_manifest(path: Path, *, permissions: str = '["read"]', extra: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
[[project_type]]
id = "demo"
display_name = "Demo"
permissions = {permissions}
{extra}

[project_type.template_provider]
template_id = "demo-template"
kind = "filesystem"
path = "templates/demo"
""".strip(),
        encoding="utf-8",
    )


def test_disabled_project_type_plugin_manifest_is_not_loaded(tmp_path: Path):
    manifest = tmp_path / "plugins" / "demo" / "opc-plugin.toml"
    _write_project_type_manifest(manifest, extra='unknown_field = "ignored-if-disabled"')

    registry = load_project_type_registry(tmp_path, (), {"demo": {"manifest_path": str(manifest)}})

    assert registry.list() == ()


def test_project_type_manifest_path_must_stay_under_project_root(tmp_path: Path):
    outside = tmp_path.parent / "outside-plugin.toml"
    outside.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="escapes project root"):
        load_project_type_registry(tmp_path, ("demo",), {"demo": {"manifest_path": str(outside)}})


def test_project_type_manifest_rejects_unknown_fields(tmp_path: Path):
    manifest = tmp_path / "plugins" / "demo" / "opc-plugin.toml"
    _write_project_type_manifest(manifest, extra='surprise = "field"')

    with pytest.raises(ValueError, match="unknown field"):
        load_project_type_registry(tmp_path, ("demo",), {"demo": {"manifest_path": str(manifest)}})


def test_project_type_manifest_rejects_permission_escalation(tmp_path: Path):
    manifest = tmp_path / "plugins" / "demo" / "opc-plugin.toml"
    _write_project_type_manifest(manifest, permissions='["read", "admin"]')

    with pytest.raises(ValueError, match="invalid project type permissions"):
        load_project_type_registry(tmp_path, ("demo",), {"demo": {"manifest_path": str(manifest)}})
