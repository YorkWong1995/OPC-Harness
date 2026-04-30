"""文件型 artifact 存储，保存工作流产出的文档"""

from pathlib import Path


class Store:
    def __init__(self, artifacts_dir: Path):
        self.dir = artifacts_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: str) -> Path:
        path = self.dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def load(self, filename: str) -> str:
        return (self.dir / filename).read_text(encoding="utf-8")

    def exists(self, filename: str) -> bool:
        return (self.dir / filename).exists()
