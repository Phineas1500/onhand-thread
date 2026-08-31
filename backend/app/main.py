"""Onhand Thread service — the Cloud Run backend.

Surface (mirrors the contract the Onhand extension already speaks):
  POST /v1/register          -> {token}; the token is the stable learner identity
  POST /v1/chat/completions  -> OpenAI-compatible tutor lane (Gemini), learner
                                model injected, replies distilled into memory
  POST /v1/telemetry         -> learning events (checks opened/resolved, feedback)
  GET  /v1/learner           -> current learner model (demo/debug)
  GET  /healthz
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from collections import OrderedDict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import gemini_proxy, learner_agent
from .memory import LearnerStore, learner_context_block

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("thread.main")

app = FastAPI(title="Onhand Thread")
store = LearnerStore()

OBSERVATION_LIMIT = 4000
_distilled_turns: OrderedDict[str, None] = OrderedDict()


def _seen_turn(turn_id: str) -> bool:
    """One distillation per extension turn (the agent loop makes several
    model calls per turn; only the first carries the fresh user prompt)."""
    if not turn_id:
        return False
    if turn_id in _distilled_turns:
        return True
    _distilled_turns[turn_id] = None
    while len(_distilled_turns) > 500:
        _distilled_turns.popitem(last=False)
    return False


def learner_id_from_request(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    token = auth[7:].strip()
    if not token.startswith("thr_"):
        raise HTTPException(401, "unrecognized token")
    return "lrn_" + hashlib.sha256(token.encode()).hexdigest()[:20]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"ok": "true", "memory": store.mode}


@app.post("/v1/register")
async def register() -> dict[str, str]:
    return {"token": "thr_" + secrets.token_urlsafe(24)}


@app.get("/v1/learner")
async def get_learner(learner_id: str = Depends(learner_id_from_request)):
    return await store.get(learner_id)


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request, learner_id: str = Depends(learner_id_from_request)
):
    try:
        body = json.loads(await request.body())
    except json.JSONDecodeError:
        raise HTTPException(400, "invalid JSON body")

    api_key = os.environ["GOOGLE_API_KEY"]
    model = await store.get(learner_id)
    gemini_proxy.inject_learner_context(body, learner_context_block(model))

    turn_id = request.headers.get("x-onhand-turn-id", "")
    user_text = gemini_proxy.last_user_text(body)
    # Distill only real tutoring turns: the main agent loop sends tools; the
    # extension's internal JSON planner calls do not. A turn spans several
    # model calls (tool-call rounds produce no text), so consume the turn id
    # only once a call actually yields assistant text.
    eligible = bool(body.get("tools")) and len(user_text) > 20

    def on_complete(assistant_text: str) -> None:
        if not eligible or not assistant_text.strip() or _seen_turn(turn_id):
            return
        observation = (
            f"Student (context/prompt): {user_text[:OBSERVATION_LIMIT]}\n\n"
            f"Tutor replied: {assistant_text[:OBSERVATION_LIMIT]}"
        )
        learner_agent.distill_in_background(store, learner_id, observation, "turn")

    if body.get("stream"):
        return StreamingResponse(
            gemini_proxy.stream_completion(body, api_key, on_complete),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )
    status, data, assistant_text = await gemini_proxy.completion(body, api_key)
    on_complete(assistant_text)
    return JSONResponse(data, status_code=status)


@app.post("/v1/telemetry")
async def telemetry(request: Request):
    """Learning events from the extension. Check results and explicit learner
    feedback go through the learner-model agent; everything else is logged."""
    try:
        payload = json.loads(await request.body())
    except json.JSONDecodeError:
        return JSONResponse({"ok": False}, status_code=400)
    try:
        learner_id = learner_id_from_request(request)
    except HTTPException:
        return JSONResponse({"ok": True})  # telemetry is best-effort

    events = payload.get("events") or [payload]
    for event in events:
        if not isinstance(event, dict):
            continue
        etype = str(event.get("type", ""))
        await store.log_event(learner_id, event)
        if etype == "check_resolved":
            # assessment vocabulary from the extension: correct | partial |
            # incorrect | skipped
            assessment = str(event.get("assessment", ""))
            if assessment in {"correct", "partial", "incorrect"}:
                await store.record_check(learner_id, assessment == "correct")
            observation = (
                f"Learning check on page {event.get('page', '')!r}.\n"
                f"Concept: {event.get('concept', '')}\n"
                f"Question: {event.get('question', '')}\n"
                f"Tutor assessed the student's answer as: {assessment}\n"
                f"Evidence: {event.get('evidence', '')}"
            )
            if assessment != "skipped":
                learner_agent.distill_in_background(
                    store, learner_id, observation, "check"
                )
        elif etype == "learner_feedback":
            learner_agent.distill_in_background(
                store,
                learner_id,
                f"Student gave explicit feedback to the tutor: {event.get('text', '')}",
                "feedback",
            )
    return JSONResponse({"ok": True})


@app.post("/v1/error-reports")
async def error_reports() -> dict[str, bool]:
    return {"ok": True}
