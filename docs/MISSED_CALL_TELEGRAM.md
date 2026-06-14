# Missed-Call → Telegram (no SIP, no Twilio, no Vapi)

This is the working architecture. It uses only:

- The **Airtel SIM** in your Android phone (no changes to carrier).
- The **Android companion app** (already built in `../android-gateway/`).
- A **Windows laptop** running the FastAPI service.
- **Ollama** (`minimax-m3`) for the AI summary.
- **Telegram** to deliver the notification to you.

```
                    Airtel SIM
                        │
                  Call rings on phone
                        │
              (user answers? ── yes ──▶ nothing happens)
                        │ no (20s elapse)
                        ▼
        Android app (CallStateReceiver)
          ├─ gets caller number (broadcast + CallLog fallback)
          ├─ resolves contact name
          └─ POST /incoming-call  ──▶  FastAPI (laptop)
                                              │
                                ┌─────────────┼─────────────┐
                                ▼             ▼             ▼
                          Persist in    Ollama (minimax-m3) Piper TTS
                            SQLite        "possible reason"   (audio URL)
                                │             │             │
                                └─────────────┼─────────────┘
                                              ▼
                                    Telegram Bot API
                                              ▼
                                    Your phone (Telegram app)
                                    ┌──────────────────────────┐
                                    │ 📞 Missed Call            │
                                    │                          │
                                    │ Name: Rahul              │
                                    │ Number: +91XXXXXXXXXX    │
                                    │ Time: 4:35 PM            │
                                    │                          │
                                    │ Possible reason:         │
                                    │ Project discussion       │
                                    │ regarding internship.    │
                                    └──────────────────────────┘
```

## How it solves every blocker

| Blocker                              | How we handle it                                          |
| ------------------------------------ | --------------------------------------------------------- |
| Auto-answer a phone call             | Not needed — we let it ring and report after 20 s         |
| `EXTRA_INCOMING_NUMBER` blank/10+    | Fall back to `CallLog` provider query                     |
| Caller name                          | `ContactsContract.PhoneLookup` (already in app)           |
| App gets killed in background        | Foreground service of type `phoneCall`                    |
| Reachable from Android on Wi-Fi      | `GET /network/info` auto-discovery + firewall rule        |
| Notify the user on the go            | Telegram Bot API — free, no approval                      |
| Send to a number not in the phone    | Same — the name lookup is on the Android side             |
| Per-call dedupe                      | 60-second window per `call_id` on the server              |
| Cold start before user opens app     | First `PHONE_STATE` rebuilds the AppContext automatically  |

## One-time setup (10 minutes)

### 1. Create a Telegram bot

1. Open Telegram, message **@BotFather**.
2. Send `/newbot`, follow the prompts, copy the **bot token**.
3. Open a chat with your new bot, send `/start`.
4. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and note the
   `chat.id` (a negative number for a private chat).

### 2. Configure the laptop

Add to `C:\Users\rohan\call\.env`:

```
TELEGRAM_BOT_TOKEN=1234567890:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

Open the firewall for the FastAPI port:

```powershell
New-NetFirewallRule -DisplayName "FastAPI 8000" -Direction Inbound `
    -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```

### 3. Find your laptop's IP

```powershell
ipconfig
```

Look for the `IPv4 Address` under your active Wi-Fi adapter, e.g.
`192.168.1.20`.

### 4. Install the Android app

```bash
cd android-gateway
gradle :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Open the app, tap **Discover laptop on Wi-Fi** (it sweeps the LAN), or
paste `http://192.168.1.20:8000` manually. Tap **Start service**.

### 5. Verify the chain

1. `curl http://localhost:8000/health` — server up.
2. From a phone, call your Android phone, let it ring 20 s, hang up.
3. Check the Android logcat for `Server response: ok=true`.
4. Check your Telegram chat — you should see the notification.

## Endpoints (server)

| Method | Path                | Purpose                                  |
| ------ | ------------------- | ---------------------------------------- |
| POST   | `/incoming-call`    | Android app webhook                      |
| POST   | `/telegram/test`    | Send a test Telegram message             |
| GET    | `/network/info`     | Laptop's IP / base URLs                  |
| GET    | `/contacts/lookup`  | Server-side name lookup (best-effort)    |
| GET    | `/health`           | Service health                           |
| GET    | `/history/{call_id}`| Conversation log                         |

## Endpoints (Android)

| File                                  | Purpose                                  |
| ------------------------------------- | ---------------------------------------- |
| `receiver/CallStateReceiver.kt`       | Listens to `PHONE_STATE` broadcasts      |
| `service/CallTracker.kt`              | 20-second timer + fall-back to CallLog   |
| `service/GatewayForegroundService.kt` | Keeps the process alive                  |
| `util/LanDiscovery.kt`                | Sweeps the LAN for `/network/info`       |
| `util/CallLogResolver.kt`             | Recovers numbers masked by Android 10+   |
| `util/Contacts.kt`                    | Resolves phone → contact name            |

## What you can add later

- **SMS auto-reply** (laptop → Airtel SIM) — needs a GSM modem or
  Android-as-SMS-gateway. The summary field in the request is already
  a free-form string.
- **Calendar / WhatsApp peek** — populate `context` in the Android
  payload to enrich the Ollama summary.
- **Auto-call-back** — wire `asterisk-full/` in front of this for real
  voice conversations.
