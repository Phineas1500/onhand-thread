#!/usr/bin/env bash
# Deploy the Onhand Thread service to Cloud Run.
# Prereqs: gcloud auth login; GOOGLE_API_KEY set in the local environment.
set -euo pipefail

PROJECT="${PROJECT:-onhand-507204}"
REGION="${REGION:-us-east1}"
SERVICE="${SERVICE:-onhand-thread}"
SECRET_NAME="onhand-thread-google-api-key"
BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"

gcloud config set project "$PROJECT" >/dev/null

echo "== Enabling APIs =="
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com firestore.googleapis.com \
  secretmanager.googleapis.com

echo "== Firestore database (native mode) =="
if ! gcloud firestore databases describe --database='(default)' >/dev/null 2>&1; then
  gcloud firestore databases create --location="$REGION" --database='(default)'
else
  echo "already exists"
fi

echo "== Gemini API key -> Secret Manager =="
if ! gcloud secrets describe "$SECRET_NAME" >/dev/null 2>&1; then
  printf '%s' "${GOOGLE_API_KEY:?set GOOGLE_API_KEY in your environment}" |
    gcloud secrets create "$SECRET_NAME" --data-file=-
else
  echo "secret already exists (delete it to rotate)"
fi

echo "== IAM for the default compute service account =="
# New GCP projects no longer grant these by default: source builds need the
# builder role; the running service reads the secret and writes Firestore.
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for role in roles/cloudbuild.builds.builder roles/datastore.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$COMPUTE_SA" --role="$role" --condition=None >/dev/null
done
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --member="serviceAccount:$COMPUTE_SA" \
  --role=roles/secretmanager.secretAccessor >/dev/null

echo "== Deploying to Cloud Run =="
gcloud run deploy "$SERVICE" \
  --source "$BACKEND_DIR" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT,ONHAND_THREAD_TUTOR_MODEL=gemini-3.6-flash,ONHAND_THREAD_DISTILL_MODEL=gemini-3.6-flash" \
  --set-secrets "GOOGLE_API_KEY=$SECRET_NAME:latest"

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')
echo
echo "Deployed: $URL"
echo "Extension base URL to configure: $URL/v1"
echo "Smoke test: curl $URL/healthz"
