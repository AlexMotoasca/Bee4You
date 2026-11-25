"""Persist one LangGraph thread as JSON so it lives in our own Postgres table.

Each request loads the thread into an InMemorySaver, runs the graph, and dumps it back in
the SAME transaction as any record it saved. That keeps the conversation state and the
saved record consistent, needs no extra DB driver, and works on serverless hosts.
The stored bytes are LangGraph-serialized values written only by this server; the table
is not readable or writable by users (see the voice_sessions migration).
"""

import base64
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

FORMAT_VERSION = 1


def _enc(typed: tuple[str, bytes]) -> list[str]:
    return [typed[0], base64.b64encode(typed[1]).decode("ascii")]


def _dec(raw: list[str]) -> tuple[str, bytes]:
    return raw[0], base64.b64decode(raw[1])


class ThreadStore:
    def __init__(self, thread_id: str) -> None:
        self.thread_id = thread_id
        self.saver = InMemorySaver()

    @property
    def config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}

    def dump(self) -> dict[str, Any]:
        t = self.thread_id
        checkpoints = [
            [ns, cp_id, _enc(cp), _enc(meta), parent]
            for ns, by_id in self.saver.storage.get(t, {}).items()
            for cp_id, (cp, meta, parent) in by_id.items()
        ]
        writes = [
            [ns, cp_id, task_id, idx, w_task, channel, _enc(value), task_path]
            for (wt, ns, cp_id), inner in self.saver.writes.items()
            if wt == t
            for (task_id, idx), (w_task, channel, value, task_path) in inner.items()
        ]
        blobs = [
            [ns, channel, version, _enc(value)]
            for (bt, ns, channel, version), value in self.saver.blobs.items()
            if bt == t
        ]
        return {"v": FORMAT_VERSION, "checkpoints": checkpoints, "writes": writes, "blobs": blobs}

    def load(self, data: dict[str, Any]) -> None:
        if data.get("v") != FORMAT_VERSION:
            raise ValueError("unsupported voice session format")
        t = self.thread_id
        for ns, cp_id, cp, meta, parent in data["checkpoints"]:
            self.saver.storage[t][ns][cp_id] = (_dec(cp), _dec(meta), parent)
        for ns, cp_id, task_id, idx, w_task, channel, value, task_path in data["writes"]:
            self.saver.writes[(t, ns, cp_id)][(task_id, idx)] = (
                w_task,
                channel,
                _dec(value),
                task_path,
            )
        for ns, channel, version, value in data["blobs"]:
            self.saver.blobs[(t, ns, channel, version)] = _dec(value)
