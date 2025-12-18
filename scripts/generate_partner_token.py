"""
Generate a short-lived partner JWT (HS256) for the partner diagnosis API.

Usage:
  export SECRET_KEY="your_api_secret"
  python scripts/generate_partner_token.py --partner-id partner-123 --ttl 1800
"""

import argparse
import os
import sys
import time
import jwt  # pip install pyjwt


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint a partner JWT (HS256).")
    parser.add_argument(
        "--partner-id",
        required=True,
        help="Partner identifier to set as the JWT 'sub' claim.",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=1800,
        help="Token lifetime in seconds (default: 1800 = 30 minutes).",
    )
    parser.add_argument(
        "--scope",
        default="diagnosis:read",
        help="Space-delimited scopes; must include diagnosis:read.",
    )
    args = parser.parse_args()

    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        print("ERROR: SECRET_KEY env var must be set.", file=sys.stderr)
        return 1

    now = int(time.time())
    payload = {
        "sub": args.partner_id,
        "token_type": "partner",
        "scope": args.scope,
        "iat": now,
        "exp": now + args.ttl,
    }

    try:
        token = jwt.encode(payload, secret_key, algorithm="HS256")
    except Exception as exc:
        print(f"ERROR: Failed to encode token: {exc}", file=sys.stderr)
        return 1

    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



