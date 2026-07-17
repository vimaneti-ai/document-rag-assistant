import time
from copy import deepcopy
from threading import RLock
from typing import Optional


PIPELINE_STEPS = {
    "upload": [
        ("validation", "Validate file"),
        ("parsing", "Extract content"),
        ("chunking", "Create chunks"),
        ("embedding", "Generate embeddings"),
        ("indexing", "Store in Pinecone"),
        ("summary", "Create summary"),
    ],
    "chat": [
        ("query_embedding", "Embed question"),
        ("retrieval", "Search Pinecone"),
        ("prompt", "Assemble context"),
        ("generation", "Generate with Claude"),
        ("citations", "Attach sources"),
    ],
}


class OperationTracker:
    def __init__(self, retention_seconds: int = 3600) -> None:
        self.retention_seconds = retention_seconds
        self._operations: dict[str, dict] = {}
        self._lock = RLock()

    def start(self, operation_id: str, kind: str) -> dict:
        if kind not in PIPELINE_STEPS:
            raise ValueError(f"Unknown pipeline kind: {kind}")

        now = time.time()
        operation = {
            "operation_id": operation_id,
            "kind": kind,
            "status": "running",
            "started_at": now,
            "elapsed_ms": 0,
            "steps": [
                {
                    "id": step_id,
                    "label": label,
                    "status": "pending",
                    "detail": None,
                    "duration_ms": None,
                    "_started_at": None,
                }
                for step_id, label in PIPELINE_STEPS[kind]
            ],
        }
        with self._lock:
            self._prune(now)
            self._operations[operation_id] = operation
            return self._snapshot(operation)

    def begin_step(self, operation_id: str, step_id: str, detail: Optional[str] = None) -> None:
        with self._lock:
            operation = self._required(operation_id)
            step = self._step(operation, step_id)
            step["status"] = "running"
            step["detail"] = detail
            step["_started_at"] = time.perf_counter()

    def finish_step(self, operation_id: str, step_id: str, detail: Optional[str] = None) -> None:
        with self._lock:
            operation = self._required(operation_id)
            step = self._step(operation, step_id)
            started_at = step.get("_started_at")
            step["status"] = "completed"
            step["detail"] = detail
            step["duration_ms"] = (
                max(0, round((time.perf_counter() - started_at) * 1000))
                if started_at is not None
                else 0
            )

    def complete(self, operation_id: str) -> dict:
        with self._lock:
            operation = self._required(operation_id)
            operation["status"] = "completed"
            operation["elapsed_ms"] = max(
                0, round((time.time() - operation["started_at"]) * 1000)
            )
            return self._snapshot(operation)

    def fail(self, operation_id: str, detail: str) -> Optional[dict]:
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                return None
            operation["status"] = "failed"
            operation["elapsed_ms"] = max(
                0, round((time.time() - operation["started_at"]) * 1000)
            )
            running_step = next(
                (step for step in operation["steps"] if step["status"] == "running"),
                None,
            )
            if running_step is not None:
                started_at = running_step.get("_started_at")
                running_step["status"] = "failed"
                running_step["detail"] = detail
                running_step["duration_ms"] = (
                    max(0, round((time.perf_counter() - started_at) * 1000))
                    if started_at is not None
                    else 0
                )
            return self._snapshot(operation)

    def get(self, operation_id: str) -> Optional[dict]:
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                return None
            snapshot = self._snapshot(operation)
            if operation["status"] == "running":
                snapshot["elapsed_ms"] = max(
                    0, round((time.time() - operation["started_at"]) * 1000)
                )
                for position, step in enumerate(operation["steps"]):
                    if step["status"] == "running" and step.get("_started_at") is not None:
                        snapshot["steps"][position]["duration_ms"] = max(
                            0,
                            round((time.perf_counter() - step["_started_at"]) * 1000),
                        )
            return snapshot

    def _required(self, operation_id: str) -> dict:
        operation = self._operations.get(operation_id)
        if operation is None:
            raise KeyError(f"Unknown operation: {operation_id}")
        return operation

    def _step(self, operation: dict, step_id: str) -> dict:
        step = next((item for item in operation["steps"] if item["id"] == step_id), None)
        if step is None:
            raise KeyError(f"Unknown pipeline step: {step_id}")
        return step

    def _snapshot(self, operation: dict) -> dict:
        snapshot = deepcopy(operation)
        for step in snapshot["steps"]:
            step.pop("_started_at", None)
        return snapshot

    def _prune(self, now: float) -> None:
        expired = [
            operation_id
            for operation_id, operation in self._operations.items()
            if now - operation["started_at"] > self.retention_seconds
        ]
        for operation_id in expired:
            self._operations.pop(operation_id, None)
