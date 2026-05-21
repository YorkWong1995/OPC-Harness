"""Append-only run trace storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


TRACE_SCHEMA_VERSION = 1


@dataclass
class RunEvent:
    type: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RunSummary:
    artifacts_dir: Path
    run_id: str
    final_status: str | None
    duration_seconds: float | int | None
    failed_reason: str
    updated_at: float


class RunStore:
    def __init__(self, artifacts_dir: Path, run_id: str | None = None):
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or uuid4().hex
        self.trace_path = self.artifacts_dir / "run_trace.json"
        self.events_path = self.artifacts_dir / "run_events.jsonl"
        self.events: list[RunEvent] = []

    def append(self, event_type: str, **payload: Any) -> RunEvent:
        """Append an event. Writes only the JSONL line — O(1) per call.

        Call ``write_trace()`` (or ``finalize()``) at the end of a run to
        produce ``run_trace.json``. Earlier versions wrote the full trace on
        every append, which was O(n^2) over a run.
        """
        event = RunEvent(type=event_type, payload={"run_id": self.run_id, **_json_safe(payload)})
        self.events.append(event)
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return event

    def write_trace(self, final_status: str | None = None, metrics: dict[str, Any] | None = None) -> Path:
        trace = {
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "final_status": final_status,
            "metrics": metrics or {},
            "events": [asdict(event) for event in self.events],
        }
        self.trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.trace_path

    def read_trace(self) -> dict[str, Any]:
        trace: dict[str, Any] = {}
        if self.trace_path.exists():
            trace = json.loads(self.trace_path.read_text(encoding="utf-8"))
        trace.setdefault("trace_schema_version", 0)
        trace.setdefault("run_id", self.run_id)
        trace.setdefault("final_status", None)
        trace.setdefault("metrics", {})
        if "events" not in trace:
            trace["events"] = [asdict(event) for event in self.events]
        return trace

    # Alias requested by the roadmap; kept as a thin wrapper to avoid churn at call sites.
    finalize = write_trace

    @classmethod
    def load(cls, artifacts_dir: Path) -> "RunStore":
        """Reload a run store. Prefer events.jsonl (always up to date); fall
        back to run_trace.json for runs persisted before P2.2.
        """
        events_path = artifacts_dir / "run_events.jsonl"
        trace_path = artifacts_dir / "run_trace.json"

        if events_path.exists():
            run_id = None
            events: list[RunEvent] = []
            for line in events_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = RunEvent(**json.loads(line))
                events.append(event)
                if run_id is None:
                    run_id = event.payload.get("run_id")
            store = cls(artifacts_dir, run_id=run_id)
            store.events = events
            return store

        if not trace_path.exists():
            return cls(artifacts_dir)
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        store = cls(artifacts_dir, run_id=trace.get("run_id"))
        store.events = [RunEvent(**event) for event in trace.get("events", [])]
        return store


def find_run_artifacts(root: Path) -> list[Path]:
    if not root.exists():
        return []
    candidates = [path for path in root.rglob("artifacts") if path.is_dir()]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates


def summarize_run(artifacts_dir: Path) -> RunSummary:
    store = RunStore.load(artifacts_dir)
    trace = store.read_trace()
    metrics_path = artifacts_dir / "run_metrics.json"
    metrics = trace.get("metrics") or {}
    if not metrics and metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    totals = metrics.get("totals", {}) if isinstance(metrics, dict) else {}
    failed_reason = ""
    for event in reversed(trace.get("events", [])):
        payload = event.get("payload", {}) if isinstance(event, dict) else {}
        reason = payload.get("reason") or payload.get("error") or payload.get("message")
        if reason and ("fail" in event.get("type", "") or event.get("type") in {"workflow_stopped", "tool_call"}):
            failed_reason = str(reason)
            break

    return RunSummary(
        artifacts_dir=artifacts_dir,
        run_id=str(trace.get("run_id") or store.run_id),
        final_status=trace.get("final_status"),
        duration_seconds=totals.get("duration_seconds"),
        failed_reason=failed_reason,
        updated_at=artifacts_dir.stat().st_mtime,
    )


def trace_summary(artifacts_dir: Path) -> dict[str, Any]:
    store = RunStore.load(artifacts_dir)
    trace = store.read_trace()
    events = trace.get("events", [])
    metrics = trace.get("metrics") or {}
    totals = metrics.get("totals", {}) if isinstance(metrics, dict) else {}
    return {
        "trace_schema_version": trace.get("trace_schema_version", 0),
        "run_id": trace.get("run_id"),
        "final_status": trace.get("final_status"),
        "event_count": len(events),
        "stage_events": len([event for event in events if event.get("type") in {"stage_started", "stage_completed"}]),
        "tool_calls": len([event for event in events if event.get("type") == "tool_call"]),
        "duration_seconds": totals.get("duration_seconds"),
    }


def trace_inspect(artifacts_dir: Path, focus: str | None = None) -> dict[str, Any]:
    store = RunStore.load(artifacts_dir)
    trace = store.read_trace()
    events = trace.get("events", [])
    compatibility: list[str] = []

    if not store.trace_path.exists():
        compatibility.append("run_trace.json missing; rebuilt view from run_events.jsonl when available")
    if not store.events_path.exists():
        compatibility.append("run_events.jsonl missing; using run_trace.json events when available")

    metrics = trace.get("metrics") or {}
    metrics_path = artifacts_dir / "run_metrics.json"
    if not metrics and metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    elif not metrics:
        compatibility.append("run_metrics.json missing")

    state_path = artifacts_dir / ".opc_state.json"
    state: dict[str, Any] = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        compatibility.append(".opc_state.json missing")

    timeline_types = {"stage_started", "stage_completed", "stage_summary_created"}
    decision_types = {"approval_required", "approval_decision", "rollback_decision", "circuit_breaker_open"}
    failure_types = {
        "validation_failed",
        "role_output_validation_failed",
        "qa_failed",
        "workflow_stopped",
        "cost_hard_limit",
    }

    result = {
        "trace_schema_version": trace.get("trace_schema_version", 0),
        "run_id": trace.get("run_id") or store.run_id,
        "final_status": trace.get("final_status") or state.get("current_stage"),
        "timeline": [event for event in events if event.get("type") in timeline_types],
        "artifacts": state.get("artifact_paths", {}),
        "tool_calls": [
            event for event in events
            if event.get("type") == "tool_call" or str(event.get("type", "")).startswith("guardrail_")
        ],
        "decisions": [event for event in events if event.get("type") in decision_types],
        "failures": [event for event in events if event.get("type") in failure_types],
        "metrics": metrics,
        "compatibility": compatibility,
    }
    if focus and focus != "all":
        focused = {key: result[key] for key in ["trace_schema_version", "run_id", "final_status", "compatibility"]}
        focused[focus] = result.get(focus, [])
        return focused
    return result


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(item) for item in value]
        return str(value)
