"""Append-only run trace storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class RunEvent:
    type: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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
            "run_id": self.run_id,
            "final_status": final_status,
            "metrics": metrics or {},
            "events": [asdict(event) for event in self.events],
        }
        self.trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.trace_path

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
