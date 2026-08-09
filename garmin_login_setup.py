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
try:
    token_string = client.garth.dumps()
except Exception as e:
    print(f"❌ Could not export the token: {e}")
    sys.exit(1)

# Sanity check it round-trips and actually contains both halves
try:
    parts = json.loads(base64.b64decode(token_string))
    assert isinstance(parts, list) and len(parts) == 2
    assert "oauth_token" in parts[0]
    assert "refresh_token_expires_at" in parts[1]
except Exception:
    print("❌ Exported token doesn't contain both halves. Something went wrong.")
    sys.exit(1)

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
print(f"  OAuth1 token : present (good for ~1 year)")
if when:
    print(f"  OAuth2 refresh: valid until {when:%Y-%m-%d}")
print()
print("Because both halves are included, the workflow refreshes itself on")
print("every run. You should not need to redo this for months. If you were")
print("re-adding this weekly before, that's the bug this fixes — only the")
print("short-lived half was reaching GitHub.")
print("-" * 60)
