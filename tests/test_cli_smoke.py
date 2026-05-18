"""CLI 冒烟测试：验证 opc 命令行参数解析与索引构建"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# opc run 参数解析测试（不实际调用 API，mock anthropic client）
# ---------------------------------------------------------------------------


@pytest.fixture
def _mock_workflow_deps():
    """Mock HarnessWorkflow 及其依赖，避免实际 API 调用和文件系统操作。"""
    from opc.config import WorkflowConfig

    mock_wf = MagicMock()
    with (
        patch("opc.cli.HarnessWorkflow", return_value=mock_wf) as wf_cls,
        patch("opc.cli.load_workflow_config", return_value=WorkflowConfig()) as load_cfg,
        patch("opc.cli.normalize_roles", side_effect=lambda r: r) as norm_roles,
    ):
        yield wf_cls, load_cfg, norm_roles, mock_wf


def _call_main_with_args(args: list[str]):
    """以给定参数调用 opc.cli.main()。"""
    with patch("sys.argv", ["opc"] + args):
        from opc.cli import main
        main()


def test_run_minimal_task(_mock_workflow_deps):
    """opc run '测试任务' 最小参数：仅提供 task。"""
    wf_cls, _load_cfg, _norm, mock_wf = _mock_workflow_deps
    _call_main_with_args(["run", "测试任务"])

    wf_cls.assert_called_once()
    call_kwargs = wf_cls.call_args[1]
    assert call_kwargs["task"] == "测试任务"
    assert call_kwargs["auto_confirm"] is False
    assert call_kwargs["model"] is None
    mock_wf.run.assert_called_once()


def test_run_with_project(_mock_workflow_deps):
    """opc run '任务' --project myproj 正确传递 project 并创建目录。"""
    wf_cls, _load_cfg, _norm, mock_wf = _mock_workflow_deps
    _call_main_with_args(["run", "任务", "--project", "myproj"])

    call_kwargs = wf_cls.call_args[1]
    assert call_kwargs["task"] == "任务"
    # project_dir 应指向 workspace/myproj
    assert call_kwargs["project_dir"].name == "myproj"
    assert "workspace" in str(call_kwargs["project_dir"])


def test_run_with_project_dir(_mock_workflow_deps, tmp_path: Path):
    """opc run '任务' --project-dir <path> 使用指定目录。"""
    wf_cls, _load_cfg, _norm, mock_wf = _mock_workflow_deps
    project_dir = tmp_path / "existing_project"
    project_dir.mkdir()

    _call_main_with_args(["run", "任务", "--project-dir", str(project_dir)])

    call_kwargs = wf_cls.call_args[1]
    assert call_kwargs["project_dir"].resolve() == project_dir.resolve()


def test_run_with_model(_mock_workflow_deps):
    """opc run '任务' --model claude-opus-4-6 正确传递模型名称。"""
    wf_cls, _load_cfg, _norm, mock_wf = _mock_workflow_deps
    _call_main_with_args(["run", "任务", "--model", "claude-opus-4-6"])

    call_kwargs = wf_cls.call_args[1]
    assert call_kwargs["model"] == "claude-opus-4-6"


def test_run_auto_confirm(_mock_workflow_deps):
    """opc run '任务' --auto-confirm 启用自动确认。"""
    wf_cls, _load_cfg, _norm, mock_wf = _mock_workflow_deps
    _call_main_with_args(["run", "任务", "--auto-confirm"])

    call_kwargs = wf_cls.call_args[1]
    assert call_kwargs["auto_confirm"] is True


def test_run_ceo_review(_mock_workflow_deps):
    """opc run '任务' --ceo-review 将 ceo 加入角色集。"""
    wf_cls, _load_cfg, _norm, mock_wf = _mock_workflow_deps
    _call_main_with_args(["run", "任务", "--ceo-review"])

    call_kwargs = wf_cls.call_args[1]
    assert "ceo" in call_kwargs["roles"]


def test_run_skip_architect(_mock_workflow_deps):
    """opc run '任务' --skip-architect 从角色集中移除 architect。"""
    wf_cls, _load_cfg, _norm, mock_wf = _mock_workflow_deps
    _call_main_with_args(["run", "任务", "--skip-architect"])

    call_kwargs = wf_cls.call_args[1]
    assert "architect" not in call_kwargs["roles"]


def test_run_combined_flags(_mock_workflow_deps, tmp_path: Path):
    """opc run 组合多个 flag 的参数解析。"""
    wf_cls, _load_cfg, _norm, mock_wf = _mock_workflow_deps
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    _call_main_with_args([
        "run", "综合任务",
        "--project-dir", str(project_dir),
        "--model", "claude-haiku-4-5-20251001",
        "--auto-confirm",
        "--ceo-review",
        "--skip-architect",
    ])

    call_kwargs = wf_cls.call_args[1]
    assert call_kwargs["task"] == "综合任务"
    assert call_kwargs["project_dir"].resolve() == project_dir.resolve()
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert call_kwargs["auto_confirm"] is True
    assert "ceo" in call_kwargs["roles"]
    assert "architect" not in call_kwargs["roles"]


def test_ui_command_launches_streamlit():
    """opc ui 使用 streamlit 启动可视化控制台。"""
    with (
        patch("shutil.which", return_value="streamlit"),
        patch("os.execv") as execv,
    ):
        _call_main_with_args(["ui", "--host", "0.0.0.0", "--port", "8600"])

    args = execv.call_args[0][1]
    assert args[:2] == ["streamlit", "run"]
    assert "ui.py" in args[2]
    assert "--server.address" in args
    assert "0.0.0.0" in args
    assert "--server.port" in args
    assert "8600" in args


# ---------------------------------------------------------------------------
# opc index / query 冒烟测试
# ---------------------------------------------------------------------------


@pytest.fixture
def test_data(tmp_path: Path) -> Path:
    """创建测试用文件目录"""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()

    (data_dir / "hello.py").write_text(
        'def greet(name):\n    return f"Hello, {name}!"\n',
        encoding="utf-8",
    )
    (data_dir / "readme.md").write_text(
        "# Test Project\n\nThis is a test.\n",
        encoding="utf-8",
    )
    return data_dir


def test_opc_index_smoke(test_data: Path, tmp_path: Path):
    """opc index --name test-idx --dirs test_data 能成功构建索引"""
    index_root = tmp_path / "index_output"

    result = subprocess.run(
        [
            sys.executable, "-m", "opc.cli",
            "index",
            "--name", "test-idx",
            "--dirs", str(test_data),
        ],
        env={
            **__import__("os").environ,
            "OPC_INDEX_ROOT": str(index_root),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert result.returncode == 0, (
        f"opc index 失败 (exit code {result.returncode})\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # 验证索引目录和元数据已生成
    index_dir = index_root / "test-idx" / "index"
    assert index_dir.exists(), f"索引目录未生成: {index_dir}"
    assert (index_dir / "meta.json").exists(), "meta.json 未生成"
    assert (index_dir / "bm25").exists(), "BM25 索引目录未生成"
    assert (index_dir / "vector").exists(), "向量索引目录未生成"

    # 验证元数据内容
    import json

    meta = json.loads((index_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["index_name"] == "test-idx"
    assert meta["total_files"] >= 1
    assert meta["total_chunks"] >= 1


def test_opc_query_no_llm(test_data: Path, tmp_path: Path):
    """opc query "测试问题" --name test-idx --no-llm 能返回结果"""
    index_root = tmp_path / "index_output"

    # 先构建索引
    build = subprocess.run(
        [
            sys.executable, "-m", "opc.cli",
            "index",
            "--name", "test-idx",
            "--dirs", str(test_data),
        ],
        env={
            **__import__("os").environ,
            "OPC_INDEX_ROOT": str(index_root),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert build.returncode == 0, f"索引构建失败: {build.stderr}"

    # 执行查询
    result = subprocess.run(
        [
            sys.executable, "-m", "opc.cli",
            "query", "测试问题",
            "--name", "test-idx",
            "--no-llm",
        ],
        env={
            **__import__("os").environ,
            "OPC_INDEX_ROOT": str(index_root),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert result.returncode == 0, (
        f"opc query 失败 (exit code {result.returncode})\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "检索结果" in result.stdout or "检索详情" in result.stdout, (
        f"未找到检索结果输出\nstdout: {result.stdout}"
    )
