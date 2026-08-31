# Onhand Thread

**A browser tutor that turns your reading, mistakes, and feedback into a persistent learning memory.**

Onhand Thread is a Chrome extension + cloud agent built for the All Things Agentic Hackathon (Collaborative Partner category). As you study webpages and PDFs, it asks you checks, watches what you get wrong, and maintains a **persistent learner model** — concepts you've encountered, misconceptions you've shown, and how you like things explained — so it teaches you differently tomorrow than it did today.

## Architecture

```
Chrome extension (Onhand Thread)
        │  OpenAI-compatible SSE + learning-event telemetry
        ▼
Cloud Run: Thread service (FastAPI)
   ├── /v1/chat/completions ──► Gemini (context enriched with learner model)
   ├── /v1/telemetry ─────────► learning events (checks opened/resolved)
   └── Learner-Model Agent (Google ADK + Gemini)
              │  distills each turn + event into durable memory
              ▼
        Firestore: learner model
   (concepts, misconceptions, check outcomes, explanation preferences)
```

- **Gemini** powers both the tutoring conversation and the learner-model agent.
- **Google ADK** (Agent Development Kit) runs the learner-model agent: an LLM agent with Firestore tools that decides *what is worth remembering* about the learner after every turn.
- **Cloud Run** hosts the Thread service.
- **Firestore** is the persistent learner memory, keyed by learner and durable across sessions and devices.

## Repository layout

- `extension/` — the Chrome extension (browser tutor UI, page/PDF context, learning checks)
- `backend/` — the Thread service: FastAPI facade, ADK learner-model agent, Firestore memory
- `docs/` — architecture notes and submission materials

## Provenance

The extension is derived from [Onhand](https://github.com/sriramk/onhand) (Apache-2.0), an open-source contextual learning assistant, at base commit `7a4078e` (2026-08-26). Everything in `backend/` — the ADK learner-model agent, the Firestore learner memory, the Cloud Run service — plus the extension's Thread provider integration was built new during the hackathon submission period.

## License

Apache-2.0 (see `LICENSE`).
