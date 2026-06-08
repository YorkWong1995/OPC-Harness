"""OPC 项目级配置读取。

配置优先级（从低到高）：
1. 默认配置（dataclass 默认值）
2. opc.toml 文件
3. 环境变量（OPC_ 前缀）
4. CLI 参数（通过 cli_overrides 传入）
5. 运行时覆盖（通过 runtime_overrides 传入）
"""

from dataclasses import dataclass, field
from pathlib import Path
import os

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

OPTIONAL_ROLES = {"ceo", "architect", "ops", "growth", "all"}
ALL_OPTIONAL_ROLES = {"ceo", "architect", "ops", "growth"}


@dataclass
class ConfigIssue:
    level: str
    message: str
    location: str


@dataclass
class WorkflowConfig:
    roles: set[str] = field(default_factory=lambda: {"architect"})
    ceo_review: bool = False
    auto_confirm: bool = False
    profile: str = "default"
    max_rework_attempts: int = 1
    max_rounds: int = 12


@dataclass
class ModelConfig:
    default: str = "claude-sonnet-4-6"
    fallback: str = ""
    temperature: float = 0.0
    max_tokens: int = 4096


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
    estimate_enabled: bool = False
    currency: str = "USD"
    pricing_source: str = "opc.toml"
    model_prices: dict[str, dict[str, float]] = field(default_factory=dict)
    # 硬限制：超过即抛出 _StopWorkflow 中止；为 0 表示不启用
    workflow_token_hard_limit: int = 0
    role_token_hard_limit: int = 0
    enforce_hard_limit: bool = True


@dataclass
class SecurityConfig:
    workspace_boundary: bool = True
    command_whitelist: list[str] = field(default_factory=lambda: [
        "python", "pip", "npm", "node", "git", "pytest", "eslint", "npx",
        "cargo", "go", "gcc", "g++", "cmake", "make",
    ])
    audit_dangerous_commands: bool = True
    block_env_file_write: bool = True
    permission_profile: str = "execute"
    dangerous_command_policy: str = "deny"


@dataclass
class MemoryConfig:
    enable_rag: bool = True
    max_context_tokens: int = 2000
    strict_ingestion: bool = True
    embedding_model: str = "minilm"


@dataclass
class PluginConfig:
    enabled: tuple[str, ...] = ()
    settings: dict[str, dict[str, object]] = field(default_factory=dict)


@dataclass
class OPCConfig:
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)


def validate_project_config(project_dir: Path, profile: str | None = None) -> list[ConfigIssue]:
    config_path = project_dir.resolve() / "opc.toml"
    if not config_path.exists():
        return [ConfigIssue("error", "未找到 opc.toml", str(config_path))]

    issues: list[ConfigIssue] = []
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [ConfigIssue("error", f"TOML 解析失败: {exc}", str(config_path))]

    workflow = data.get("workflow", {})
    active_profile = profile or workflow.get("profile", "default")
    profiles = data.get("profile", {})
    if active_profile != "default" and active_profile not in profiles:
        issues.append(ConfigIssue("error", f"未知 profile: {active_profile}", "workflow.profile"))

    _collect_role_issues(set(str(role).strip().lower() for role in workflow.get("roles", []) if str(role).strip()), "workflow.roles", issues)
    _collect_role_issues({str(role).strip().lower() for role in data.get("roles", {})}, "roles", issues)

    for profile_name, profile_data in profiles.items():
        if not isinstance(profile_data, dict):
            issues.append(ConfigIssue("error", f"profile 必须是表: {profile_name}", f"profile.{profile_name}"))
            continue
        profile_workflow = profile_data.get("workflow", {})
        profile_roles = profile_data.get("roles", {})
        _collect_role_issues(set(str(role).strip().lower() for role in profile_workflow.get("roles", []) if str(role).strip()), f"profile.{profile_name}.workflow.roles", issues)
        _collect_role_issues({str(role).strip().lower() for role in profile_roles}, f"profile.{profile_name}.roles", issues)

    if not issues:
        try:
            load_project_config(project_dir, profile=profile)
        except (TypeError, ValueError) as exc:
            issues.append(ConfigIssue("error", str(exc), str(config_path)))

    return issues


def _collect_role_issues(roles: set[str], location: str, issues: list[ConfigIssue]) -> None:
    unknown = roles - OPTIONAL_ROLES
    if unknown:
        allowed = ", ".join(sorted(OPTIONAL_ROLES))
        invalid = ", ".join(sorted(unknown))
        issues.append(ConfigIssue("error", f"未知 OPC 角色：{invalid}。允许的角色：{allowed}", location))


def load_project_config(
    project_dir: Path,
    profile: str | None = None,
    cli_overrides: dict | None = None,
    runtime_overrides: dict | None = None,
) -> OPCConfig:
    config_path = project_dir.resolve() / "opc.toml"
    if not config_path.exists():
        config = OPCConfig(workflow=load_workflow_config(project_dir, profile))
    else:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        workflow_config = load_workflow_config(project_dir, profile)
        tools = data.get("tools", {})
        cost = data.get("cost", {})
        model = data.get("model", {})
        security = data.get("security", {})
        memory = data.get("memory", {})
        plugins = data.get("plugins", {})
        config = OPCConfig(
            workflow=workflow_config,
            model=ModelConfig(
                default=str(model.get("default", "claude-sonnet-4-6")),
                fallback=str(model.get("fallback", "")),
                temperature=float(model.get("temperature", 0.0)),
                max_tokens=int(model.get("max_tokens", 4096)),
            ),
            tools=ToolConfig(
                max_retries=int(tools.get("max_retries", 1)),
                default_timeout_seconds=int(tools.get("default_timeout_seconds", 300)),
            ),
            cost=CostConfig(
                workflow_token_limit=int(cost.get("workflow_token_limit", 200_000)),
                role_token_limit=int(cost.get("role_token_limit", 50_000)),
                role_call_limit=int(cost.get("role_call_limit", 10)),
                api_calls_per_minute=int(cost.get("api_calls_per_minute", 30)),
                estimate_enabled=bool(cost.get("estimate_enabled", False)),
                currency=str(cost.get("currency", "USD")),
                pricing_source=str(cost.get("pricing_source", "opc.toml")),
                model_prices=_normalize_model_prices(cost.get("model_prices", {})),
                workflow_token_hard_limit=int(cost.get("workflow_token_hard_limit", 0)),
                role_token_hard_limit=int(cost.get("role_token_hard_limit", 0)),
                enforce_hard_limit=bool(cost.get("enforce_hard_limit", True)),
            ),
            security=SecurityConfig(
                workspace_boundary=bool(security.get("workspace_boundary", True)),
                command_whitelist=security.get("command_whitelist", SecurityConfig().command_whitelist),
                audit_dangerous_commands=bool(security.get("audit_dangerous_commands", True)),
                block_env_file_write=bool(security.get("block_env_file_write", True)),
                permission_profile=str(security.get("permission_profile", "execute")),
                dangerous_command_policy=str(security.get("dangerous_command_policy", "deny")),
            ),
            memory=MemoryConfig(
                enable_rag=bool(memory.get("enable_rag", True)),
                max_context_tokens=int(memory.get("max_context_tokens", 2000)),
                strict_ingestion=bool(memory.get("strict_ingestion", True)),
                embedding_model=str(memory.get("embedding_model", "minilm")),
            ),
            plugins=_normalize_plugin_config(plugins),
        )

    _apply_env_overrides(config)
    _apply_dict_overrides(config, cli_overrides)
    _apply_dict_overrides(config, runtime_overrides)
    return config


def _normalize_model_prices(raw_prices: object) -> dict[str, dict[str, float]]:
    if not isinstance(raw_prices, dict):
        raise TypeError("cost.model_prices 必须是 TOML 表")

    model_prices: dict[str, dict[str, float]] = {}
    for model, prices in raw_prices.items():
        if not isinstance(prices, dict):
            raise TypeError(f"cost.model_prices.{model} 必须是 TOML 表")
        model_prices[str(model)] = {
            "input_per_million": float(prices.get("input_per_million", 0.0)),
            "output_per_million": float(prices.get("output_per_million", 0.0)),
        }
    return model_prices


def _normalize_plugin_config(raw_plugins: object) -> PluginConfig:
    if not isinstance(raw_plugins, dict):
        raise TypeError("plugins 必须是 TOML 表")
    enabled = tuple(str(plugin).strip() for plugin in raw_plugins.get("enabled", []) if str(plugin).strip())
    settings: dict[str, dict[str, object]] = {}
    for plugin_id, plugin_data in raw_plugins.items():
        if plugin_id == "enabled":
            continue
        if not isinstance(plugin_data, dict):
            raise TypeError(f"plugins.{plugin_id} 必须是 TOML 表")
        settings[str(plugin_id)] = dict(plugin_data)
    return PluginConfig(enabled=enabled, settings=settings)


def _parse_plugin_list(raw_value: str) -> tuple[str, ...]:
    return tuple(plugin.strip() for plugin in raw_value.split(",") if plugin.strip())


def _apply_env_overrides(config: OPCConfig) -> None:
    if val := os.environ.get("OPC_MAX_REWORK_ATTEMPTS"):
        config.workflow.max_rework_attempts = int(val)
    if val := os.environ.get("OPC_MAX_ROUNDS"):
        config.workflow.max_rounds = int(val)
    if val := os.environ.get("OPC_AUTO_CONFIRM"):
        config.workflow.auto_confirm = val.lower() in ("1", "true", "yes")
    if val := os.environ.get("OPC_WORKFLOW_TOKEN_LIMIT"):
        config.cost.workflow_token_limit = int(val)
    if val := os.environ.get("OPC_ROLE_TOKEN_LIMIT"):
        config.cost.role_token_limit = int(val)
    if val := os.environ.get("OPC_ROLE_CALL_LIMIT"):
        config.cost.role_call_limit = int(val)
    if val := os.environ.get("OPC_API_CALLS_PER_MINUTE"):
        config.cost.api_calls_per_minute = int(val)
    if val := os.environ.get("OPC_COST_ESTIMATE_ENABLED"):
        config.cost.estimate_enabled = val.lower() in ("1", "true", "yes")
    if val := os.environ.get("OPC_COST_CURRENCY"):
        config.cost.currency = val
    if val := os.environ.get("OPC_COST_PRICING_SOURCE"):
        config.cost.pricing_source = val
    if val := os.environ.get("OPC_WORKFLOW_TOKEN_HARD_LIMIT"):
        config.cost.workflow_token_hard_limit = int(val)
    if val := os.environ.get("OPC_ROLE_TOKEN_HARD_LIMIT"):
        config.cost.role_token_hard_limit = int(val)
    if val := os.environ.get("OPC_ENFORCE_HARD_LIMIT"):
        config.cost.enforce_hard_limit = val.lower() in ("1", "true", "yes")
    if val := os.environ.get("OPC_EMBEDDING_MODEL"):
        config.memory.embedding_model = val
    if val := os.environ.get("OPC_TOOL_MAX_RETRIES"):
        config.tools.max_retries = int(val)
    if val := os.environ.get("OPC_TOOL_TIMEOUT"):
        config.tools.default_timeout_seconds = int(val)
    if val := os.environ.get("OPC_PERMISSION_PROFILE"):
        config.security.permission_profile = val
    if val := os.environ.get("OPC_DANGEROUS_COMMAND_POLICY"):
        config.security.dangerous_command_policy = val
    if val := os.environ.get("OPC_PLUGINS_ENABLED"):
        config.plugins.enabled = _parse_plugin_list(val)


def _apply_dict_overrides(config: OPCConfig, overrides: dict | None) -> None:
    if not overrides:
        return
    if "max_rework_attempts" in overrides:
        config.workflow.max_rework_attempts = int(overrides["max_rework_attempts"])
    if "max_rounds" in overrides:
        config.workflow.max_rounds = int(overrides["max_rounds"])
    if "auto_confirm" in overrides:
        config.workflow.auto_confirm = bool(overrides["auto_confirm"])
    if "workflow_token_limit" in overrides:
        config.cost.workflow_token_limit = int(overrides["workflow_token_limit"])
    if "role_token_limit" in overrides:
        config.cost.role_token_limit = int(overrides["role_token_limit"])
    if "role_call_limit" in overrides:
        config.cost.role_call_limit = int(overrides["role_call_limit"])
    if "api_calls_per_minute" in overrides:
        config.cost.api_calls_per_minute = int(overrides["api_calls_per_minute"])
    if "cost_estimate_enabled" in overrides:
        config.cost.estimate_enabled = bool(overrides["cost_estimate_enabled"])
    if "cost_currency" in overrides:
        config.cost.currency = str(overrides["cost_currency"])
    if "cost_pricing_source" in overrides:
        config.cost.pricing_source = str(overrides["cost_pricing_source"])
    if "cost_model_prices" in overrides:
        config.cost.model_prices = _normalize_model_prices(overrides["cost_model_prices"])
    if "workflow_token_hard_limit" in overrides:
        config.cost.workflow_token_hard_limit = int(overrides["workflow_token_hard_limit"])
    if "role_token_hard_limit" in overrides:
        config.cost.role_token_hard_limit = int(overrides["role_token_hard_limit"])
    if "enforce_hard_limit" in overrides:
        config.cost.enforce_hard_limit = bool(overrides["enforce_hard_limit"])
    if "embedding_model" in overrides:
        config.memory.embedding_model = str(overrides["embedding_model"])
    if "tool_max_retries" in overrides:
        config.tools.max_retries = int(overrides["tool_max_retries"])
    if "tool_timeout" in overrides:
        config.tools.default_timeout_seconds = int(overrides["tool_timeout"])
    if "permission_profile" in overrides:
        config.security.permission_profile = str(overrides["permission_profile"])
    if "dangerous_command_policy" in overrides:
        config.security.dangerous_command_policy = str(overrides["dangerous_command_policy"])
    if "plugins_enabled" in overrides:
        config.plugins.enabled = tuple(str(plugin).strip() for plugin in overrides["plugins_enabled"] if str(plugin).strip())


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
