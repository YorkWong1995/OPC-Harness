"""测试工具注册协议。"""

from opc.agent import TOOLS_READ_ONLY, TOOLS_READ_WRITE, Agent
from opc.tools import list_tool_definitions, list_tool_schemas, list_tool_schemas_for_profile


def test_tool_registry_definitions_include_protocol_fields():
    definitions = list_tool_definitions()
    required_fields = {"name", "description", "input_schema", "output_schema", "permission", "side_effect", "timeout"}

    assert definitions
    for definition in definitions:
        assert required_fields <= set(definition)
        assert definition["permission"] in {"read", "write", "execute"}
        assert definition["side_effect"] in {"none", "filesystem_read", "filesystem_write", "process"}
        assert isinstance(definition["timeout"], int)
        assert definition["timeout"] > 0


def test_agent_tool_schemas_expose_only_claude_fields():
    assert TOOLS_READ_WRITE
    for schema in TOOLS_READ_WRITE:
        assert set(schema) == {"name", "description", "input_schema"}


def test_read_only_tools_are_derived_from_permissions():
    read_only_names = {tool["name"] for tool in TOOLS_READ_ONLY}
    registry_read_names = {tool["name"] for tool in list_tool_schemas(permissions={"read"})}
    write_or_execute_names = {
        tool["name"] for tool in list_tool_definitions(permissions={"write", "execute"})
    }

    assert read_only_names == registry_read_names
    assert read_only_names.isdisjoint(write_or_execute_names)


def test_dangerous_params_denied_by_default_in_run_command(tmp_path):
    from pathlib import Path

    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    result = agent._tool_run_command("git push --force origin main")
    assert "[guardrail_blocked]" in result
    assert "push --force" in result


def test_safe_command_has_no_warning(tmp_path):
    from pathlib import Path

    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    result = agent._tool_run_command("python --version")
    assert "[WARNING]" not in result


def test_workspace_boundary_rejects_outside_path(tmp_path):
    import sys
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    if sys.platform == "win32":
        outside_path = "C:\\Windows\\System32\\calc.exe"
    else:
        outside_path = "/etc/passwd"

    result = agent._tool_run_command(f"python {outside_path}")
    assert "workspace" in result


def test_workspace_boundary_allows_relative_path(tmp_path):
    (tmp_path / "hello.py").write_text("print('hi')\n", encoding="utf-8")
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    result = agent._tool_run_command("python hello.py")
    assert "workspace" not in result


def test_dangerous_command_writes_audit_log(tmp_path):
    agent = Agent(role="test", system_prompt="test", tools=TOOLS_READ_WRITE, project_dir=tmp_path)

    agent._tool_run_command("git push --force origin main")

    assert len(agent.audit_log) == 1
    entry = agent.audit_log[0]
    assert entry["event"] == "guardrail_blocked"
    assert "push --force" in entry["matched_patterns"]
    assert entry["role"] == "test"


def test_permission_profiles_filter_tool_visibility():
    read_names = {tool["name"] for tool in list_tool_schemas_for_profile("read-only")}
    write_names = {tool["name"] for tool in list_tool_schemas_for_profile("write")}
    execute_names = {tool["name"] for tool in list_tool_schemas_for_profile("execute")}

    assert "read_file" in read_names
    assert "write_file" not in read_names
    assert "write_file" in write_names
    assert "run_command" not in write_names
    assert "run_command" in execute_names


def test_permission_profile_blocks_disallowed_tool(tmp_path):
    agent = Agent(
        role="test",
        system_prompt="test",
        tools=TOOLS_READ_WRITE,
        project_dir=tmp_path,
        permission_profile="read-only",
    )

    result = agent._execute_tool("write_file", {"path": "x.txt", "content": "x"})
    assert "[guardrail_blocked]" in result
    assert not (tmp_path / "x.txt").exists()


def test_dangerous_command_can_require_approval(tmp_path):
    agent = Agent(
        role="test",
        system_prompt="test",
        tools=TOOLS_READ_WRITE,
        project_dir=tmp_path,
        dangerous_command_policy="approval",
    )

    result = agent._tool_run_command("git push --force origin main")
    assert "[approval_required]" in result
