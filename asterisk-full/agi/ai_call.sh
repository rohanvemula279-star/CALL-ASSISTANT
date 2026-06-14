#!/bin/sh
# Resilient curl wrapper used by the dialplan to call the FastAPI service.
# Usage:   ai_call.sh <method> <path> [json-body | @file]
# Example: ai_call.sh POST /chat '{"message":"hi"}'
#
# Writes the body (or the path to a generated audio file) to stdout.

set -eu

METHOD="${1:-GET}"
URL="${AIAPP_URL:-http://app:8000}${2:-/}"
BODY="${3:-}"

case "$METHOD" in
    POST)
        if [ "${BODY#@}" != "$BODY" ]; then
            curl -fsS -X POST -F "audio=@${BODY#@}" "$URL"
        else
            curl -fsS -X POST -H 'Content-Type: application/json' -d "$BODY" "$URL"
        fi
        ;;
    GET)
        curl -fsS "$URL"
        ;;
    *)
        echo "unknown method: $METHOD" >&2
        exit 2
        ;;
esac
