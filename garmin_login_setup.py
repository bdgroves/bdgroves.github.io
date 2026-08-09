#!/usr/bin/env python3
"""
ONE-TIME LOCAL SETUP — run this on your own machine, never in CI.

This logs into Garmin Connect once with your real email/password (entered
interactively, never saved to disk in plaintext) and produces a token file
that the GitHub Actions workflow will use instead. Your actual Garmin
password never gets pasted into GitHub — only this derived token does.

Usage (with pixi — recommended, matches the repo's pixi.toml):
    pixi install
    pixi run python3 garmin_login_setup.py

Usage (plain pip, if you'd rather not install pixi for this one-off):
    pip install garminconnect curl_cffi
    python3 garmin_login_setup.py

If your account has MFA/2FA enabled, you'll be prompted for the one-time
code at the right moment — check your phone/email when asked.

When it finishes it writes a single-line token string and tells you to
paste it into the GitHub Secret called GARMIN_TOKENS_JSON. That string
carries BOTH halves of Garmin's auth, which is what stops the secret
expiring every week.
"""
import base64
import json
import sys
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path

try:
    from garminconnect import (
        Garmin,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
except ImportError:
    print("Missing dependency. Run this first:")
    print("    pip install garminconnect curl_cffi")
    sys.exit(1)

TOKEN_DIR = Path("./garmin_tokens_output")
TOKEN_DIR.mkdir(exist_ok=True)

print("=" * 60)
print("Garmin Connect — one-time login to generate a token file")
print("=" * 60)
print()

# If a previous run already logged in successfully, reuse those tokens rather
# than hitting Garmin's login endpoint again — it rate-limits (429) hard.
_existing = (((TOKEN_DIR / "oauth1_token.json").exists() and (TOKEN_DIR / "oauth2_token.json").exists())
              or (TOKEN_DIR / "garmin_tokens.json").exists())
client = None

if _existing:
    print("Found tokens from a previous login in", TOKEN_DIR)
    print("Exporting those instead of logging in again (avoids Garmin's rate limit).")
    print("Delete that folder and re-run if you want a completely fresh login.")
    print()
else:
    email = input("Garmin email: ").strip()
    password = getpass("Garmin password (hidden, not saved): ")

    try:
        client = Garmin(
            email=email,
            password=password,
            prompt_mfa=lambda: input("MFA one-time code (check your phone/email): ").strip(),
        )
        client.login(str(TOKEN_DIR))
        print()
        print("✅ Login successful!")

    except GarminConnectAuthenticationError:
        print()
        print("❌ Wrong email or password. Run this script again to retry.")
        sys.exit(1)

    except GarminConnectTooManyRequestsError as e:
        print()
        print(f"❌ Rate limited by Garmin: {e}")
        print("   Wait a while and try again.")
        sys.exit(1)

    except GarminConnectConnectionError as e:
        print()
        print(f"❌ Connection error: {e}")
        sys.exit(1)

# Garmin auth has two halves and BOTH have to reach GitHub:
#
#   OAuth1  — long-lived, good for roughly a year. This is the one that lets
#             the workflow mint a fresh OAuth2 token on every run.
#   OAuth2  — short-lived. Its refresh token dies in about a week.
#
# The library writes these as two separate files (oauth1_token.json and
# oauth2_token.json), which is easy to half-copy by accident. If only the
# OAuth2 half makes it into the secret, everything works for about a week
# and then stops — which is exactly the "why do I keep re-adding this?"
# failure. So we export the portable base64 form instead, which carries
# both halves in a single string.
def _garth_client(c):
    for attr in ("client", "garth"):
        inner = getattr(c, attr, None)
        if inner is not None and hasattr(inner, "dump"):
            return attr, inner
    return None, None


def _summarise(name, obj):
    """Describe a token structure without printing any secret values."""
    if isinstance(obj, dict):
        keys = sorted(obj)
        print(f"   {name}: dict with keys {keys}")
        return keys
    if isinstance(obj, list):
        print(f"   {name}: list of {len(obj)} items")
        for i, item in enumerate(obj):
            _summarise(f"{name}[{i}]", item)
        return []
    print(f"   {name}: {type(obj).__name__}")
    return []


print()
print("Exporting token...")

try:
    import garminconnect as _gc
    print(f"   garminconnect {getattr(_gc, '__version__', '?')}")
except Exception:
    pass

attr, inner = _garth_client(client) if client is not None else (None, None)
if inner is not None:
    print(f"   (using client.{attr})")
    try:
        inner.dump(str(TOKEN_DIR))
    except Exception as e:
        print(f"   note: explicit dump failed: {e}")

present = sorted(p.name for p in TOKEN_DIR.glob("*"))
print(f"   token files on disk: {present or 'none'}")

# Different garminconnect releases store this differently: some write a single
# garmin_tokens.json, others write oauth1_token.json + oauth2_token.json.
# Take whatever is actually there rather than assuming a layout.
o1f, o2f = TOKEN_DIR / "oauth1_token.json", TOKEN_DIR / "oauth2_token.json"
single = TOKEN_DIR / "garmin_tokens.json"

token_string = None
has_oauth1 = False
oauth2_blob = {}

if o1f.exists() and o2f.exists():
    a = json.loads(o1f.read_text(encoding="utf-8"))
    b = json.loads(o2f.read_text(encoding="utf-8"))
    print("   layout: two-file (oauth1 + oauth2)")
    _summarise("oauth1", a); _summarise("oauth2", b)
    has_oauth1 = bool(a) and "oauth_token" in a
    oauth2_blob = b if isinstance(b, dict) else {}
    token_string = base64.b64encode(json.dumps([a, b]).encode()).decode()

elif single.exists():
    raw = single.read_text(encoding="utf-8").strip()
    print("   layout: single-file (garmin_tokens.json)")
    try:
        parsed = json.loads(raw)
        _summarise("token", parsed)
        # Find the oauth1/oauth2 parts wherever they live in this layout.
        if isinstance(parsed, list) and len(parsed) == 2:
            has_oauth1 = isinstance(parsed[0], dict) and "oauth_token" in parsed[0]
            oauth2_blob = parsed[1] if isinstance(parsed[1], dict) else {}
        elif isinstance(parsed, dict):
            has_oauth1 = "oauth_token" in parsed or "oauth1_token" in parsed
            oauth2_blob = parsed.get("oauth2_token") if isinstance(parsed.get("oauth2_token"), dict) else parsed
    except json.JSONDecodeError:
        print("   (not JSON — passing through verbatim)")
    # This file IS the tokenstore for this release; the secret is its contents.
    token_string = raw

if not token_string:
    print()
    print("❌ Could not produce a token.")
    print(f"   Check {TOKEN_DIR.resolve()} for what login() left behind.")
    sys.exit(1)

exp = (oauth2_blob or {}).get("refresh_token_expires_at")
parts = [{"oauth_token": "present"} if has_oauth1 else {}, oauth2_blob or {}]
exp = parts[1].get("refresh_token_expires_at")
when = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None

out_file = TOKEN_DIR / "GARMIN_TOKENS_JSON.txt"
out_file.write_text(token_string, encoding="utf-8")

print()
print("=" * 60)
print("SUCCESS — here's what to do next:")
print("=" * 60)
print()
print(f"1. Open this file:  {out_file.resolve()}")
print("2. Copy the ENTIRE contents — it's one long line of base64,")
print("   no quotes, no line breaks.")
print("3. GitHub repo -> Settings -> Secrets and variables -> Actions")
print("4. Update (or create) the secret named:  GARMIN_TOKENS_JSON")
print("5. Paste as the value and save.")
print()
print("Then delete the local garmin_tokens_output/ folder — the GitHub")
print("Secret is the source of truth from here.")
print()
print("-" * 60)
print("What you just exported:")
print(f"  OAuth1 token : {'present (good for ~1 year)' if has_oauth1 else 'NOT FOUND — this is why it expires weekly'}")
if when:
    print(f"  OAuth2 refresh: valid until {when:%Y-%m-%d}")
print()
if has_oauth1:
    print("The long-lived OAuth1 half is included, so the workflow refreshes")
    print("itself on every run. This should hold for months.")
else:
    print("NOTE: no long-lived OAuth1 half was found in what Garmin issued.")
    print("That is why the secret keeps expiring. Worth checking whether MFA")
    print("is enabled on the account — it changes which tokens Garmin hands out.")
print("-" * 60)
