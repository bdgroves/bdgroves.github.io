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

When it finishes, it prints the exact contents you should paste into a
new GitHub Secret called GARMIN_TOKENS_JSON.
"""
import json
import sys
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

token_file = TOKEN_DIR / "garmin_tokens.json"
if not token_file.exists():
    print(f"❌ Expected token file not found at {token_file}")
    print("   Something unexpected happened — check the garmin_tokens_output/ folder manually.")
    sys.exit(1)

with open(token_file, encoding="utf-8") as f:
    token_contents = f.read()

# Sanity check it's valid JSON before telling Brooks to paste it anywhere
try:
    json.loads(token_contents)
except json.JSONDecodeError:
    print("❌ Token file doesn't look like valid JSON. Something went wrong.")
    sys.exit(1)

print()
print("=" * 60)
print("SUCCESS — here's what to do next:")
print("=" * 60)
print()
print(f"1. Open this file in a text editor: {token_file.resolve()}")
print("2. Copy the ENTIRE contents (it's JSON, starts with '{' and ends with '}')")
print("3. Go to your GitHub repo -> Settings -> Secrets and variables -> Actions")
print("4. Create a new secret named:  GARMIN_TOKENS_JSON")
print("5. Paste the file contents as the value, save")
print()
print("Once that's saved, delete this local garmin_tokens_output/ folder —")
print("you don't need it anymore, the secret in GitHub is now the source of truth.")
print()
print("This token should keep working indefinitely (Garmin auto-refreshes it")
print("on each use). If it ever stops working, just re-run this script and")
print("update the GitHub Secret with the new token.")
