from pathlib import Path

from opc.project_types import load_project_type_registry


SAMPLE_PLUGIN_SETTINGS = {
    "sample_project_type": {
        "manifest_path": "examples/opc_plugins/sample_project_type/opc-plugin.toml",
    },
}


def test_sample_project_type_plugin_is_disabled_until_enabled() -> None:
    registry = load_project_type_registry(Path.cwd(), (), SAMPLE_PLUGIN_SETTINGS)

    assert registry.list() == ()


def test_sample_project_type_plugin_registers_non_qt_static_site() -> None:
    registry = load_project_type_registry(Path.cwd(), ("sample_project_type",), SAMPLE_PLUGIN_SETTINGS)
    static_site = registry.get("static-site")

    assert static_site is not None
    assert static_site.id == "static-site"
    assert static_site.display_name == "Static Site"
    assert static_site.source == "plugin"
    assert static_site.plugin_id == "sample_project_type"
    assert static_site.permissions == ("read", "write")
    assert static_site.template_provider.template_id == "static-html"
    assert static_site.template_provider.path == "examples/opc_plugins/sample_project_type/templates/static-html"
    assert static_site.template_provider.file_patterns == ("index.html", "README.md")
    assert static_site.env_checks == ()
    assert static_site.build_commands == ()
    assert [check.id for check in static_site.acceptance_checks] == ["static-site-files"]
    assert "qt" not in static_site.id
    assert "qt" not in static_site.template_provider.path.lower()
