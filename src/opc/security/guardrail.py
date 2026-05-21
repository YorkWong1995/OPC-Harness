from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .command_whitelist import match_dangerous_params
from ..tools.tool_registry import ToolDefinition, ToolPermission

GuardrailAction = Literal["allow", "deny", "approval", "audit", "stop"]
DangerousCommandPolicy = Literal["deny", "approval", "audit"]
PermissionProfileName = Literal["read-only", "write", "execute", "dangerous"]

EXTERNAL_IMPACT_PATTERNS = [
    "git push",
    "gh pr create",
    "gh issue create",
    "npm publish",
    "npm unpublish",
    "twine upload",
]

PROFILE_PERMISSIONS: dict[PermissionProfileName, set[ToolPermission]] = {
    "read-only": {"read"},
    "write": {"read", "write"},
    "execute": {"read", "write", "execute"},
    "dangerous": {"read", "write", "execute"},
}


@dataclass(frozen=True)
class GuardrailDecision:
    action: GuardrailAction
    reason: str = ""
    matched_patterns: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.action in {"allow", "audit"}

    @property
    def stops_workflow(self) -> bool:
        return self.action == "stop"


@dataclass(frozen=True)
class GuardrailPolicy:
    profile: PermissionProfileName = "execute"
    dangerous_command_policy: DangerousCommandPolicy = "deny"

    def allowed_permissions(self) -> set[ToolPermission]:
        return PROFILE_PERMISSIONS[self.profile]

    def check_tool(self, definition: ToolDefinition, inputs: dict) -> GuardrailDecision:
        if definition.timeout <= 0:
            return GuardrailDecision("stop", "tool timeout must be positive")

        if definition.permission not in self.allowed_permissions():
            return GuardrailDecision("deny", f"profile {self.profile} 不允许 {definition.permission} 工具")

        if definition.side_effect in {"filesystem_write", "process"} and self.profile == "read-only":
            return GuardrailDecision("deny", f"profile {self.profile} 不允许 {definition.side_effect} side effect")

        if definition.name == "run_command":
            command = str(inputs.get("command", ""))
            lowered = command.lower()
            cmd_name = command.strip().split(maxsplit=1)[0].lower() if command.strip() else ""
            external_matches = [pattern for pattern in EXTERNAL_IMPACT_PATTERNS if pattern in lowered]
            if external_matches:
                return GuardrailDecision("approval", "external impact action requires approval", external_matches)
            matched = match_dangerous_params(cmd_name, command)
            if matched:
                if self.dangerous_command_policy == "audit":
                    return GuardrailDecision("audit", "dangerous command audited", matched)
                if self.dangerous_command_policy == "approval":
                    return GuardrailDecision("approval", "dangerous command requires approval", matched)
                return GuardrailDecision("deny", "dangerous command denied", matched)

        return GuardrailDecision("allow")


def normalize_permission_profile(value: str | None) -> PermissionProfileName:
    normalized = (value or "execute").strip().lower()
    if normalized not in PROFILE_PERMISSIONS:
        raise ValueError(f"未知权限 profile: {value}")
    return normalized  # type: ignore[return-value]
