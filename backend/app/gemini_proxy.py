"""Tutor lane: OpenAI-compatible passthrough to Gemini.

The extension speaks OpenAI chat-completions with SSE streaming and tool
calls. Gemini exposes an OpenAI-compatible surface at
generativelanguage.googleapis.com/v1beta/openai, so this lane forwards the
request nearly verbatim — after injecting the persistent learner model into
the system context — and tees the assistant's reply for the learner-model
agent to distill afterwards.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from typing import Any, AsyncIterator, Callable

import httpx

GEMINI_OPENAI_BASE = os.environ.get(
    "ONHAND_THREAD_GEMINI_OPENAI_BASE",
    "https://generativelanguage.googleapis.com/v1beta/openai",
)
TUTOR_MODEL = os.environ.get("ONHAND_THREAD_TUTOR_MODEL", "gemini-3.6-flash")

_client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=20.0))

# Gemini requires the thought_signature it emitted with a tool call to come
# back when that tool call is replayed in conversation history. OpenAI
# clients (the extension included) drop Google's extra_content when they
# rebuild history, so we cache signatures by tool-call id on the way out and
# re-attach them on the way in. The dummy value is Google's documented
# validator bypass for history that has no signature (e.g. after a restart).
DUMMY_THOUGHT_SIGNATURE = "context_engineering_is_the_way_to_go"
_signatures: OrderedDict[str, str] = OrderedDict()


def _remember_signature(tool_call_id: str, signature: str) -> None:
    if not tool_call_id or not signature:
        return
    _signatures[tool_call_id] = signature
    while len(_signatures) > 2000:
        _signatures.popitem(last=False)


def attach_thought_signatures(body: dict[str, Any]) -> None:
    """Re-attach cached (or dummy) thought signatures to replayed tool calls."""
    for msg in body.get("messages") or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            google = (tc.get("extra_content") or {}).get("google") or {}
            if not google.get("thought_signature"):
                sig = _signatures.get(str(tc.get("id") or ""), DUMMY_THOUGHT_SIGNATURE)
                tc["extra_content"] = {"google": {"thought_signature": sig}}


def _harvest_signatures(delta: dict[str, Any], ids_by_index: dict[int, str]) -> None:
    for tc in delta.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        index = tc.get("index", 0)
        if tc.get("id"):
            ids_by_index[index] = tc["id"]
        sig = ((tc.get("extra_content") or {}).get("google") or {}).get(
            "thought_signature"
        )
        if sig:
            _remember_signature(ids_by_index.get(index, ""), sig)


def message_text(content: Any) -> str:
    """Flatten OpenAI message content (string or parts list) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
        )
    return ""


def inject_learner_context(body: dict[str, Any], block: str) -> None:
    """Append the learner-model block to the request's system context."""
    if not block:
        return
    messages = body.get("messages")
    if not isinstance(messages, list):
        return
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "system":
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = content + "\n\n" + block
            elif isinstance(content, list):
                content.append({"type": "text", "text": block})
            return
    messages.insert(0, {"role": "system", "content": block})


def last_user_text(body: dict[str, Any]) -> str:
    for msg in reversed(body.get("messages") or []):
        if isinstance(msg, dict) and msg.get("role") == "user":
            return message_text(msg.get("content"))
    return ""


async def stream_completion(
    body: dict[str, Any],
    api_key: str,
    on_complete: Callable[[str], None],
) -> AsyncIterator[bytes]:
    """Forward a streaming chat completion to Gemini; yield raw SSE bytes.

    Calls on_complete(assistant_text) once the upstream stream finishes.
    """
    body = {**body, "model": TUTOR_MODEL}
    attach_thought_signatures(body)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    assistant_parts: list[str] = []
    ids_by_index: dict[int, str] = {}
    async with _client.stream(
        "POST", f"{GEMINI_OPENAI_BASE}/chat/completions", json=body, headers=headers
    ) as response:
        if response.status_code != 200:
            detail = (await response.aread()).decode("utf-8", "replace")
            payload = json.dumps(
                {"error": {"message": f"upstream {response.status_code}: {detail[:800]}"}}
            )
            yield f"data: {payload}\n\n".encode()
            yield b"data: [DONE]\n\n"
            return
        async for line in response.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0]["delta"]
                    if isinstance(delta.get("content"), str):
                        assistant_parts.append(delta["content"])
                    _harvest_signatures(delta, ids_by_index)
                except (json.JSONDecodeError, LookupError, TypeError):
                    pass
            yield (line + "\n").encode()
        yield b"\n"
    on_complete("".join(assistant_parts))


async def completion(body: dict[str, Any], api_key: str) -> tuple[int, dict[str, Any], str]:
    """Non-streaming completion. Returns (status, json_body, assistant_text)."""
    body = {**body, "model": TUTOR_MODEL}
    attach_thought_signatures(body)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = await _client.post(
        f"{GEMINI_OPENAI_BASE}/chat/completions", json=body, headers=headers
    )
    try:
        data = response.json()
    except json.JSONDecodeError:
        data = {"error": {"message": response.text[:800]}}
    text = ""
    try:
        message = data["choices"][0]["message"]
        text = message_text(message.get("content"))
        for tc in message.get("tool_calls") or []:
            sig = ((tc.get("extra_content") or {}).get("google") or {}).get(
                "thought_signature"
            )
            _remember_signature(str(tc.get("id") or ""), sig or "")
    except (LookupError, TypeError):
        pass
    return response.status_code, data, text
