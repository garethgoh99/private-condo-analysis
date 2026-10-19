"""Get the day's URA API token using the URA_ACCESS_KEY secret.

Usage as a module:  from ura_token import get_token
As a script (connectivity check): python pipeline/ura_token.py
Never prints the token itself.
"""
import os
import sys
import requests

TOKEN_URL = "https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1"
# URA has been known to reject requests without a browser-like User-Agent.
HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}


def get_token(access_key=None, timeout=30):
    key = access_key or os.environ.get("URA_ACCESS_KEY")
    if not key:
        raise SystemExit("URA_ACCESS_KEY is not set.")
    r = requests.get(TOKEN_URL, headers={**HEADERS_BASE, "AccessKey": key.strip()}, timeout=timeout)
    ctype = r.headers.get("content-type", "")
    if "json" not in ctype.lower():
        raise SystemExit(f"Token request returned HTTP {r.status_code}, content-type {ctype!r} "
                         f"(not JSON - likely blocked). First 300 chars:\n{r.text[:300]}")
    body = r.json()
    if body.get("Status") != "Success" or not body.get("Result"):
        raise SystemExit(f"Token request failed: HTTP {r.status_code}, Status={body.get('Status')!r}, "
                         f"Message={body.get('Message')!r}")
    return body["Result"]


if __name__ == "__main__":
    tok = get_token()
    print(f"OK: got a token ({len(tok)} chars). Token not printed.")
    sys.exit(0)
