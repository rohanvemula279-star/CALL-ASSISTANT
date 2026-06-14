# Self-Hosted Telephony Stack

This directory contains a complete, production-shaped Asterisk + FastAPI
deployment for an AI phone assistant that **actually talks to the caller**:

```
Caller
  └─ PSTN / SIP trunk / GSM gateway
        └─ PJSIP endpoint (Asterisk)
              └─ Dialplan: [ai-inbound]
                    ├─ Record (up to 8s, ends on silence)
                    ├─ POST /transcribe (Whisper)
                    ├─ POST /chat       (Ollama minimax-m3)
                    ├─ POST /speak      (Piper)
                    └─ ControlPlayback the returned WAV
```

## Contents

```
asterisk-full/
├── config/                Asterisk config files
│   ├── pjsip.conf         SIP endpoints (rohan-phone, ai-bridge)
│   ├── extensions.conf    Dialplan with the AI loop
│   ├── manager.conf       AMI credentials
│   ├── modules.conf       Module autoload list
│   └── voicemail.conf     Stub
├── agi/                   AGI scripts called by the dialplan
│   ├── ai_agi.py          Python AGI entrypoint
│   └── ai_call.sh         curl wrapper
├── docker/                Dockerized Asterisk + compose file
│   ├── Dockerfile
│   └── docker-compose.yml
└── docs/
    └── WINDOWS_INSTALL.md Native install + Docker guide
```

## Quick start (Docker)

```bash
cd docker
docker compose up --build
```

Then call your softphone (Linphone) at `*91*` to test.

## Quick start (native)

See `docs/WINDOWS_INSTALL.md` for the Windows 11 step-by-step.

## Call flow (full)

```
Caller
   │
   ▼
[GSM gateway / SIP trunk]
   │  SIP INVITE
   ▼
PJSIP endpoint "rohan-phone"  ────────►  [ai-inbound] dialplan
                                                │
                                                ▼
                                       Record(${UNIQUEID}.wav)
                                                │
                                                ▼
                                       curl POST /transcribe
                                                │
                                                ▼
                                       curl POST /chat
                                                │
                                                ▼
                                       curl POST /speak
                                                │
                                                ▼
                                       wget audio_path.wav
                                                │
                                                ▼
                                       ControlPlayback(...)
                                                │
                                                ▼
                                          loop ↻
```

The same FastAPI service from `../app/` is used; no extra service is
required.

## Configuration touch-ups

- `pjsip.conf` — change `CHANGEME_PHONE_PASSWORD`, `YOUR_LAPTOP_IP`,
  and `PUBLIC_IP` for your environment.
- `extensions.conf` — the `[ai-inbound]` context is the entry point.
- `manager.conf` — change `CHANGEME_AMI_PASSWORD` and restrict the
  `permit` line to your AGI host.

## Notes

- The current dialplan uses `System()` calls to `curl` for simplicity.
  Production deployments should migrate to `AGI(ai_agi.py)` (already
  provided) for cleaner environment handling.
- This stack is fully self-hosted; no SaaS dependencies.
