from pathlib import Path
import re


def test_public_root_docs_exist():
    root = Path(__file__).resolve().parent.parent
    docs_structure = root / "docs" / "DOCS_STRUCTURE.md"
    content = docs_structure.read_text(encoding="utf-8")
    public_section = content.split("## 内部文档", 1)[0]
    referenced = re.findall(r"- `([^`/]+\.md)`", public_section)
    missing = [path for path in referenced if not (root / path).exists()]
    assert missing == []
