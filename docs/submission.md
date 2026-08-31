# Devpost submission draft — Onhand Thread

**Category:** Collaborative Partner
**Tagline:** A browser tutor that turns your reading, mistakes, and feedback into a persistent learning memory.

## Inspiration

Every AI tutor has amnesia. You can spend an evening working through TCP congestion control with an assistant, reveal exactly which idea you're confused about — and tomorrow it re-explains everything from zero, including the parts you had mastered. Human tutors are valuable precisely because they remember *you*: what you've seen, what you got wrong, and how you like things explained.

## What it does

Onhand Thread is a Chrome extension tutor that lives beside any webpage or PDF. As you study, it explains, anchors answers to the source with highlights, and opens learning checks (prediction/retrieval questions). What's new: every exchange and every check result flows to a **learner-model agent** (Google ADK + Gemini) that decides what the moment revealed about you — a misconception, a solidified concept, a teaching preference — and writes that judgment into a **persistent Firestore learner model**.

The next time you open the tutor — new tab, new day, new topic — Gemini teaches with that model in context. Ask for a refresher on TCP and it opens with "the NIC bitrate does *not* change," because last week you thought slow start was a physical rate limit.

## How we built it

- **Chrome extension** (derived from the open-source Onhand project, disclosed below): page/PDF context capture, anchored highlights, Learning Mode checks, client-side agent loop.
- **Thread service on Cloud Run** (FastAPI): an OpenAI-compatible facade the extension already speaks. It injects the learner model into every tutoring request, streams Gemini 3.6 Flash responses back, and tees each completed turn to the learner-model agent.
- **Learner-model agent (Google ADK 2.8)**: an LLM agent with tools (`upsert_concept`, `set_preference`, `note_no_update`) that runs after each turn and each resolved check. It is deliberately an agent, not a heuristic — deciding whether a wrong answer is a slip, a shaky concept, or a genuine misconception is a judgment call.
- **Firestore**: the persistent learner model — concepts with status (encountered/solid/shaky/misconception), evidence counts, teaching preferences, check statistics, and a full event audit trail — keyed by an anonymous device token, durable across sessions.

## Challenges

- Gemini 3.6 requires `thought_signature` on replayed tool calls; OpenAI-compatible clients drop it. The service caches signatures per tool-call id and re-attaches them transparently.
- Distilling at the right moment: an agent turn spans several model calls (tool rounds produce no text), so the service consumes a turn id only when a call actually yields tutoring text.

## What's pre-existing vs. new

The extension UI and browsing machinery derive from [Onhand](https://github.com/Phineas1500/Onhand) (Apache-2.0), base commit `7a4078e`. Built new during the submission period: the entire Thread service (Gemini facade, ADK learner-model agent, Firestore memory, Cloud Run deployment) and the extension's Thread provider + learning-event sync.

## Demo script (4 min)

1. (0:00) The amnesia problem, one sentence. Open a TCP article, ask a question that reveals the NIC-bitrate misconception.
2. (0:45) Tutor corrects it; show the Firestore console: the agent has recorded `tcp-slow-start: misconception` with the specific wrong belief.
3. (1:30) Answer a learning check correctly; show the model upgrade to `solid` and stats update — the agent's tool calls in Cloud Run logs.
4. (2:15) Fresh session (or second device, same token): ask for a refresher. The tutor pre-empts the old misconception unprompted and skips what's solid.
5. (3:00) Architecture slide: extension → Cloud Run → Gemini + ADK agent → Firestore. Close on "a tutor that's different tomorrow because of what you did today."

## Submission checklist

- [ ] Public repo with README + reproducible setup
- [ ] Architecture diagram (image for Devpost)
- [ ] ~4 min public demo video (YouTube/Vimeo)
- [ ] Deployed Cloud Run URL live at judging time
- [ ] Devpost form: category = Collaborative Partner, Google tech used = Gemini, ADK, Cloud Run, Firestore
