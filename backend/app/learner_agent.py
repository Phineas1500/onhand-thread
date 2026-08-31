"""The learner-model agent: a Google ADK agent that decides what a tutoring
exchange or learning-check event reveals about the learner, and writes those
judgments into the persistent Firestore learner model through tools.

This is deliberately an LLM agent rather than a heuristic: whether a wrong
answer is a slip, a shaky concept, or a genuine misconception — and whether a
preference ("show me code, not prose") is worth remembering — is a judgment
call. The tutor lane stays fast; this agent runs after the fact.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .memory import LearnerStore

log = logging.getLogger("thread.learner_agent")

DISTILL_MODEL = os.environ.get("ONHAND_THREAD_DISTILL_MODEL", "gemini-3.6-flash")

INSTRUCTION = """\
You maintain a persistent learner model for one student using Onhand Thread,
a browser tutor. You are given (1) the current learner model and (2) a new
observation: either a tutoring exchange (what the student read/asked and how
the tutor replied) or a learning-check result (a question the student
answered, and whether they were correct).

Decide what, if anything, this observation reveals about the learner, then
record it with your tools:

- upsert_concept(name, status, note): a concept the learner engaged with.
  status must be one of: encountered (saw it, no evidence either way),
  solid (demonstrated understanding), shaky (partial/uncertain grasp),
  misconception (holds a specific wrong belief — put the wrong belief in the
  note so a future tutor can target it).
- set_preference(key, value): a durable teaching preference the learner
  expressed or demonstrated (e.g. explanation_style: "prefers concrete code
  examples over prose"). Only genuine, durable preferences.
- note_no_update(reason): when the observation reveals nothing durable.

Rules: be conservative — 0 to 3 tool calls per observation. Name concepts
canonically and reuse existing concept names from the model when the
observation is about the same idea (so evidence accumulates instead of
fragmenting). Never invent facts about the learner. An incorrect check answer
usually means shaky; call it a misconception only when the wrong answer
implies a specific wrong belief. A correct answer on a previously shaky
concept upgrades it to solid.
"""


def build_tools(store: LearnerStore, learner_id: str):
    """ADK function tools closed over the store and learner identity."""

    async def upsert_concept(name: str, status: str, note: str) -> dict[str, Any]:
        """Create or update a concept in the learner model.

        Args:
            name: Canonical concept name, e.g. "TCP slow start".
            status: One of encountered, solid, shaky, misconception.
            note: One sentence of evidence; for misconceptions, the specific
                wrong belief the learner holds.
        """
        if status not in {"encountered", "solid", "shaky", "misconception"}:
            return {"error": f"invalid status {status!r}"}
        result = await store.upsert_concept(learner_id, name, status, note)
        return {"saved": result}

    async def set_preference(key: str, value: str) -> dict[str, Any]:
        """Record a durable teaching preference for this learner.

        Args:
            key: Short preference key, e.g. "explanation_style".
            value: The preference, e.g. "prefers analogies before formalism".
        """
        await store.set_preference(learner_id, key, value)
        return {"saved": {key: value}}

    async def note_no_update(reason: str) -> dict[str, Any]:
        """Explicitly record that this observation warrants no model change.

        Args:
            reason: One short sentence explaining why.
        """
        return {"ok": reason}

    return [upsert_concept, set_preference, note_no_update]


async def distill(
    store: LearnerStore,
    learner_id: str,
    observation: str,
    kind: str,
) -> list[str]:
    """Run the learner-model agent over one observation. Returns tool-call
    summaries (for logging/demo)."""
    model_snapshot = await store.get(learner_id)
    agent = Agent(
        name="learner_model_agent",
        model=DISTILL_MODEL,
        instruction=INSTRUCTION,
        tools=build_tools(store, learner_id),
    )
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent, app_name="onhand-thread", session_service=session_service
    )
    session_id = uuid.uuid4().hex
    await session_service.create_session(
        app_name="onhand-thread", user_id=learner_id, session_id=session_id
    )

    concepts = model_snapshot.get("concepts", {})
    known = (
        "\n".join(
            f"- {c['name']} [{c['status']}] {c.get('note', '')}"
            for c in concepts.values()
        )
        or "(empty — new learner)"
    )
    prefs = model_snapshot.get("preferences", {}) or "(none)"
    prompt = (
        f"CURRENT LEARNER MODEL\nConcepts:\n{known}\nPreferences: {prefs}\n\n"
        f"NEW OBSERVATION ({kind}):\n{observation}"
    )

    actions: list[str] = []
    async for event in runner.run_async(
        user_id=learner_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        for call in event.get_function_calls() or []:
            actions.append(f"{call.name}({call.args})")
    await store.log_event(
        learner_id,
        {"type": f"distill_{kind}", "observation": observation[:2000], "actions": actions},
    )
    log.info("distill(%s) for %s: %s", kind, learner_id, actions or "no tool calls")
    return actions


def distill_in_background(
    store: LearnerStore, learner_id: str, observation: str, kind: str
) -> None:
    """Fire-and-forget wrapper safe to call from request handlers."""

    async def _run() -> None:
        try:
            await distill(store, learner_id, observation, kind)
        except Exception:
            log.exception("learner-model distillation failed")

    asyncio.get_running_loop().create_task(_run())
