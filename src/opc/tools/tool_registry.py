"""Tool registration and plugin loading."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

ToolPermission = Literal["read", "write", "execute"]
ToolSideEffect = Literal["none", "filesystem_read", "filesystem_write", "process"]

TEXT_OUTPUT_SCHEMA = {"type": "string"}


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    permission: ToolPermission
    side_effect: ToolSideEffect
    timeout: int
    handler_name: str | None = None
    handler: Callable | None = None

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def to_registry_entry(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "permission": self.permission,
            "side_effect": self.side_effect,
            "timeout": self.timeout,
        }


_TOOL_REGISTRY: dict[str, ToolDefinition] = {}


def register_tool(
    name: str,
    description: str,
    input_schema: dict,
    output_schema: dict | None = None,
    permission: ToolPermission = "read",
    side_effect: ToolSideEffect = "none",
    timeout: int = 300,
    handler_name: str | None = None,
):
    def decorator(func: Callable) -> Callable:
        _TOOL_REGISTRY[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema or TEXT_OUTPUT_SCHEMA,
            permission=permission,
            side_effect=side_effect,
            timeout=timeout,
            handler_name=handler_name,
            handler=func,
        )
        return func

    return decorator


def get_tool(name: str) -> ToolDefinition | None:
    return _TOOL_REGISTRY.get(name)


def get_tool_schema(name: str) -> dict | None:
    definition = get_tool(name)
    return definition.to_schema() if definition else None


def _filter_definitions(
    names: set[str] | None = None,
    permissions: set[ToolPermission] | None = None,
) -> list[ToolDefinition]:
    definitions = list(_TOOL_REGISTRY.values())
    if names is not None:
        definitions = [definition for definition in definitions if definition.name in names]
    if permissions is not None:
        definitions = [definition for definition in definitions if definition.permission in permissions]
    return definitions


def list_tool_schemas(
    names: set[str] | None = None,
    permissions: set[ToolPermission] | None = None,
) -> list[dict]:
    return [definition.to_schema() for definition in _filter_definitions(names, permissions)]


def list_tool_definitions(
    names: set[str] | None = None,
    permissions: set[ToolPermission] | None = None,
) -> list[dict]:
    return [definition.to_registry_entry() for definition in _filter_definitions(names, permissions)]


def register_builtin_tools(agent_cls: type) -> None:
    for definition in BUILTIN_TOOLS:
        if definition.name not in _TOOL_REGISTRY:
            _TOOL_REGISTRY[definition.name] = definition


def load_plugin_tools(project_dir: Path | None = None, plugins_dir: Path | None = None) -> list[Path]:
    root = plugins_dir or ((project_dir / "opc_plugins") if project_dir else Path.cwd() / "opc_plugins")
    if not root.exists() or not root.is_dir():
        return []

    loaded: list[Path] = []
    for module_path in sorted(root.glob("*.py")):
        if module_path.name.startswith("_"):
            continue
        module_name = f"opc_plugins.{module_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loaded.append(module_path)
    return loaded


BUILTIN_TOOLS = [
    ToolDefinition(
        name="read_file",
        description="读取项目中的文件内容",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "相对于项目根目录的文件路径"}},
            "required": ["path"],
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="read",
        side_effect="filesystem_read",
        timeout=30,
        handler_name="_tool_read_file",
    ),
    ToolDefinition(
        name="write_file",
        description="创建或修改项目中的文件（完整覆盖）",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对于项目根目录的文件路径"},
                "content": {"type": "string", "description": "要写入的文件内容"},
            },
            "required": ["path", "content"],
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="write",
        side_effect="filesystem_write",
        timeout=30,
        handler_name="_tool_write_file",
    ),
    ToolDefinition(
        name="edit_file",
        description="编辑文件：用 new_string 替换 old_string（diff 模式，节省 token）。优先使用此工具而非 write_file。",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对于项目根目录的文件路径"},
                "old_string": {"type": "string", "description": "要替换的原始字符串（必须在文件中存在）"},
                "new_string": {"type": "string", "description": "替换后的新字符串"},
                "replace_all": {"type": "boolean", "description": "是否替换所有匹配项（默认 false，只替换第一个）", "default": False},
            },
            "required": ["path", "old_string", "new_string"],
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="write",
        side_effect="filesystem_write",
        timeout=30,
        handler_name="_tool_edit_file",
    ),
    ToolDefinition(
        name="list_files",
        description="列出项目中的文件",
        input_schema={
            "type": "object",
            "properties": {"pattern": {"type": "string", "description": "glob 模式，默认 **/*", "default": "**/*"}},
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="read",
        side_effect="filesystem_read",
        timeout=30,
        handler_name="_tool_list_files",
    ),
    ToolDefinition(
        name="grep",
        description="搜索文件内容：支持正则表达式，优先使用 ripgrep（快速），回退到 Python re",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "正则表达式搜索模式"},
                "file_glob": {"type": "string", "description": "文件过滤 glob 模式，默认 **/*", "default": "**/*"},
                "case_sensitive": {"type": "boolean", "description": "是否区分大小写，默认 true", "default": True},
                "limit": {"type": "integer", "description": "最大返回结果数，默认 200", "default": 200},
            },
            "required": ["pattern"],
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="read",
        side_effect="filesystem_read",
        timeout=30,
        handler_name="_tool_grep",
    ),
    ToolDefinition(
        name="search_knowledge",
        description="查询项目知识库，返回与问题相关的文档或代码片段及来源位置。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要检索的问题或关键词"},
                "top_k": {"type": "integer", "description": "返回结果数，默认 5", "default": 5},
                "index_name": {"type": "string", "description": "可选索引名称；默认使用当前项目目录名"},
            },
            "required": ["query"],
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="read",
        side_effect="filesystem_read",
        timeout=60,
        handler_name="_tool_search_knowledge",
    ),
    ToolDefinition(
        name="git_status",
        description="查看当前项目 Git 工作区状态。",
        input_schema={
            "type": "object",
            "properties": {
                "porcelain": {"type": "boolean", "description": "是否使用短格式输出，默认 true", "default": True},
            },
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="read",
        side_effect="filesystem_read",
        timeout=30,
        handler_name="_tool_git_status",
    ),
    ToolDefinition(
        name="git_diff",
        description="查看当前项目 Git diff，可选择 staged diff 或指定相对路径。",
        input_schema={
            "type": "object",
            "properties": {
                "cached": {"type": "boolean", "description": "是否查看暂存区 diff，默认 false", "default": False},
                "path": {"type": "string", "description": "可选的项目内相对路径"},
            },
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="read",
        side_effect="filesystem_read",
        timeout=30,
        handler_name="_tool_git_diff",
    ),
    ToolDefinition(
        name="git_log",
        description="查看当前项目最近 Git 提交记录。",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "最多返回多少条提交，默认 5", "default": 5},
            },
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="read",
        side_effect="filesystem_read",
        timeout=30,
        handler_name="_tool_git_log",
    ),
    ToolDefinition(
        name="run_command",
        description="在项目目录中执行终端命令（仅限白名单命令：python, pip, npm, node, git, pytest, eslint, npx, cargo, go）。支持交互式命令检测。",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "timeout": {"type": "integer", "description": "超时时间（秒），默认 300", "default": 300},
            },
            "required": ["command"],
        },
        output_schema=TEXT_OUTPUT_SCHEMA,
        permission="execute",
        side_effect="process",
        timeout=300,
        handler_name="_tool_run_command",
    ),
]

for builtin_tool in BUILTIN_TOOLS:
    _TOOL_REGISTRY[builtin_tool.name] = builtin_tool
