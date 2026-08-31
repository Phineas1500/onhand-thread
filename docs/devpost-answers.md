# Devpost form — drafted answers

Every field on the submission wizard, in order. Copy-paste ready.

## Step 1 — Project overview

**Project name** (60 max):
`Onhand Thread` (13 chars)

**Elevator pitch** (200 max, 196 used):
`A browser tutor that remembers how you learn — your reading, checks, and mistakes become a persistent learner model that changes how it teaches you tomorrow. Gemini + ADK + Firestore on Cloud Run.`

**Thumbnail** (3:2, ≤5MB): use a screenshot of the side panel mid-tutoring on the
transformers lecture (crop to 3:2), or `docs/architecture.png` as fallback.

## Step 2 — Project details (public page)

**About the project** (Markdown):

```markdown
## Inspiration

Every AI tutor has amnesia. You can spend an evening working through TCP congestion control with an assistant, reveal exactly which idea you're confused about — and tomorrow it re-explains everything from zero, including the parts you had mastered. Human tutors are valuable precisely because they remember *you*: what you've seen, what you got wrong, and how you like things explained.

## What it does

Onhand Thread is a Chrome extension tutor that lives beside any webpage or PDF. As you study, it explains, anchors answers to the source with highlights, and opens learning checks (prediction/retrieval questions). Every exchange and every check result flows to a **learner-model agent** (Google ADK + Gemini) that decides what the moment revealed about you — a misconception, a solidified concept, a teaching preference — and writes that judgment into a **persistent Firestore learner model**.

The next time you open the tutor — new tab, new day, new topic — Gemini teaches with that model in context. Ask for a refresher on TCP and it opens with "the NIC bitrate does *not* change," because yesterday you thought slow start was a physical rate limit.

## How we built it

- **Chrome extension** (derived from the open-source Onhand project, disclosed below): page/PDF context capture, anchored highlights, Learning Mode checks, client-side agent loop.
- **Thread service on Cloud Run** (FastAPI): an OpenAI-compatible facade the extension already speaks. It injects the learner model into every tutoring request, streams **Gemini 3.6 Flash (via Vertex AI)** responses back, and tees each completed turn to the learner-model agent. A **global Application Load Balancer** (serverless NEG + Google-managed TLS) fronts the service.
- **Learner-model agent (Google ADK)**: an LLM agent with tools (`upsert_concept`, `set_preference`, `note_no_update`) that runs after each turn and each resolved check. It is deliberately an agent, not a heuristic — deciding whether a wrong answer is a slip, a shaky concept, or a genuine misconception is a judgment call.
- **Firestore**: the persistent learner model — concepts with status (encountered/solid/shaky/misconception), evidence counts, teaching preferences, check statistics, and a full event audit trail — keyed by an anonymous device token, durable across sessions and devices.

## How it differs from upstream Onhand

Upstream Onhand *records* learning events; Thread adds an agent that *interprets* them. Base Onhand logs concepts and graded checks into per-session browser state. Thread's ADK agent runs after each turn as an independent judge: it distinguishes slips from misconceptions, accumulates evidence across phrasings, captures beliefs embedded in how a question was *asked* (no check required), and can decline to write at all. The result is a longitudinal model of the learner — not the session — injected server-side into every future model call, so a brand-new conversation on a new device still knows you.

## Challenges we ran into

- **Gemini 3.6 thought signatures**: replayed tool calls must carry the `thought_signature` Gemini emitted, but OpenAI-compatible clients drop it. The service caches signatures per tool-call id and re-attaches them transparently.
- **Strict OpenAI-compat validation**: Gemini 400s on any unknown request field (e.g. `store`), so the facade forwards an allowlist.
- **A platform bug**: our fresh project's `*.run.app` URLs 404'd at Google's edge despite Ready=True and correct IAM — we fronted Cloud Run with a global ALB + serverless NEG, which both fixed routing and upgraded the architecture.
- **Distillation timing**: an agent turn spans several model calls (tool rounds produce no text), so the service consumes a turn only when a call actually yields tutoring text.

## What we learned

Memory is a judgment problem, not a storage problem — the interesting design work was deciding *what deserves to be remembered*, which is exactly why the memory-writer is an ADK agent with tools rather than a database write. We also learned more than we expected about Gemini's OpenAI-compat surface, thought signatures, and Cloud Run networking.

## What's next

Spaced-repetition review driven by the learner model, a learner-facing "what Thread believes about me" dashboard with corrections (feedback the agent must honor), and multi-subject concept graphs.

## Pre-existing work disclosure

The extension derives from [Onhand](https://github.com/Phineas1500/Onhand) (Apache-2.0), base commit `7a4078e`. Built new during the submission period: the entire Thread service (Gemini facade, ADK learner-model agent, Firestore memory, Cloud Run + load-balancer deployment) and the extension's Thread provider + learning-event sync.
```

**Built with** (tags, ≤25):
`gemini` `google-adk` `vertex-ai` `cloud-run` `firestore` `cloud-load-balancing` `secret-manager` `cloud-build` `artifact-registry` `python` `fastapi` `typescript` `chrome-extension` `node.js` `esbuild`

**Try it out links**:
- `https://github.com/Phineas1500/onhand-thread` (code + spin-up instructions)
- `https://8-233-210-178.sslip.io/healthz` (live backend on Google Cloud)

**Image gallery** (≤15, 3:2): side-panel screenshots (tutoring turn, a learning
check), Firestore console showing a learner doc with a `misconception` entry,
`docs/architecture.png`, Cloud Run service page.

**Video demo link**: upload the ≤4-min demo to YouTube (public, English,
unedited live run, Google Cloud consoles visible) and paste the URL.

## Step 3 — Additional info (judges only)

- **Sponsor / Special Prizes (Startup Excellence)**: leave unchecked (incorporated orgs only).
- **Submitter Type**: Individuals
- **Submitter country of residence**: United States *(confirm)*
- **Category**: **Collaborative Partner**
- **Organization name**: blank
- **Start date** (MM-DD-YY): `08-30-26`
- **Repo URL**: `https://github.com/Phineas1500/onhand-thread`
- **Reproducible Testing instructions in README?**: **Yes**
- **Hosted project URL**: `https://8-233-210-178.sslip.io`
- **Testing instructions** (judges, optional):

```
1. Live backend (Cloud Run behind a global ALB): https://8-233-210-178.sslip.io/healthz → {"ok":"true","memory":"firestore"}
2. Extension: clone the repo, `npm ci && npm run build:extension`, then load `packages/browser-extension/` unpacked at chrome://extensions (Chrome 116+). The deployed backend is baked in — no configuration needed.
3. Open any article, open the side panel (Cmd+Shift+Space), ask about the page. Learning Mode is on; answer the checks it opens.
4. Inspect your persistent learner model: `curl https://8-233-210-178.sslip.io/v1/learner -H "Authorization: Bearer <token>"` where <token> is chrome.storage.local.onhandThreadToken (visible in the extension service-worker console). Get a check wrong, wait ~15s, fetch again — the ADK agent records the misconception; open a new conversation and watch the tutoring adapt.
```

- **Which Google SDK**: check **Agent Development Kit (ADK)** and **Google GenAI SDK (google-genai)** (ADK runs the learner-model agent; google-genai underneath it).
- **Which Google Cloud Service(s)**: check **Cloud Run** and **Firestore**.
- **Architecture diagram**: upload `docs/architecture.png`.
- **Startup Prize fields**: blank (not incorporated).
- **Which Google AI Models**: `Gemini 3.6 Flash, accessed through Vertex AI` (satisfies the "3.5 or newer" requirement).
- **Bonus content link** (optional): a short blog post would qualify — it must be public and state it was created for this hackathon.
- **Bonus social post** (optional) — draft, must keep the hashtag:

> Built Onhand Thread for the #AllThingsAgentic Hackathon: a browser tutor that remembers how you learn. A Google ADK agent distills your reading, checks, and mistakes into a persistent Firestore learner model, so Gemini teaches you differently tomorrow than it did today. https://github.com/Phineas1500/onhand-thread

## ⚠️ Deadline

The form's countdown showed **"9 more hours to deadline"** (~9:00 AM PT Aug 31?) — tighter than the "5:00 PM PDT" on the overview page. Trust the form's countdown; record and submit early.
