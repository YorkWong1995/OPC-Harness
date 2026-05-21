from opc.security.guardrail import GuardrailPolicy
from opc.tools.tool_registry import ToolDefinition


def _tool(
    name="read_file",
    permission="read",
    side_effect="filesystem_read",
    timeout=30,
):
    return ToolDefinition(
        name=name,
        description="test",
        input_schema={"type": "object"},
        output_schema={"type": "string"},
        permission=permission,
        side_effect=side_effect,
        timeout=timeout,
    )


def test_guardrail_policy_allows_read_by_default():
    decision = GuardrailPolicy(profile="execute").check_tool(_tool(), {})

    assert decision.action == "allow"
    assert decision.allowed


def test_guardrail_policy_denies_disallowed_permission():
    decision = GuardrailPolicy(profile="read-only").check_tool(
        _tool(name="write_file", permission="write", side_effect="filesystem_write"),
        {},
    )

    assert decision.action == "deny"
    assert not decision.allowed


def test_guardrail_policy_audits_dangerous_command_when_configured():
    decision = GuardrailPolicy(profile="execute", dangerous_command_policy="audit").check_tool(
        _tool(name="run_command", permission="execute", side_effect="process"),
        {"command": "git reset --hard HEAD"},
    )

    assert decision.action == "audit"
    assert decision.allowed
    assert "reset --hard" in decision.matched_patterns


def test_guardrail_policy_requires_approval_for_external_impact():
    decision = GuardrailPolicy(profile="execute").check_tool(
        _tool(name="run_command", permission="execute", side_effect="process"),
        {"command": "git push origin main"},
    )

    assert decision.action == "approval"
    assert not decision.allowed
    assert "git push" in decision.matched_patterns


def test_guardrail_policy_stops_invalid_tool_definition():
    decision = GuardrailPolicy(profile="execute").check_tool(_tool(timeout=0), {})

    assert decision.action == "stop"
    assert decision.stops_workflow
