#!/usr/bin/env bash
# Deploy an already-built image to a Render service through its deploy hook, then wait until THAT image is serving.
# Inputs (environment): DEPLOY_HOOK (secret URL), IMAGE (full image reference), BASE_URL (public URL of the service).
# Optional: WAIT_ATTEMPTS (default 60) and WAIT_SECONDS (default 10) between checks.
#
# "Healthy" is not enough: during a rollout the previous instance keeps answering /ready. The app reports the
# image tag it was built with in /health ({"version": "sha-..."}), so we wait until it equals the tag we deployed.
# Images built before that field existed cannot be verified and will time out; roll back to a newer tag.
set -euo pipefail

: "${DEPLOY_HOOK:?DEPLOY_HOOK secret is not set for this environment}"
: "${IMAGE:?IMAGE is not set}"
: "${BASE_URL:?BASE_URL variable is not set for this environment}"

tag="${IMAGE##*:}"
case "$tag" in
  ""|*[!A-Za-z0-9._-]*) echo "IMAGE must end in a plain tag such as :sha-1a2b3c4 (got '${IMAGE}')" >&2; exit 1 ;;
esac

encoded="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$IMAGE")"
sep="&"
case "$DEPLOY_HOOK" in *\?*) ;; *) sep="?" ;; esac

echo "Deploying ${IMAGE} to ${BASE_URL}"
curl --fail --silent --show-error -X POST "${DEPLOY_HOOK}${sep}imgURL=${encoded}" > /dev/null
echo "Deploy triggered. Waiting for ${BASE_URL} to report version ${tag} ..."

attempts="${WAIT_ATTEMPTS:-60}"
pause="${WAIT_SECONDS:-10}"
seen="(no answer yet)"

for attempt in $(seq 1 "$attempts"); do
  if body="$(curl --fail --silent --max-time 10 "${BASE_URL%/}/health")"; then
    seen="$(printf '%s' "$body" | head -c 200)"
    if printf '%s' "$body" | grep -Eq "\"version\" *: *\"${tag}\"" \
        && curl --fail --silent --max-time 10 "${BASE_URL%/}/ready" > /dev/null; then
      echo "Serving ${tag} and ready after ${attempt} checks."
      echo "$body"
      exit 0
    fi
  fi
  sleep "$pause"
done

echo "Service did not report version ${tag} and ready within $((attempts * pause)) seconds. Last /health answer: ${seen}" >&2
echo "Use the Rollback workflow to restore the previous image." >&2
exit 1
