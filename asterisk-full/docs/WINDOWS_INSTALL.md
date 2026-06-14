# Windows Installation Guide — Self-Hosted AI Phone Assistant

This guide walks you through running the **full** voice-conversation stack
on Windows 11 (your Airtel SIM, your laptop) using:

- **Asterisk** (PJSIP softswitch)
- **FastAPI** (Python 3.11)
- **Whisper** (STT)
- **Ollama** with `minimax-m3`
- **Piper** (TTS)

There are two recommended paths. **Path B (Docker)** is the easiest.

---

## Path A — Native Windows install

Use this if you want to learn the internals or run outside Docker.

### 1. Install prerequisites

- **WSL2** (Ubuntu 22.04) — `wsl --install` from an elevated PowerShell
- **Python 3.11** — https://www.python.org/downloads/windows/
- **Ollama** — https://ollama.com/download/windows
- **Visual Studio Build Tools** — for compiling `openai-whisper`
- **Git for Windows**

### 2. Build the AI side (WSL2)

```bash
# In WSL
git clone <your-repo> ~/ai-phone && cd ~/ai-phone
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama serve &
ollama pull minimax-m3
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Install Asterisk on WSL2

```bash
sudo apt update && sudo apt install -y build-essential \
  libssl-dev libxml2-dev libncurses5-dev uuid-dev \
  libsqlite3-dev libjansson-dev libcurl4-openssl-dev \
  libpjsip-dev libsrtp2-dev

wget https://downloads.asterisk.org/pub/telephony/asterisk/asterisk-20-current.tar.gz
tar xzf asterisk-20-current.tar.gz
cd asterisk-20.*
./configure --with-pjproject-bundled
make -j$(nproc) menuselect.makeopts
menuselect/menuselect --enable-category-channel --enable-category-app menuselect.makeopts
make -j$(nproc) && sudo make install && sudo make samples
```

Copy the configs from `asterisk-full/config/` into `/etc/asterisk/`:

```bash
sudo cp asterisk-full/config/* /etc/asterisk/
sudo cp asterisk-full/agi/* /usr/local/bin/
sudo chmod +x /usr/local/bin/ai_*
```

Start Asterisk:

```bash
sudo systemctl enable asterisk
sudo systemctl start asterisk
sudo asterisk -rvvv
```

### 4. Open the firewall

```powershell
# Allow SIP + RTP through Windows Firewall
New-NetFirewallRule -DisplayName "Asterisk SIP" -Direction Inbound -Protocol UDP -LocalPort 5060 -Action Allow
New-NetFirewallRule -DisplayName "Asterisk RTP" -Direction Inbound -Protocol UDP -LocalPort 10000-10100 -Action Allow
New-NetFirewallRule -DisplayName "FastAPI"   -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

### 5. Softphone for testing

Install **Linphone** (https://linphone.org/) and configure:

| Field          | Value                  |
| -------------- | ---------------------- |
| SIP server     | `<your-Windows-LAN-IP>` |
| Username       | `rohan`                |
| Password       | `CHANGEME_PHONE_PASSWORD` |
| Transport      | UDP                    |

Replace `CHANGEME_PHONE_PASSWORD` in `pjsip.conf` and `YOUR_LAPTOP_IP` in the
identify section.

### 6. Make a test call

From Linphone, call `*91*` (the `s` extension in `[ai-inbound]`). You should
hear the AI say "Hello, thanks for calling" and respond to your speech.

---

## Path B — Docker Compose (recommended)

```powershell
# From the project root
docker compose -f asterisk-full/docker/docker-compose.yml up --build
```

`network_mode: host` makes the Asterisk container bind SIP/RTP directly to
your host. **On Windows this requires WSL2 with mirrored networking**, which
Docker Desktop enables by default since 4.20.

### Verify the stack

```powershell
curl http://localhost:11434/api/tags                # Ollama
curl http://localhost:8000/health                   # FastAPI
docker exec -it ai-phone-asterisk asterisk -rx "pjsip show endpoints"
```

You should see the `rohan-phone` and `ai-bridge` endpoints listed.

---

## Connect a real phone number (Airtel, Jio, etc.)

For a real inbound number, you have two choices:

1. **GSM gateway** — a hardware box (e.g., GoIP, Dinstar) with a SIM slot.
   Point its SIP trunk at your Asterisk. Calls to the Airtel number ring
   Asterisk, which runs the AI loop.
2. **SIP trunk provider** — sign up with Exotel, Plivo, or Twilio, and
   route the DID to your public IP. You'll need to forward ports 5060/UDP
   and 10000-10100/UDP from your router.

Until then, **use the Android app** (`../android-gateway/`) — it watches
your Airtel SIM and reports missed calls to the same FastAPI server, so
you get a working "phone assistant" without any SIP infrastructure at all.

---

## Call-flow summary

```
Inbound (PSTN / SIP / GSM gateway)
        |
        v
   PJSIP endpoint  →  [ai-inbound] context
        |                  |
        |       (record  →  /transcribe  →  /chat  →  /speak)
        |                  |
        v                  v
   AI voice reply  ←  FastAPI  ←  Whisper + Ollama (minimax-m3) + Piper
```

Outbound (callback a missed call) works the same way: the dialplan dials
`PJSIP/<number>@ai-bridge`, which uses the GSM gateway as a trunk.

---

## Troubleshooting

| Symptom                          | Likely cause                                  |
| -------------------------------- | --------------------------------------------- |
| One-way audio                    | NAT — confirm `external_*_address` in pjsip  |
| FastAPI 502 from AGI             | `AIAPP_URL` not set, or services not linked   |
| Ollama model not found           | Run `ollama pull minimax-m3`                  |
| Whisper slow on first call       | First-load is normal; subsequent are fast     |
| `pjsip show endpoints` empty     | `pjsip.conf` not loaded; run `module reload` |
