"""测试工具注册协议。"""

from opc.agent import TOOLS_READ_WRITE
from opc.tools import list_tool_definitions


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
