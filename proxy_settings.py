"""Opt-in Uvicorn proxy headers with an explicitly restricted trust boundary."""
import os


def proxy_settings():
    enabled = os.environ.get("FORTUNE_PROXY_HEADERS", "0")
    if enabled not in ("0", "1"):
        raise ValueError("FORTUNE_PROXY_HEADERS must be 0 or 1")
    values = os.environ.get("FORTUNE_TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
    trusted = [value.strip() for value in values]
    if not trusted or any(value not in {"127.0.0.1", "::1"} for value in trusted):
        raise ValueError("FORTUNE_TRUSTED_PROXY_IPS accepts only 127.0.0.1 and ::1")
    return {"proxy_headers": enabled == "1", "forwarded_allow_ips": ",".join(dict.fromkeys(trusted))}
