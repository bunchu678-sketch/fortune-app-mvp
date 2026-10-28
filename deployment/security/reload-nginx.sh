#!/bin/sh
# Candidate for /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
# Only Certbot successful deploy events for these two webroot lineages need this.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

case "${RENEWED_LINEAGE:-}" in
    /etc/letsencrypt/live/mari-mutsuro.hakase-uranai.jp|/etc/letsencrypt/live/admin.hakase-uranai.jp) ;;
    '') printf '%s\n' 'fortune-certbot: missing successful-renewal context' >&2; exit 64 ;;
    *) exit 0 ;; # B2C nginx installer/other projects are unchanged; no duplicate reload.
esac

failure() {
    printf '%s\n' "fortune-certbot: $1" >&2
    /usr/bin/logger -p daemon.err -t fortune-certbot "$1" || :
    exit 1
}

# Keep raw nginx/config/key paths out of ordinary output. Log failure stage only.
/usr/sbin/nginx -t >/dev/null 2>&1 || failure 'nginx syntax validation failed; reload skipped'
/usr/bin/systemctl reload nginx.service >/dev/null 2>&1 || failure 'nginx reload failed after renewal'
/usr/bin/logger -p daemon.info -t fortune-certbot 'nginx reload completed after renewal' || :
