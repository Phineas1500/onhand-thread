# Onhand Thread

**A browser tutor that turns your reading, mistakes, and feedback into a persistent learning memory.**

Onhand Thread is a Chrome extension + cloud agent built for the All Things Agentic Hackathon (Collaborative Partner category). As you study webpages and PDFs, it asks you checks, watches what you get wrong, and maintains a **persistent learner model** — concepts you've encountered, misconceptions you've shown, and how you like things explained — so it teaches you differently tomorrow than it did today.

## Architecture

```
Chrome extension (Onhand Thread)
        │  OpenAI-compatible SSE + learning-event telemetry
        ▼
Cloud Load Balancing (global ALB + serverless NEG)
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
- **Cloud Run** hosts the Thread service, fronted by **Cloud Load Balancing** (global ALB with a serverless NEG and a Google-managed TLS certificate).
- **Firestore** is the persistent learner memory, keyed by learner and durable across sessions and devices.

## Repository layout

- `packages/browser-extension/` — the Chrome extension (browser tutor UI, page/PDF context, learning checks); load this directory unpacked
- `backend/` — the Thread service: FastAPI facade, ADK learner-model agent, Firestore memory, deploy scripts
- `docs/` — architecture diagram, demo setup, submission materials

## Spin-up instructions

Prerequisites: Node 20+, Python 3.12 (via [uv](https://docs.astral.sh/uv/)), the
`gcloud` CLI authenticated against a billing-enabled GCP project, and Chrome.

**1. Deploy the backend (Cloud Run + Firestore + Vertex AI):**

```bash
cd backend
PROJECT=<your-project-id> bash deploy.sh        # APIs, Firestore, IAM, Cloud Run
PROJECT=<your-project-id> bash loadbalancer.sh  # global ALB + managed TLS (optional if *.run.app works for you)
```

`deploy.sh` prints the service URL; your extension base URL is that URL plus `/v1`.

**2. Build and load the extension:**

```bash
npm ci
npm run build:extension
```

Open `chrome://extensions`, enable Developer mode, **Load unpacked**, and select
`packages/browser-extension/`. To point the extension at your own backend, open
the extension service worker console and run:

```js
chrome.storage.local.set({ onhandThreadBaseUrl: "https://<your-backend>/v1" })
```

(The repo ships with our deployed backend baked in as the default, so the
extension works immediately after loading.)

**3. Use it:** open any article or PDF, open the side panel (Cmd+Shift+Space),
and ask about the page. Learning Mode is on by default; answer the checks it
opens and watch your learner model form in the Firestore console under
`learners/`. `GET <backend>/v1/learner` (with your bearer token from
`chrome.storage.local.onhandThreadToken`) returns your current learner model.

**Local development (no cloud):** `cd backend && ONHAND_THREAD_MEMORY=local
GOOGLE_API_KEY=<gemini-api-key> uv run uvicorn app.main:app --port 8787`, then
set the extension's base URL to `http://127.0.0.1:8787/v1`.

## Google technologies

Gemini 3.6 Flash (via Vertex AI) · Google ADK · Cloud Run · Firestore ·
Cloud Load Balancing · Secret Manager · Cloud Build · Artifact Registry —
see [docs/google-stack.md](docs/google-stack.md) for what each one does and
where it lives in the code.

## Provenance

The extension is derived from [Onhand](https://github.com/Phineas1500/Onhand) (Apache-2.0), an open-source contextual learning assistant, at base commit `7a4078e` (2026-08-26). Everything in `backend/` — the ADK learner-model agent, the Firestore learner memory, the Cloud Run service — plus the extension's Thread provider integration was built new during the hackathon submission period.

## License

Apache-2.0 (see `LICENSE`).
