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
    profile: str = "default"
    max_rework_attempts: int = 1
    max_rounds: int = 12


@dataclass
class ToolConfig:
    max_retries: int = 1
    default_timeout_seconds: int = 300


@dataclass
class CostConfig:
    workflow_token_limit: int = 200_000
    role_token_limit: int = 50_000
    role_call_limit: int = 10
    api_calls_per_minute: int = 30


@dataclass
class OPCConfig:
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    cost: CostConfig = field(default_factory=CostConfig)


def load_project_config(project_dir: Path, profile: str | None = None) -> OPCConfig:
    config_path = project_dir.resolve() / "opc.toml"
    if not config_path.exists():
        return OPCConfig(workflow=load_workflow_config(project_dir, profile))

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    workflow_config = load_workflow_config(project_dir, profile)
    tools = data.get("tools", {})
    cost = data.get("cost", {})
    return OPCConfig(
        workflow=workflow_config,
        tools=ToolConfig(
            max_retries=int(tools.get("max_retries", 1)),
            default_timeout_seconds=int(tools.get("default_timeout_seconds", 300)),
        ),
        cost=CostConfig(
            workflow_token_limit=int(cost.get("workflow_token_limit", 200_000)),
            role_token_limit=int(cost.get("role_token_limit", 50_000)),
            role_call_limit=int(cost.get("role_call_limit", 10)),
            api_calls_per_minute=int(cost.get("api_calls_per_minute", 30)),
        ),
    )


def load_workflow_config(project_dir: Path, profile: str | None = None) -> WorkflowConfig:
    """读取目标项目根目录的 opc.toml。

    Args:
        project_dir: 项目根目录路径。
        profile: 指定使用的 profile 名称，优先于配置文件中的默认值。
    """
    config_path = project_dir.resolve() / "opc.toml"
    if not config_path.exists():
        return WorkflowConfig()

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    workflow = data.get("workflow", {})
    role_flags = data.get("roles", {})

    active_profile = profile or workflow.get("profile", "default")

    profiles = data.get("profile", {})
    if active_profile != "default" and active_profile in profiles:
        profile_data = profiles[active_profile]
        if "workflow" in profile_data:
            workflow = {**workflow, **profile_data["workflow"]}
        if "roles" in profile_data:
            role_flags = {**role_flags, **profile_data["roles"]}

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

    if not roles:
        roles = set()

    _validate_roles(roles)

    if "all" in roles:
        roles = set(ALL_OPTIONAL_ROLES)

    return WorkflowConfig(
        roles=roles,
        ceo_review=bool(workflow.get("ceo_review", False)),
        auto_confirm=bool(workflow.get("auto_confirm", False)),
        profile=active_profile,
        max_rework_attempts=int(workflow.get("max_rework_attempts", 1)),
        max_rounds=int(workflow.get("max_rounds", 12)),
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
