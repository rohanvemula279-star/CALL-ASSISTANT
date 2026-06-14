# Minimal Asterisk config for the AI phone assistant.
#
# Mount the asterisk/ directory over /etc/asterisk/ in the container.
# In production, replace pjsip.conf with your trunk config and point
# [ai-inbound] at the FastAPI service for proper recording + playback.

[options]
verbose = 3

[modules]
autoload=yes
