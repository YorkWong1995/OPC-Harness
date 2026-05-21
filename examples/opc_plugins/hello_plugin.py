from opc.tools.tool_registry import register_tool


@register_tool(
    name="sample_hello",
    description="Return a static hello message from the sample plugin.",
    input_schema={"type": "object", "properties": {}},
    permission="read",
    side_effect="none",
    timeout=5,
)
def sample_hello() -> str:
    return "hello from opc plugin"
