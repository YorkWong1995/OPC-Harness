"""Project type definitions and in-memory registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
import re

from .tools.tool_registry import ToolPermission

ProjectTypeSource = Literal["builtin", "plugin"]
TemplateProviderKind = Literal["filesystem", "package", "plugin"]

_PROJECT_TYPE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


@dataclass(frozen=True)
class TemplateProviderDefinition:
    template_id: str
    kind: TemplateProviderKind
    path: str
    variables: tuple[str, ...] = ()
    file_patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.template_id, "template_id")
        if not self.path.strip():
            raise ValueError("template provider path is required")
        object.__setattr__(self, "variables", tuple(self.variables))
        object.__setattr__(self, "file_patterns", tuple(self.file_patterns))


@dataclass(frozen=True)
class EnvironmentCheckDefinition:
    id: str
    description: str
    command: str | None = None
    required: bool = True

    def __post_init__(self) -> None:
        _validate_identifier(self.id, "env check id")
        if not self.description.strip():
            raise ValueError("env check description is required")


@dataclass(frozen=True)
class ProjectCommandDefinition:
    id: str
    command: tuple[str, ...]
    description: str
    required: bool = True

    def __post_init__(self) -> None:
        _validate_identifier(self.id, "command id")
        if not self.command:
            raise ValueError("command is required")
        if not self.description.strip():
            raise ValueError("command description is required")
        object.__setattr__(self, "command", tuple(self.command))


@dataclass(frozen=True)
class ProjectTypeDefinition:
    id: str
    display_name: str
    template_provider: TemplateProviderDefinition
    env_checks: tuple[EnvironmentCheckDefinition, ...] = ()
    build_commands: tuple[ProjectCommandDefinition, ...] = ()
    acceptance_checks: tuple[ProjectCommandDefinition, ...] = ()
    permissions: tuple[ToolPermission, ...] = ("read",)
    source: ProjectTypeSource = "builtin"
    plugin_id: str | None = None
    enabled_by_default: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.id, "project type id")
        if not self.display_name.strip():
            raise ValueError("project type display_name is required")
        if self.source == "plugin" and not self.plugin_id:
            raise ValueError("plugin project type requires plugin_id")
        invalid_permissions = set(self.permissions) - {"read", "write", "execute"}
        if invalid_permissions:
            invalid = ", ".join(sorted(invalid_permissions))
            raise ValueError(f"invalid project type permissions: {invalid}")
        object.__setattr__(self, "env_checks", tuple(self.env_checks))
        object.__setattr__(self, "build_commands", tuple(self.build_commands))
        object.__setattr__(self, "acceptance_checks", tuple(self.acceptance_checks))
        object.__setattr__(self, "permissions", tuple(dict.fromkeys(self.permissions)))


class ProjectTypeRegistry:
    def __init__(self, definitions: tuple[ProjectTypeDefinition, ...] | None = None) -> None:
        self._definitions: dict[str, ProjectTypeDefinition] = {}
        for definition in definitions or ():
            self.register(definition)

    def register(self, definition: ProjectTypeDefinition) -> None:
        if definition.id in self._definitions:
            raise ValueError(f"duplicate project type id: {definition.id}")
        self._definitions[definition.id] = definition

    def get(self, project_type_id: str) -> ProjectTypeDefinition | None:
        return self._definitions.get(project_type_id)

    def list(self) -> tuple[ProjectTypeDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))


DEFAULT_PROJECT_TYPE_REGISTRY = ProjectTypeRegistry()


def _validate_identifier(value: str, field_name: str) -> None:
    if not _PROJECT_TYPE_ID_RE.fullmatch(value):
        raise ValueError(f"invalid {field_name}: {value}")
