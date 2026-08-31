"""Persistent learner-model store.

Firestore in production (Cloud Run service account / ADC); an in-process
dict when ONHAND_THREAD_MEMORY=local so the service runs end-to-end on a
laptop before any cloud auth exists.

Learner doc shape (learners/{learner_id}):
  preferences: {key: value}            # how they like to be taught
  concepts: {slug: {name, status, note, evidence, last_seen}}
      status: encountered | solid | shaky | misconception
  stats: {checks_total, checks_correct, turns}
  updated_at: iso string

Raw events land in learners/{learner_id}/events for the audit trail.
"""

from __future__ import annotations

import datetime
import os
import re
from typing import Any


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] or "unnamed"


def empty_model() -> dict[str, Any]:
    return {
        "preferences": {},
        "concepts": {},
        "stats": {"checks_total": 0, "checks_correct": 0, "turns": 0},
        "updated_at": _now(),
    }


class LearnerStore:
    """Async learner-model store backed by Firestore or local memory."""

    def __init__(self) -> None:
        self._mode = os.environ.get("ONHAND_THREAD_MEMORY", "firestore")
        self._local: dict[str, dict[str, Any]] = {}
        self._db = None
        if self._mode == "firestore":
            from google.cloud import firestore

            self._db = firestore.AsyncClient(
                project=os.environ.get("GOOGLE_CLOUD_PROJECT") or None,
                database=os.environ.get("ONHAND_THREAD_FIRESTORE_DB", "(default)"),
            )

    @property
    def mode(self) -> str:
        return self._mode

    async def get(self, learner_id: str) -> dict[str, Any]:
        if self._db is None:
            return self._local.setdefault(learner_id, empty_model())
        snap = await self._db.collection("learners").document(learner_id).get()
        return snap.to_dict() if snap.exists else empty_model()

    async def put(self, learner_id: str, model: dict[str, Any]) -> None:
        model["updated_at"] = _now()
        if self._db is None:
            self._local[learner_id] = model
            return
        await self._db.collection("learners").document(learner_id).set(model)

    async def log_event(self, learner_id: str, event: dict[str, Any]) -> None:
        event = {**event, "ts": event.get("ts") or _now()}
        if self._db is None:
            self._local.setdefault(learner_id + "/events", empty_model()).setdefault(
                "log", []
            ).append(event)
            return
        await (
            self._db.collection("learners")
            .document(learner_id)
            .collection("events")
            .add(event)
        )

    # --- mutations used as ADK tool implementations -----------------------

    async def upsert_concept(
        self, learner_id: str, name: str, status: str, note: str
    ) -> dict[str, Any]:
        model = await self.get(learner_id)
        slug = slugify(name)
        prior = model["concepts"].get(slug, {})
        model["concepts"][slug] = {
            "name": name,
            "status": status,
            "note": note[:500],
            "evidence": int(prior.get("evidence", 0)) + 1,
            "last_seen": _now(),
        }
        await self.put(learner_id, model)
        return model["concepts"][slug]

    async def set_preference(self, learner_id: str, key: str, value: str) -> None:
        model = await self.get(learner_id)
        model["preferences"][slugify(key)] = value[:300]
        await self.put(learner_id, model)

    async def record_check(self, learner_id: str, correct: bool) -> None:
        model = await self.get(learner_id)
        model["stats"]["checks_total"] += 1
        if correct:
            model["stats"]["checks_correct"] += 1
        await self.put(learner_id, model)

    async def bump_turns(self, learner_id: str) -> None:
        model = await self.get(learner_id)
        model["stats"]["turns"] = int(model["stats"].get("turns", 0)) + 1
        await self.put(learner_id, model)


def learner_context_block(model: dict[str, Any]) -> str:
    """Render the learner model as a system-context block for the tutor."""
    concepts = model.get("concepts", {})
    prefs = model.get("preferences", {})
    stats = model.get("stats", {})
    if not concepts and not prefs:
        return ""
    lines = [
        "## Persistent learner model (Onhand Thread memory)",
        "You have taught this learner before. Adapt to what follows; do not",
        "recite it back to them unless they ask what you remember.",
    ]
    misconceptions = {s: c for s, c in concepts.items() if c.get("status") == "misconception"}
    shaky = {s: c for s, c in concepts.items() if c.get("status") == "shaky"}
    solid = {s: c for s, c in concepts.items() if c.get("status") == "solid"}
    seen = {s: c for s, c in concepts.items() if c.get("status") == "encountered"}
    if misconceptions:
        lines.append("Active misconceptions (address these directly when relevant):")
        lines += [f"- {c['name']}: {c.get('note', '')}" for c in misconceptions.values()]
    if shaky:
        lines.append("Shaky understanding (reinforce, quiz gently):")
        lines += [f"- {c['name']}: {c.get('note', '')}" for c in shaky.values()]
    if solid:
        lines.append("Solid (build on these, skip re-explaining):")
        lines += [f"- {c['name']}" for c in solid.values()]
    if seen:
        lines.append("Previously encountered: " + ", ".join(c["name"] for c in seen.values()))
    if prefs:
        lines.append("Teaching preferences:")
        lines += [f"- {k}: {v}" for k, v in prefs.items()]
    total, correct = stats.get("checks_total", 0), stats.get("checks_correct", 0)
    if total:
        lines.append(f"Check record: {correct}/{total} correct across all sessions.")
    return "\n".join(lines)
