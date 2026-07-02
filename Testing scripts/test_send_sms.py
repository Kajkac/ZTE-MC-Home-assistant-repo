#!/usr/bin/env python3
"""
Sends a REAL SMS through an MC-series router via mc.run_commands() -- the
same in-process function router_backend.py now calls in Home Assistant --
to verify the rewritten send path works end-to-end (command ID 8).

THIS SENDS AN ACTUAL SMS AND MAY INCUR CARRIER CHARGES. It is NOT read-only.
You will be shown the router IP, phone number, and message text, and must
confirm before anything is sent.

Setup (run this on a machine with network access to your router):
    pip install cryptography
    # Either copy mc.py and pygsm7.py into the same folder as this script,
    # or run from a full repo checkout (Testing scripts/ next to
    # custom_components/zte_router/) -- both layouts are auto-detected.

Usage:
    python3 test_send_sms.py --ip 192.168.1.1 --password PASS --to +385989072702

    # Custom message text:
    python3 test_send_sms.py --ip 192.168.1.1 --password PASS --to +385989072702 --message "Test from rewrite"

    # MC888/MC889 with a username:
    python3 test_send_sms.py --ip 192.168.1.1 --password PASS --username admin --to +385989072702

    # Skip the interactive confirmation prompt (e.g. for scripted use):
    python3 test_send_sms.py --ip 192.168.1.1 --password PASS --to +385989072702 --yes
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CANDIDATE_MC_DIRS = [
    SCRIPT_DIR,  # mc.py copied next to this script (flat folder layout)
    os.path.join(os.path.dirname(SCRIPT_DIR), "custom_components", "zte_router"),  # full repo checkout
]
MC_DIR = next((d for d in _CANDIDATE_MC_DIRS if os.path.isfile(os.path.join(d, "mc.py"))), None)
if MC_DIR is None:
    sys.exit(
        "Could not find mc.py. Copy mc.py and pygsm7.py into the same folder as "
        "this script, or run from a full repo checkout (Testing scripts/ next "
        "to custom_components/zte_router/)."
    )
sys.path.insert(0, MC_DIR)

import mc  # noqa: E402  (must come after sys.path setup above)

DEFAULT_MESSAGE = "Test SMS from ZTE Router integration in-process rewrite validation."


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ip", required=True, help="Router IP address")
    parser.add_argument("--password", required=True, help="Router admin password")
    parser.add_argument("--username", default=None, help="Only needed for MC888/MC889 with username auth")
    parser.add_argument("--to", required=True, help="Destination phone number, e.g. +385989072702")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="SMS text to send")
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation prompt")
    args = parser.parse_args()

    print("=" * 60)
    print("ABOUT TO SEND A REAL SMS")
    print("=" * 60)
    print(f"  Router IP : {args.ip}")
    print(f"  To        : {args.to}")
    print(f"  Message   : {args.message}")
    print("=" * 60)

    if not args.yes:
        answer = input("Type YES to actually send this SMS: ").strip()
        if answer != "YES":
            print("Aborted -- no SMS sent.")
            return

    raw = mc.run_commands(args.ip, args.password, args.username, "8", phone_number=args.to, message=args.message)
    print("\nRaw result from mc.run_commands():")
    print(raw)

    try:
        parsed = json.loads(raw)
        result = parsed.get("8")
    except Exception as e:
        print(f"\nCould not parse result as JSON: {e}")
        return

    print(f"\nParsed result for command 8: {result!r}")
    if result in (None, "", "Phone number or message not provided for sending SMS", "SMS sending not supported in multi-command mode."):
        print("\nFAILED -- see the message above.")
    else:
        print("\nSent -- check your phone to confirm delivery.")


if __name__ == "__main__":
    main()
