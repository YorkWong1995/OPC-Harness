from pathlib import Path

import pytest

from opc.config import load_project_config
from opc.project_types import (
    EnvironmentCheckDefinition,
    ProjectCommandDefinition,
    ProjectTypeDefinition,
    ProjectTypeRegistry,
    TemplateProviderDefinition,
    load_project_type_registry,
)


def test_project_type_definition_expresses_qt_widgets_cmake() -> None:
    qt = ProjectTypeDefinition(
        id="qt",
        display_name="Qt Widgets",
        template_provider=TemplateProviderDefinition(
            template_id="widgets-cmake",
            kind="filesystem",
            path="templates/qt/widgets-cmake",
            variables=("project_name", "class_name"),
            file_patterns=("CMakeLists.txt", "src/*.cpp", "src/*.h"),
        ),
        env_checks=(
            EnvironmentCheckDefinition(id="qt5", description="Qt 5.14.2 SDK is available"),
            EnvironmentCheckDefinition(id="cmake", description="CMake is available"),
        ),
        build_commands=(
            ProjectCommandDefinition(
                id="cmake-configure",
                command=("cmake", "-S", ".", "-B", "build"),
                description="Configure the CMake build directory",
            ),
        ),
        acceptance_checks=(
            ProjectCommandDefinition(
                id="cmake-build",
                command=("cmake", "--build", "build"),
                description="Build the generated Qt project",
            ),
        ),
        permissions=("read", "write", "execute"),
        source="plugin",
        plugin_id="qt",
    )

    assert qt.id == "qt"
    assert qt.template_provider.template_id == "widgets-cmake"
    assert [check.id for check in qt.env_checks] == ["qt5", "cmake"]
    assert qt.build_commands[0].command == ("cmake", "-S", ".", "-B", "build")
    assert qt.permissions == ("read", "write", "execute")


def test_project_type_definition_is_not_qt_specific() -> None:
    python_app = ProjectTypeDefinition(
        id="python-cli",
        display_name="Python CLI",
        template_provider=TemplateProviderDefinition(
            template_id="python-basic",
            kind="plugin",
            path="examples/opc_plugins/sample_project_type/templates/python-basic",
        ),
        env_checks=(EnvironmentCheckDefinition(id="python", description="Python runtime is available"),),
        build_commands=(
            ProjectCommandDefinition(
                id="pytest",
                command=("python", "-m", "pytest"),
                description="Run Python tests",
                required=False,
            ),
        ),
        permissions=("read", "write"),
        source="plugin",
        plugin_id="sample_project_type",
    )

    registry = ProjectTypeRegistry((python_app,))

    assert registry.get("python-cli") == python_app
    assert registry.list() == (python_app,)


def test_registry_rejects_duplicate_project_type_ids() -> None:
    definition = ProjectTypeDefinition(
        id="sample",
        display_name="Sample",
        template_provider=TemplateProviderDefinition(
            template_id="sample-template",
            kind="filesystem",
            path="templates/sample",
        ),
    )
    registry = ProjectTypeRegistry((definition,))

    with pytest.raises(ValueError, match="duplicate project type id"):
        registry.register(definition)


def test_project_type_validation_rejects_invalid_ids_and_permissions() -> None:
    with pytest.raises(ValueError, match="invalid project type id"):
        ProjectTypeDefinition(
            id="Qt Widgets",
            display_name="Qt Widgets",
            template_provider=TemplateProviderDefinition(
                template_id="widgets-cmake",
                kind="filesystem",
                path="templates/qt/widgets-cmake",
            ),
        )

    with pytest.raises(ValueError, match="invalid project type permissions"):
        ProjectTypeDefinition(
            id="qt",
            display_name="Qt Widgets",
            template_provider=TemplateProviderDefinition(
                template_id="widgets-cmake",
                kind="filesystem",
                path="templates/qt/widgets-cmake",
            ),
            permissions=("read", "network"),
        )


def test_project_type_registry_skips_disabled_plugins(tmp_path: Path) -> None:
    _write_qt_manifest(tmp_path)
    _write_opc_toml(tmp_path, enabled_plugins=[])
    config = load_project_config(tmp_path)

    registry = load_project_type_registry(tmp_path, config.plugins.enabled, config.plugins.settings)

    assert registry.list() == ()


def test_project_type_registry_loads_enabled_plugin_manifest(tmp_path: Path) -> None:
    _write_qt_manifest(tmp_path)
    _write_opc_toml(tmp_path, enabled_plugins=["qt"])
    config = load_project_config(tmp_path)

    registry = load_project_type_registry(tmp_path, config.plugins.enabled, config.plugins.settings)
    qt = registry.get("qt")

    assert qt is not None
    assert qt.display_name == "Qt Widgets"
    assert qt.source == "plugin"
    assert qt.plugin_id == "qt"
    assert qt.template_provider.path == "templates/qt/widgets-cmake"


def test_project_type_registry_rejects_duplicate_manifest_ids(tmp_path: Path) -> None:
    _write_qt_manifest(tmp_path)
    _write_opc_toml(tmp_path, enabled_plugins=["qt"])
    config = load_project_config(tmp_path)
    builtin_qt = ProjectTypeDefinition(
        id="qt",
        display_name="Built-in Qt",
        template_provider=TemplateProviderDefinition(
            template_id="builtin-qt",
            kind="filesystem",
            path="templates/builtin-qt",
        ),
    )

    with pytest.raises(ValueError, match="duplicate project type id: qt"):
        load_project_type_registry(
            tmp_path,
            config.plugins.enabled,
            config.plugins.settings,
            builtin_definitions=(builtin_qt,),
        )


def test_project_type_registry_rejects_invalid_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins" / "qt" / "opc-plugin.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """
[[project_type]]
id = "qt"
display_name = "Qt Widgets"
""".strip(),
        encoding="utf-8",
    )
    _write_opc_toml(tmp_path, enabled_plugins=["qt"])
    config = load_project_config(tmp_path)

    with pytest.raises(ValueError, match="project_type.template_provider is required"):
        load_project_type_registry(tmp_path, config.plugins.enabled, config.plugins.settings)


def _write_opc_toml(tmp_path: Path, enabled_plugins: list[str]) -> None:
    enabled = ", ".join(f'"{plugin}"' for plugin in enabled_plugins)
    (tmp_path / "opc.toml").write_text(
        f"""
[plugins]
enabled = [{enabled}]

[plugins.qt]
manifest_path = "plugins/qt/opc-plugin.toml"
""".strip(),
        encoding="utf-8",
    )


def _write_qt_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins" / "qt" / "opc-plugin.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """
[[project_type]]
id = "qt"
display_name = "Qt Widgets"
permissions = ["read", "write", "execute"]

[project_type.template_provider]
template_id = "widgets-cmake"
kind = "filesystem"
path = "templates/qt/widgets-cmake"
variables = ["project_name"]
file_patterns = ["CMakeLists.txt", "src/*.cpp", "src/*.h"]

[[project_type.env_checks]]
id = "qt5"
description = "Qt 5.14.2 SDK is available"

[[project_type.env_checks]]
id = "cmake"
description = "CMake is available"

[[project_type.build_commands]]
id = "cmake-configure"
command = ["cmake", "-S", ".", "-B", "build"]
description = "Configure CMake"

[[project_type.acceptance_checks]]
id = "cmake-build"
command = ["cmake", "--build", "build"]
description = "Build generated project"
""".strip(),
        encoding="utf-8",
    )
