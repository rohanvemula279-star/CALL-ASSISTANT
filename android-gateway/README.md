# Rohan Assistant Gateway (Android)

A tiny Android companion app that turns your phone into a SIP-less missed-call
reporter. It watches `PHONE_STATE` broadcasts in the background; if an
incoming call isn't picked up within 20 seconds, it POSTs the caller number,
contact name, and timestamp to your FastAPI server's `/incoming-call` endpoint.

This is the **cheapest gateway**: no SIP trunk, no Asterisk, no public IP.
The call itself is *not* answered by the AI — it just reports what your
phone already knows, and the server can decide whether to call the user
back, send a WhatsApp/SMS, queue a follow-up, etc.

For the **full self-hosted AI voice conversation** see `../asterisk-full/`.

---

## How it works

```
Caller -> Android (Airtel SIM) -> CallStateReceiver
                                     |
                              20s timer (no pickup)
                                     |
                          POST /incoming-call
                                     v
                       FastAPI (your PC) -> Ollama / Whisper / Piper
```

* `RINGING` starts a coroutine that waits 20 s.
* `OFFHOOK` (user answered) cancels the coroutine.
* If the timer fires first, the app POSTs to your server with the caller
  number, contacts-resolved name, and timestamp.

---

## Build & install

Prereqs: Android Studio Hedgehog+ (or just `gradle` CLI), JDK 17, Android
SDK 34, an Android 7+ device.

```bash
cd android-gateway
gradle :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Or open the folder in Android Studio and click Run.

---

## Configure the server URL

Either:

1. Open the app and paste the URL (e.g. `http://192.168.1.20:8000`).
2. Override at install time:

```bash
adb shell setprop rohan.assistant.server http://192.168.1.20:8000
```

`network_security_config.xml` already permits cleartext to `10.0.2.2`,
`localhost`, and `127.0.0.1`. To reach your PC over Wi-Fi, add your
PC's LAN IP under `<domain>` in that file before building.

---

## Permissions

The app requests on first start:

| Permission                | Why                                           |
| ------------------------- | --------------------------------------------- |
| `READ_PHONE_STATE`        | Receive `PHONE_STATE` broadcasts              |
| `READ_CONTACTS`           | Resolve caller number to a name               |
| `POST_NOTIFICATIONS`      | Required for the foreground service on 13+    |
| `INTERNET`                | Send POST requests to your server             |
| `FOREGROUND_SERVICE`      | Keep the watcher alive in the background      |
| `FOREGROUND_SERVICE_PHONE_CALL` | Android 14+ foreground service type tag |

The app is **not** a phone-call replacement — it just observes.

---

## Server endpoint

`POST /incoming-call` on your FastAPI server. Example payload:

```json
{
  "number": "+919876543210",
  "name": "Rohan's Mom",
  "timestampMs": 1717490000000,
  "callId": "6f1c4d4e-...",
  "device": "Pixel 7"
}
```

Suggested minimal handler:

```python
from fastapi import FastAPI, BackgroundTasks
import httpx, time

app = FastAPI()
WAIT = {}  # call_id -> ts (optional: dedupe)

@app.post("/incoming-call")
async def incoming_call(req: dict, bg: BackgroundTasks):
    if req["callId"] in WAIT and time.time() - WAIT[req["callId"]] < 60:
        return {"ok": True, "message": "duplicate"}
    WAIT[req["callId"]] = time.time()
    bg.add_task(handle_missed_call, req)
    return {"ok": True, "message": "queued"}

async def handle_missed_call(req: dict):
    # Plug in: call the caller back via SIP, send a WhatsApp, etc.
    pass
```
