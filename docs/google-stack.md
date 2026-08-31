# Google products used in Onhand Thread

How each Google technology is used, where it lives in the code, and how the
project satisfies the All Things Agentic Hackathon technology requirements.

## Hackathon requirement mapping

| Requirement | What we use |
|---|---|
| "Gemini 3.5 or newer accessed through Gemini API or Vertex AI" | **Gemini 3.6 Flash via Vertex AI** — powers both the tutoring conversation and the learner-model agent |
| "At least one Google Agent Framework (Google ADK, GenAI SDK, Antigravity SDK or GenKit)" | **Google ADK 2.8** (learner-model agent) — with the **GenAI SDK** underneath it |
| "At least one Google Cloud infrastructure service" | **Cloud Run** and **Firestore** (both named examples in the rules), plus Cloud Load Balancing, Secret Manager, Cloud Build, Artifact Registry |

## Product-by-product

### Gemini 3.6 Flash (via Vertex AI)
The model behind both lanes. The tutor lane streams Gemini responses to the
extension through an OpenAI-compatible facade; the learner-model agent uses
Gemini to judge what each exchange reveals about the learner.
Code: `backend/app/gemini_proxy.py` (tutor lane), `backend/app/learner_agent.py`
(agent model). Vertex is the production path (`ONHAND_THREAD_USE_VERTEX=1`):
requests hit Vertex AI's OpenAI-compatible endpoint and authenticate with the
Cloud Run service account via Application Default Credentials — no API keys in
production.

### Google ADK (Agent Development Kit) 2.8
Runs the **learner-model agent**: a genuine LLM agent (not a heuristic) with
three tools — `upsert_concept`, `set_preference`, `note_no_update` — that
executes after every tutoring turn and every resolved learning check, and
decides what is worth remembering about the learner (a slip vs. shaky
understanding vs. a specific misconception). Code: `backend/app/learner_agent.py`
(`Agent`, `Runner`, `InMemorySessionService` from `google.adk`).

### Vertex AI
Model serving for everything above. Selected over the Gemini Developer API so
model usage bills to the GCP project and authenticates via IAM
(`roles/aiplatform.user` on the service account) instead of API keys.
Configured in `backend/deploy.sh` env vars (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`,
`GOOGLE_CLOUD_LOCATION=global`).

### Cloud Run
Hosts the Thread service (`backend/`, FastAPI + uvicorn, deployed from source
with the included `Dockerfile`). Scale-to-zero; the service account carries the
IAM grants for Vertex AI, Firestore, and Secret Manager. Deploy:
`backend/deploy.sh`.

### Firestore (Native mode)
The persistent learner model — the heart of the project. One document per
learner (`learners/{learner_id}`): concepts with status
(encountered / solid / shaky / misconception), evidence counts, teaching
preferences, and check statistics; plus an `events` subcollection holding the
audit trail of every distilled observation and the agent's tool calls. Keyed by
an anonymous device token so memory survives across sessions and devices.
Code: `backend/app/memory.py`.

### Cloud Load Balancing
A global external Application Load Balancer with a serverless NEG fronts the
Cloud Run service (`backend/loadbalancer.sh`), with a Google-managed TLS
certificate. (It also works around a platform issue where this fresh project's
`*.run.app` hostnames 404 at Google's edge despite the service being Ready.)
Public endpoint: `https://8-233-210-178.sslip.io`.

### Secret Manager
Holds the Gemini API key used in the non-Vertex development path. Production
uses ADC, so no secret material flows through the model lane there.

### Cloud Build + Artifact Registry
`gcloud run deploy --source` builds the container with Cloud Build and stores
images in Artifact Registry (`cloud-run-source-deploy` repository).

## Compliance notes (submission rules)

- **Built during the submission period / pre-existing work disclosed:** the
  extension derives from the open-source [Onhand](https://github.com/Phineas1500/Onhand)
  project (Apache-2.0, base commit `7a4078e`), disclosed in the README and to be
  disclosed on the Devpost form. Everything in `backend/` and the extension's
  Thread provider integration is new work from the submission period —
  the project "enhances and builds upon" the underlying open-source product as
  the rules require.
- **Repo:** public — https://github.com/Phineas1500/onhand-thread
- **Architecture diagram:** `docs/architecture.png`
- **Demo video:** must show unedited live execution **and visible proof the
  backend runs on Google Cloud** — keep the Cloud Run service page, its logs,
  and the Firestore console on screen during the demo (script in
  `docs/submission.md`).
- **Spin-up instructions:** in the top-level `README.md`.
