#!/usr/bin/env bash
# Deploy an already-built image to a Render service through its deploy hook, then wait until it is healthy.
# Inputs (environment): DEPLOY_HOOK (secret URL), IMAGE (full image reference), BASE_URL (public URL of the service).
set -euo pipefail

: "${DEPLOY_HOOK:?DEPLOY_HOOK secret is not set for this environment}"
: "${IMAGE:?IMAGE is not set}"
: "${BASE_URL:?BASE_URL variable is not set for this environment}"

encoded="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$IMAGE")"
sep="&"
case "$DEPLOY_HOOK" in *\?*) ;; *) sep="?" ;; esac

echo "Deploying ${IMAGE} to ${BASE_URL}"
curl --fail --silent --show-error -X POST "${DEPLOY_HOOK}${sep}imgURL=${encoded}" > /dev/null
echo "Deploy triggered. Waiting for ${BASE_URL}/ready ..."

for attempt in $(seq 1 60); do
  if curl --fail --silent --max-time 10 "${BASE_URL%/}/ready" > /dev/null; then
    echo "Healthy after ${attempt} checks."
    curl --silent --max-time 10 "${BASE_URL%/}/health"
    echo
    exit 0
  fi
  sleep 10
done

echo "Service did not become healthy within 10 minutes. Use the Rollback workflow to restore the previous image." >&2
exit 1
