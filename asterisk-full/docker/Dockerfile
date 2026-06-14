FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        asterisk \
        asterisk-pjsip \
        asterisk-core-sounds-en \
        asterisk-moh-opsound-gsm \
        curl \
        python3 \
        python3-requests \
        ca-certificates \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Drop in our configs
COPY config/ /etc/asterisk/

# Drop in AGI scripts
COPY agi/ /usr/local/bin/
RUN chmod +x /usr/local/bin/ai_call.sh /usr/local/bin/ai_agi.py

# Working dirs
RUN mkdir -p /var/lib/asterisk/ai /var/lib/asterisk/wav \
    && chown -R asterisk:asterisk /var/lib/asterisk

EXPOSE 5060/udp 5060/tcp 5038/tcp 10000-10100/udp

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
    CMD asterisk -rx 'pjsip show endpoints' | grep -q 'Endpoint:' || exit 1

CMD ["/usr/sbin/asterisk", "-f", "-U", "asterisk", "-G", "asterisk"]
