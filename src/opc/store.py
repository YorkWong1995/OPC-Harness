"""文件型 artifact 存储，保存工作流产出的文档"""

import json
from pathlib import Path


class Store:
    def __init__(self, artifacts_dir: Path):
        self.dir = artifacts_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: str) -> Path:
        path = self.dir / filename
        manifest_path = self.dir / "artifact_versions.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        entry = manifest.setdefault(filename, {"latest": filename, "versions": []})
        version = len(entry["versions"]) + 1
        versioned_name = f"{path.stem}.v{version}{path.suffix}"
        versioned_path = self.dir / versioned_name
        versioned_path.write_text(content, encoding="utf-8")
        path.write_text(content, encoding="utf-8")
        entry["latest"] = filename
        entry["versions"].append(versioned_name)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, filename: str) -> str:
        return (self.dir / filename).read_text(encoding="utf-8")

    def exists(self, filename: str) -> bool:
        return (self.dir / filename).exists()
