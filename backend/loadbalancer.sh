#!/usr/bin/env bash
# Global external Application Load Balancer fronting the Cloud Run service.
#
# Why this exists: on this fresh project the default *.run.app URLs returned
# Google-edge 404s despite Ready=True, correct IAM, and ingress=all (a known
# platform issue: https://discuss.google.dev/t/-/381607). The LB's serverless
# NEG routes straight to the service and bypasses run.app hostname routing.
# HTTPS uses a Google-managed cert on a sslip.io name for the LB IP.
set -euo pipefail

PROJECT="${PROJECT:-onhand-507204}"
REGION="${REGION:-us-east1}"
SERVICE="${SERVICE:-onhand-thread}"

gcloud config set project "$PROJECT" >/dev/null
gcloud services enable compute.googleapis.com

gcloud compute addresses create onhand-thread-ip --global --ip-version=IPV4
IP=$(gcloud compute addresses describe onhand-thread-ip --global --format='value(address)')
HOST="${IP//./-}.sslip.io"

gcloud compute network-endpoint-groups create onhand-thread-neg \
  --region="$REGION" --network-endpoint-type=serverless --cloud-run-service="$SERVICE"
gcloud compute backend-services create onhand-thread-be --global --load-balancing-scheme=EXTERNAL_MANAGED
gcloud compute backend-services add-backend onhand-thread-be --global \
  --network-endpoint-group=onhand-thread-neg --network-endpoint-group-region="$REGION"
gcloud compute url-maps create onhand-thread-lb --default-service=onhand-thread-be

# HTTP :80
gcloud compute target-http-proxies create onhand-thread-http-proxy --url-map=onhand-thread-lb
gcloud compute forwarding-rules create onhand-thread-fr --global \
  --load-balancing-scheme=EXTERNAL_MANAGED --target-http-proxy=onhand-thread-http-proxy \
  --address=onhand-thread-ip --ports=80

# HTTPS :443 (managed cert; ~15-60 min to provision)
gcloud compute ssl-certificates create onhand-thread-cert --global --domains="$HOST"
gcloud compute target-https-proxies create onhand-thread-https-proxy \
  --url-map=onhand-thread-lb --ssl-certificates=onhand-thread-cert
gcloud compute forwarding-rules create onhand-thread-fr-https --global \
  --load-balancing-scheme=EXTERNAL_MANAGED --target-https-proxy=onhand-thread-https-proxy \
  --address=onhand-thread-ip --ports=443

echo "HTTP:  http://$IP"
echo "HTTPS: https://$HOST (once cert is ACTIVE)"
