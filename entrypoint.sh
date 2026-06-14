#!/bin/sh
set -e

# Optionally wait for Ollama to be reachable
if [ -n "$OLLAMA_HOST" ]; then
    echo "Waiting for Ollama at $OLLAMA_HOST ..."
    OLLAMA_URL=${OLLAMA_HOST%/}
    until curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; do
        sleep 2
    done
    echo "Ollama is reachable."
fi

# Pre-download Whisper model on first start (optional)
if [ "$WHISPER_PRELOAD" = "true" ]; then
    echo "Preloading Whisper model: $WHISPER_MODEL"
    python -c "import whisper; whisper.load_model('$WHISPER_MODEL')" || \
        echo "Whisper preload skipped"
fi

# Pre-download Piper voice
if [ "$PIPER_PRELOAD" = "true" ] && [ -n "$PIPER_VOICE" ]; then
    echo "Ensuring Piper voice: $PIPER_VOICE"
    python -c "import piper; piper.download_voices(['$PIPER_VOICE'])" 2>/dev/null || \
        echo "Piper voice preload skipped"
fi

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-1}" \
    --log-level "${LOG_LEVEL:-info}"
