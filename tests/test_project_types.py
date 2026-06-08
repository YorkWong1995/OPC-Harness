import pytest

from opc.project_types import (
    EnvironmentCheckDefinition,
    ProjectCommandDefinition,
    ProjectTypeDefinition,
    ProjectTypeRegistry,
    TemplateProviderDefinition,
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
