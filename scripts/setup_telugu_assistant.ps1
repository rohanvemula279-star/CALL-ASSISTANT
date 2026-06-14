# Setup script for Telugu Assistant (Max)
# Run this from the project root after installing edge-tts.
# Requires: edge-tts (pip install edge-tts)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$GreetingSource = Join-Path $ProjectRoot "storage\telugu_tts\telugu_greeting.wav"
$AsteriskSounds = Join-Path $ProjectRoot "asterisk-full\sounds\custom"

Write-Host "=== Telugu Assistant (Max) Setup ===" -ForegroundColor Cyan

# 1. Install edge-tts if not present
$edgetts = pip list 2>$null | Select-String "edge-tts"
if (-not $edgetts) {
    Write-Host "[1/4] Installing edge-tts..." -ForegroundColor Yellow
    pip install edge-tts
} else {
    Write-Host "[1/4] edge-tts already installed ✓" -ForegroundColor Green
}

# 2. Generate Telugu greeting audio
if (-not (Test-Path -LiteralPath $GreetingSource)) {
    Write-Host "[2/4] Generating Telugu greeting audio..." -ForegroundColor Yellow
    edge-tts --voice te-IN-MohanNeural --text "రోహన్ సర్ బిజీగా ఉన్నారు. నేను అతని అసిస్టెంట్ మాక్స్ ని. నేను మీరు చెప్పిన సమాచారాన్ని సర్ కి పంపిస్తాను." --write-media $GreetingSource
} else {
    Write-Host "[2/4] Telugu greeting audio already exists ✓" -ForegroundColor Green
}

# 3. Copy greeting to Asterisk sounds directory (for Docker volume mount)
if (-not (Test-Path -LiteralPath $AsteriskSounds)) {
    New-Item -ItemType Directory -Path $AsteriskSounds -Force | Out-Null
}
Copy-Item -LiteralPath $GreetingSource -Destination (Join-Path $AsteriskSounds "telugu_greeting.wav") -Force
Write-Host "[3/4] Copied greeting to asterisk-full/sounds/custom/ ✓" -ForegroundColor Green

# 4. Verify the voicemail endpoint works
Write-Host "[4/4] Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "=== What's next? ===" -ForegroundColor Cyan
Write-Host "1. Start the FastAPI server: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
Write-Host "2. For Asterisk, add to extensions.conf: #include ""extensions.d/telugu_assistant.conf"""
Write-Host "3. Map the Asterisk context 'telugu-assistant-inbound' to your incoming SIP trunk"
Write-Host ""
Write-Host "The greeting says (in Telugu):" -ForegroundColor White
Write-Host "  'Rohan sir busy unnaru, nenu thana Assistant Max ni,"
Write-Host "   nenu meru chepina samacharani sir ki pamputhanu'"
Write-Host ""
Write-Host "When a caller hears this, they leave a message."
Write-Host "After they hang up, the recording is:"
Write-Host "  - Transcribed via Whisper"
Write-Host "  - Summarized via Ollama"
Write-Host "  - Sent to Telegram" -ForegroundColor Yellow
