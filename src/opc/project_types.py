"""Project type definitions and in-memory registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

from .tools.tool_registry import ToolPermission

ProjectTypeSource = Literal["builtin", "plugin"]
TemplateProviderKind = Literal["filesystem", "package", "plugin"]

_PROJECT_TYPE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_DEFAULT_PLUGIN_MANIFEST = "plugins/{plugin_id}/opc-plugin.toml"


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


def load_project_type_registry(
    project_dir: Path,
    enabled_plugins: tuple[str, ...] = (),
    plugin_settings: Mapping[str, Mapping[str, object]] | None = None,
    builtin_definitions: tuple[ProjectTypeDefinition, ...] = (),
) -> ProjectTypeRegistry:
    registry = ProjectTypeRegistry(builtin_definitions)
    settings = plugin_settings or {}
    for plugin_id in sorted(dict.fromkeys(enabled_plugins)):
        _validate_identifier(plugin_id, "plugin id")
        manifest_path = _resolve_manifest_path(project_dir, plugin_id, settings.get(plugin_id, {}))
        for definition in _load_project_type_manifest(plugin_id, manifest_path):
            registry.register(definition)
    return registry


def _resolve_manifest_path(project_dir: Path, plugin_id: str, settings: Mapping[str, object]) -> Path:
    raw_path = str(settings.get("manifest_path") or _DEFAULT_PLUGIN_MANIFEST.format(plugin_id=plugin_id))
    path = Path(raw_path)
    if not path.is_absolute():
        path = project_dir / path
    return path.resolve()


def _load_project_type_manifest(plugin_id: str, manifest_path: Path) -> tuple[ProjectTypeDefinition, ...]:
    if not manifest_path.exists():
        raise ValueError(f"project type manifest not found: {manifest_path}")
    data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    items = data.get("project_type", [])
    if not isinstance(items, list) or not items:
        raise ValueError(f"project type manifest has no project_type entries: {manifest_path}")
    return tuple(_definition_from_manifest_item(plugin_id, item, manifest_path) for item in items)


def _definition_from_manifest_item(
    plugin_id: str,
    item: Mapping[str, object],
    manifest_path: Path,
) -> ProjectTypeDefinition:
    if not isinstance(item, Mapping):
        raise ValueError(f"invalid project_type entry in {manifest_path}")
    template_provider = item.get("template_provider")
    if not isinstance(template_provider, Mapping):
        raise ValueError(f"project_type.template_provider is required in {manifest_path}")
    return ProjectTypeDefinition(
        id=str(item.get("id", "")).strip(),
        display_name=str(item.get("display_name", "")).strip(),
        template_provider=_template_provider_from_manifest(template_provider),
        env_checks=tuple(_env_check_from_manifest(raw) for raw in _manifest_list(item, "env_checks", manifest_path)),
        build_commands=tuple(_command_from_manifest(raw) for raw in _manifest_list(item, "build_commands", manifest_path)),
        acceptance_checks=tuple(_command_from_manifest(raw) for raw in _manifest_list(item, "acceptance_checks", manifest_path)),
        permissions=tuple(str(permission).strip() for permission in item.get("permissions", ["read"])),
        source="plugin",
        plugin_id=plugin_id,
        enabled_by_default=bool(item.get("enabled_by_default", False)),
    )


def _template_provider_from_manifest(raw: Mapping[str, object]) -> TemplateProviderDefinition:
    return TemplateProviderDefinition(
        template_id=str(raw.get("template_id", "")).strip(),
        kind=str(raw.get("kind", "filesystem")).strip(),
        path=str(raw.get("path", "")).strip(),
        variables=tuple(str(value).strip() for value in raw.get("variables", []) if str(value).strip()),
        file_patterns=tuple(str(value).strip() for value in raw.get("file_patterns", []) if str(value).strip()),
    )


def _env_check_from_manifest(raw: Mapping[str, object]) -> EnvironmentCheckDefinition:
    return EnvironmentCheckDefinition(
        id=str(raw.get("id", "")).strip(),
        description=str(raw.get("description", "")).strip(),
        command=str(raw["command"]).strip() if raw.get("command") is not None else None,
        required=bool(raw.get("required", True)),
    )


def _command_from_manifest(raw: Mapping[str, object]) -> ProjectCommandDefinition:
    command = raw.get("command", [])
    if isinstance(command, str):
        command_parts = (command,)
    else:
        command_parts = tuple(str(value).strip() for value in command if str(value).strip())
    return ProjectCommandDefinition(
        id=str(raw.get("id", "")).strip(),
        command=command_parts,
        description=str(raw.get("description", "")).strip(),
        required=bool(raw.get("required", True)),
    )


def _manifest_list(item: Mapping[str, object], key: str, manifest_path: Path) -> tuple[Mapping[str, object], ...]:
    values = item.get(key, [])
    if not isinstance(values, list):
        raise ValueError(f"project_type.{key} must be a list in {manifest_path}")
    if not all(isinstance(value, Mapping) for value in values):
        raise ValueError(f"project_type.{key} entries must be tables in {manifest_path}")
    return tuple(values)


def _validate_identifier(value: str, field_name: str) -> None:
    if not _PROJECT_TYPE_ID_RE.fullmatch(value):
        raise ValueError(f"invalid {field_name}: {value}")
