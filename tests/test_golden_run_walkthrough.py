from pathlib import Path


def test_golden_run_walkthrough_has_required_sections():
    root = Path(__file__).resolve().parent.parent
    doc = (root / "docs" / "runs" / "golden_run_walkthrough.md").read_text(encoding="utf-8")

    for title in ["样例 1", "样例 2", "样例 3"]:
        assert title in doc
    for section in ["命令", "输入任务", "预期产物", "Trace 查看", "验收标准", "失败排查"]:
        assert section in doc
    for command in ["opc runs list", "opc trace summary", "opc trace show"]:
        assert command in doc
