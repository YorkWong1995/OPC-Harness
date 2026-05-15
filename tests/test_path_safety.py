"""测试 _resolve_safe_path 路径穿越保护，特别是兄弟目录前缀误匹配场景。"""

from pathlib import Path

import pytest

from opc.agent import Agent


def test_resolve_safe_path_rejects_parent_traversal(tmp_path: Path):
    agent = Agent(role="test", system_prompt="test", project_dir=tmp_path)
    with pytest.raises(ValueError, match="路径穿越"):
        agent._resolve_safe_path("../outside.txt")


def test_resolve_safe_path_rejects_sibling_with_shared_prefix(tmp_path: Path):
    """关键回归用例：projectX 不能因前缀 'proj' 匹配 'proj' 目录而通过。

    旧实现用 str.startswith 时，/home/user/projectX 会被 /home/user/proj 接受。
    is_relative_to 不会被前缀骗到。
    """
    base = tmp_path / "proj"
    base.mkdir()
    sibling = tmp_path / "projectX"
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret", encoding="utf-8")

    agent = Agent(role="test", system_prompt="test", project_dir=base)

    # 通过相对路径构造一个会指向兄弟目录的解析结果
    with pytest.raises(ValueError, match="路径穿越"):
        agent._resolve_safe_path("../projectX/secret.txt")


def test_resolve_safe_path_accepts_inside_path(tmp_path: Path):
    agent = Agent(role="test", system_prompt="test", project_dir=tmp_path)
    target = agent._resolve_safe_path("a/b/c.txt")
    assert str(target).startswith(str(tmp_path.resolve()))
