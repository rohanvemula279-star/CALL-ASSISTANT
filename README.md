# AI Phone Assistant

A complete Python/FastAPI service that turns a phone call into a real-time
voice conversation with a local LLM. Architecture:

```
Caller → Asterisk → FastAPI → Whisper (STT)
                              ↓
                           Ollama (minimax-m3)
                              ↓
                           Piper (TTS)
                              ↓
                       FastAPI → Asterisk → Caller
```

## Two paths — pick one

1. **Cheapest, no SIP, no Twilio, no Vapi** — your Android phone is the gateway.
   The companion app watches your Airtel SIM and posts missed calls to FastAPI,
   which generates a reason via Ollama and pings you on Telegram. Works today
   with hardware you already have. See **[docs/MISSED_CALL_TELEGRAM.md](docs/MISSED_CALL_TELEGRAM.md)**.
2. **Full self-hosted AI voice conversation** — your laptop runs Asterisk +
   FastAPI + Whisper + Ollama + Piper and actually talks to the caller.
   See **[asterisk-full/](asterisk-full/)** and
   **[asterisk-full/docs/WINDOWS_INSTALL.md](asterisk-full/docs/WINDOWS_INSTALL.md)**.

## Stack

- **Python 3.11**
- **FastAPI** for the HTTP API
- **Ollama** with the local `minimax-m3` model for inference
- **Whisper** for speech-to-text
- **Piper** for text-to-speech
- **SQLite** (via `aiosqlite`) for conversation history
- **structlog** for structured logging
- **Docker / docker-compose** for deployment

## Project structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI factory + lifespan
│   ├── config.py              # Pydantic settings (env-driven)
│   ├── dependencies.py        # Tiny DI container
│   ├── logger.py              # structlog setup
│   ├── models/schemas.py      # Pydantic request/response models
│   ├── routers/
│   │   ├── chat.py            # POST /chat
│   │   ├── transcribe.py      # POST /transcribe
│   │   ├── speak.py           # POST /speak
│   │   └── meta.py            # GET /health, /history
│   ├── services/
│   │   ├── ollama_client.py   # Ollama HTTP client (generate + chat)
│   │   ├── whisper_service.py # Whisper STT wrapper
│   │   └── piper_service.py   # Piper TTS wrapper (SDK + CLI)
│   └── storage/
│       └── store.py           # SQLite conversation store
├── asterisk/
│   ├── extensions.conf        # Sample dialplan
│   └── README.md
├── logs/                      # Created at runtime
├── storage/                   # SQLite + TTS output (gitignored)
├── models/                    # Piper voice models (gitignored)
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── requirements.txt
├── .env.example
└── README.md
```

## API

### `POST /transcribe`

Upload an audio file. Returns the transcript.

```bash
curl -X POST -F "audio=@sample.wav" -F "language=en" http://localhost:8000/transcribe
```

Response:

```json
{
  "text": "Hi, I'd like to check my order status.",
  "language": "en",
  "duration": 3.42,
  "segments": [ ... ]
}
```

### `POST /chat`

Text in, text out. Pass `call_id` to keep history across turns.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
        "call_id": "abc-123",
        "caller": "+15551234567",
        "message": "Hi, what can you help me with?"
      }'
```

Response:

```json
{
  "call_id": "abc-123",
  "reply": "I can help with orders, scheduling, and account questions.",
  "model": "minimax-m3",
  "latency_ms": 412.7
}
```

### `POST /speak`

Synthesize text to a WAV file on disk. Returns a URL to stream it.

```bash
curl -X POST http://localhost:8000/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, thanks for calling!", "voice": "en_US-amy-medium", "speed": 1.0}'
```

Response:

```json
{
  "audio_path": "/app/storage/tts/speech_ab12cd34.wav",
  "audio_url": "/storage/tts/speech_ab12cd34.wav",
  "duration_estimate": 1.83,
  "voice": "en_US-amy-medium"
}
```

### `GET /health`

Service status for Ollama, Whisper, and Piper.

### `GET /history/{call_id}` and `GET /history`

Recent conversation history.

## Setup

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env as needed
```

### 2. Run with Docker Compose (recommended)

```bash
docker compose up --build
```

On first start this will:

1. Start Ollama and pull `minimax-m3` (via the `ollama-puller` sidecar).
2. Boot the FastAPI app, which waits for Ollama, then preloads the Whisper
   and Piper models.
3. Optionally start the Asterisk container with the sample dialplan.

### 3. Run locally (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Make sure Ollama is running locally and the model is pulled:
ollama serve &
ollama pull minimax-m3

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment variables

All settings live in `.env` (see `.env.example` for the full list):

| Key               | Default                         | Purpose                          |
| ----------------- | ------------------------------- | -------------------------------- |
| `OLLAMA_HOST`     | `http://localhost:11434`        | Ollama server URL                |
| `OLLAMA_MODEL`    | `minimax-m3`                    | Model name                       |
| `WHISPER_MODEL`   | `base`                          | `tiny`/`base`/`small`/`medium`   |
| `WHISPER_DEVICE`  | `cpu`                           | `cpu` or `cuda`                  |
| `PIPER_VOICE`     | `en_US-amy-medium`              | Piper voice ID                   |
| `SQLITE_PATH`     | `./storage/conversations.db`    | Conversation history file        |
| `LOG_LEVEL`       | `info`                          | Standard Python log levels       |

## Asterisk integration

A minimal dialplan is in `asterisk/extensions.conf`. The production flow is:

1. Caller dials in → SIP channel lands in `[ai-inbound]`.
2. Asterisk records a short utterance to disk.
3. A shell command (or AGI) `POST`s the WAV to `/transcribe`.
4. The transcript is `POST`ed to `/chat` along with the `call_id`.
5. The reply is `POST`ed to `/speak` and the resulting WAV is played back.
6. Loop.

For low latency, prefer AGI/Ari over `System()` calls.

## Logging

Logs are written to:

- `stdout` (structured via `structlog`)
- `logs/app.log` (same payload, file-friendly)

Each line is JSON-ish key/value text, e.g.:

```
2026-06-04T12:34:56 [info] app.ready port=8000
2026-06-04T12:35:01 [info] ollama.connected host=http://ollama:11434 model=minimax-m3
2026-06-04T12:35:14 [error] chat.ollama_failed error=...
```

## Error handling

- Ollama failures: retried up to 3× with exponential backoff, surfaced as `502`.
- Whisper/Piper failures: surfaced as `500` with the underlying message.
- A global `unhandled` exception handler logs the trace and returns `500`.
- Empty uploads, bad limits, etc., return `400`/`503` as appropriate.

## License

MIT.
