# Demo setup — Onhand Thread

## One-time

1. Build the extension: `npm ci && npm run build:extension`
2. Open `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and pick `packages/browser-extension/`.
3. Open the Onhand Thread side panel (puzzle icon → Onhand Thread, or Cmd+Shift+Space). The deployed Cloud Run URL is baked in as the default; to point at a different backend, set it from the extension's service-worker console:
   ```js
   chrome.storage.local.set({ onhandThreadBaseUrl: "https://<service-url>/v1" })
   ```
4. First request auto-registers an anonymous learner token (`chrome.storage.local.onhandThreadToken`). To demo "fresh learner", remove that key; to demo cross-session memory, keep it.

## Inspecting the learner model live

- Firestore console: https://console.cloud.google.com/firestore/databases/-default-/data/panel/learners?project=onhand-507204
- Or via API: `curl https://<service-url>/v1/learner -H "Authorization: Bearer $(token)"` — the token from `chrome.storage.local.onhandThreadToken`.
- Learner-agent decisions: `gcloud run services logs read onhand-thread --region us-east1 | grep distill`

## Demo beats (see submission.md for the timed script)

1. Read an article with Learning Mode on; ask a question that carries a misconception.
2. Show Firestore: concept recorded as `misconception` with the specific wrong belief.
3. Answer a learning check; show the concept upgrade + stats change.
4. New session ("next day"): ask for a refresher — the tutor pre-empts the recorded misconception unprompted.
