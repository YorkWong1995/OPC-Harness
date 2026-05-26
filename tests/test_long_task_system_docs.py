from pathlib import Path


def test_long_task_system_docs_reference_required_fields():
    root = Path(__file__).resolve().parent.parent
    files = {
        "docs/claude/standards.md": ["id", "depends_on", "read_before_start", "execution", "evidence", "handoff"],
        ".claude/skills/task-spec/SKILL.md": ["id", "depends_on", "read_before_start", "execution", "evidence", "handoff"],
        ".claude/skills/implementation-check/SKILL.md": ["任务字段完整性", "上下文恢复性", "建议进入 QA", "不建议进入 QA"],
        ".claude/skills/acceptance-check/SKILL.md": ["evidence / handoff / 前置读取", "可恢复性结论", "可清空上下文继续", "不可清空上下文继续"],
    }

    for relative, terms in files.items():
        content = (root / relative).read_text(encoding="utf-8")
        for term in terms:
            assert term in content, f"{relative} missing {term}"
