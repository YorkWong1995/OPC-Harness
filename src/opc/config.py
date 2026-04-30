"""OPC 项目级配置读取。"""

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

OPTIONAL_ROLES = {"ceo", "architect", "ops", "growth", "all"}
ALL_OPTIONAL_ROLES = {"ceo", "architect", "ops", "growth"}


@dataclass
class WorkflowConfig:
    roles: set[str] = field(default_factory=lambda: {"architect"})
    ceo_review: bool = False
    auto_confirm: bool = False


def load_workflow_config(project_dir: Path) -> WorkflowConfig:
    """读取目标项目根目录的 opc.toml。"""
    config_path = project_dir.resolve() / "opc.toml"
    if not config_path.exists():
        return WorkflowConfig()

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    workflow = data.get("workflow", {})
    role_flags = data.get("roles", {})

    roles = set()
    for role in workflow.get("roles", []):
        normalized = str(role).strip().lower()
        if normalized:
            roles.add(normalized)

    for role, enabled in role_flags.items():
        normalized = str(role).strip().lower()
        if bool(enabled):
            roles.add(normalized)
        else:
            roles.discard(normalized)

    # 允许空角色集，实现真正的简化工作流
    # 如果用户明确配置为空，则不添加默认角色
    if not roles:
        roles = set()

    _validate_roles(roles)

    if "all" in roles:
        roles = set(ALL_OPTIONAL_ROLES)

    return WorkflowConfig(
        roles=roles,
        ceo_review=bool(workflow.get("ceo_review", False)),
        auto_confirm=bool(workflow.get("auto_confirm", False)),
    )


def normalize_roles(roles: set[str]) -> set[str]:
    """展开 all 并校验角色集合。"""
    normalized = {str(role).strip().lower() for role in roles if str(role).strip()}
    _validate_roles(normalized)
    if "all" in normalized:
        return set(ALL_OPTIONAL_ROLES)
    return normalized


def _validate_roles(roles: set[str]) -> None:
    unknown = roles - OPTIONAL_ROLES
    if unknown:
        allowed = ", ".join(sorted(OPTIONAL_ROLES))
        invalid = ", ".join(sorted(unknown))
        raise ValueError(f"未知 OPC 角色：{invalid}。允许的角色：{allowed}")
