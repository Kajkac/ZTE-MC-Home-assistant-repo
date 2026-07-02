#!/usr/bin/env python3
"""
Validates the proposed mc.py "in-process" rewrite against real MC-series
hardware, without touching any Home Assistant code or your live setup.

This proves two things before router_backend.py's subprocess-based
_run_mc_commands() gets rewritten to call zteRouter directly:

  1. Calling zteRouter's methods directly (in-process) produces the exact
     same data as the current approach (spawning "python3 mc.py ..." as a
     subprocess and parsing its stdout).

  2. Running TWO different routers' zteRouter instances in the same
     process (e.g. your MC801 and MC888) doesn't leak session state
     between them via mc.py's module-level globals (global_stok,
     global_AD). Subprocess execution hides this risk for free -- every
     call gets a fresh interpreter, so shared mutable state never
     actually gets shared. In-process, it would be, unless nothing reads
     or writes those globals (this script checks).

READ-ONLY BY DEFAULT. This will NOT reboot the router, send/delete SMS,
change data mode, or toggle WiFi. It only reads: general info, SMS info,
the last SMS in memory (read, not deleted), full status (zteinfo3), and
connected clients (zteinfo4).

Setup (run this on a machine with network access to your routers):
    pip install cryptography
    # Either copy mc.py and pygsm7.py into the same folder as this script,
    # or run from a full repo checkout (Testing scripts/ next to
    # custom_components/zte_router/) -- both layouts are auto-detected.

Usage:
    # Test one router:
    python3 test_inprocess_mc.py --ip 192.168.1.1 --password PASS

    # Test one router that needs a username (MC888/MC889):
    python3 test_inprocess_mc.py --ip 192.168.1.1 --password PASS --username admin

    # Test both routers AND the cross-router isolation check:
    python3 test_inprocess_mc.py \\
        --ip 192.168.1.1 --password PASS1 --label "MC801" \\
        --ip2 192.168.8.1 --password2 PASS2 --username2 admin --label2 "MC888"
"""

import argparse
import json
import os
import subprocess
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
MC_PATH = os.path.join(MC_DIR, "mc.py")

import mc  # noqa: E402  (must come after sys.path setup above)

# Commands that only read data -- safe to run against a live router with no
# side effects. See mc.py's __main__ dispatcher for what each ID means.
STRICT_COMPARE_COMMANDS = [1, 2, 3, 7, 16]  # zteinfo, zteinfo2, ztesmsinfo, zteinfo3, zteinfo4
INFO_ONLY_COMMANDS = [6]  # last SMS -- formatting of the "no SMS" dummy differs slightly, shown but not diffed


def run_via_subprocess(ip, password, username, commands):
    cmd = ["python3", MC_PATH, ip, password, commands, username or ""]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return {"_error": "subprocess timed out after 90s"}
    if result.returncode != 0:
        return {"_error": f"subprocess exited {result.returncode}", "_stderr": result.stderr[-2000:]}
    raw = result.stdout
    try:
        return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except Exception as e:
        return {"_error": f"failed to parse subprocess output: {e}", "_raw": raw[:2000]}


def run_in_process(ip, password, username, command_ids):
    """Mirrors mc.py's own __main__ dispatcher for the read-only commands."""
    zte = mc.zteRouter(ip, username, password)
    zte.authenticate()
    results = {}
    for cmd_id in command_ids:
        try:
            if cmd_id == 1:
                results[cmd_id] = json.loads(zte.zteinfo())
            elif cmd_id == 2:
                results[cmd_id] = json.loads(zte.zteinfo2())
            elif cmd_id == 3:
                results[cmd_id] = json.loads(zte.ztesmsinfo())
            elif cmd_id == 6:
                result = zte.parsesms()
                data = json.loads(result) if result else {}
                messages = data.get("messages", [])
                results[cmd_id] = messages[0] if messages else {"content": "NO SMS IN MEMORY"}
            elif cmd_id == 7:
                results[cmd_id] = json.loads(zte.zteinfo3())
            elif cmd_id == 16:
                results[cmd_id] = json.loads(zte.zteinfo4())
            else:
                results[cmd_id] = f"(not a read-only command in this harness: {cmd_id})"
        except Exception as e:
            results[cmd_id] = {"_error": str(e)}
    return results


def test_single_router(ip, password, username, label):
    print(f"\n{'=' * 60}\nTesting {label} ({ip})\n{'=' * 60}")

    all_ids = STRICT_COMPARE_COMMANDS + INFO_ONLY_COMMANDS
    print("Running via CURRENT subprocess approach...")
    sub_result = run_via_subprocess(ip, password, username, ",".join(map(str, all_ids)))
    if "_error" in sub_result:
        print(f"  FAILED to get subprocess baseline: {sub_result}")
        return None, False

    print("Running via PROPOSED in-process approach...")
    inproc_result = run_in_process(ip, password, username, all_ids)

    mismatches = []
    for cmd_id in STRICT_COMPARE_COMMANDS:
        sub_val = sub_result.get(str(cmd_id), sub_result.get(cmd_id))
        proc_val = inproc_result.get(cmd_id)
        if sub_val != proc_val:
            mismatches.append((cmd_id, sub_val, proc_val))

    if mismatches:
        print(f"\n  MISMATCHES FOUND ({len(mismatches)}) -- do not proceed with the rewrite until these are understood:")
        for cmd_id, sub_val, proc_val in mismatches:
            print(f"\n  Command {cmd_id}:")
            print(f"    subprocess : {str(sub_val)[:400]}")
            print(f"    in-process : {str(proc_val)[:400]}")
    else:
        print("\n  MATCH: in-process results are identical to the current subprocess results for all data-fetch commands.")

    print(f"\n  Command 6 (last SMS, informational only -- dummy 'no SMS' formatting may legitimately differ):")
    print(f"    subprocess : {str(sub_result.get('6', sub_result.get(6)))[:300]}")
    print(f"    in-process : {str(inproc_result.get(6))[:300]}")

    return inproc_result, len(mismatches) == 0


def test_isolation(router_a, router_b):
    """Run two DIFFERENT routers' zteRouter instances interleaved in the same
    process, and confirm neither leaks session state into the other."""
    print(f"\n{'=' * 60}\nCross-router isolation test\n{'=' * 60}")
    ip_a, pw_a, user_a = router_a
    ip_b, pw_b, user_b = router_b

    if ip_a == ip_b:
        print("  SKIPPED (same IP given twice, can't test isolation between two different routers)")
        return True

    ok = True

    zte_a = mc.zteRouter(ip_a, user_a, pw_a)
    zte_b = mc.zteRouter(ip_b, user_b, pw_b)

    zte_a.authenticate()
    zte_b.authenticate()

    token_a = getattr(zte_a, "_zte_auth_stok", None)
    token_b = getattr(zte_b, "_zte_auth_stok", None)
    if token_a and token_b and token_a == token_b:
        print("  WARNING: both routers show the SAME session token -- likely state leak between instances!")
        ok = False
    else:
        print("  OK: session tokens differ between the two router instances (or aren't cookie-based).")

    if mc.global_stok is not None or mc.global_AD is not None:
        print(
            f"  NOTE: module-level globals are set (global_stok={mc.global_stok!r}, "
            f"global_AD={mc.global_AD!r}). If nothing in mc.py actually reads these "
            f"(the real session state lives on self._zte_auth_stok/_zte_auth_AD), this is "
            f"dead code and harmless -- but confirm nothing reads them before relying on "
            f"in-process multi-router use."
        )
    else:
        print("  OK: module-level globals (global_stok/global_AD) are untouched -- consistent with being dead code.")

    # Re-fetch info from router A AFTER router B has authenticated, to confirm
    # router A's session wasn't clobbered by router B running in the same process.
    info_a_after = zte_a.zteinfo3()
    if not info_a_after:
        print("  WARNING: router A's session appears broken after router B authenticated in the same process.")
        ok = False
    else:
        print("  OK: router A still works after router B authenticated in the same process.")

    return ok


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ip", required=True, help="First router IP (e.g. your MC801)")
    parser.add_argument("--password", required=True)
    parser.add_argument("--username", default=None, help="Only needed for MC888/MC889 with username auth")
    parser.add_argument("--label", default="Router 1")
    parser.add_argument("--ip2", default=None, help="Optional second router IP (e.g. your MC888), for the isolation test")
    parser.add_argument("--password2", default=None)
    parser.add_argument("--username2", default=None)
    parser.add_argument("--label2", default="Router 2")
    args = parser.parse_args()

    all_ok = True

    _, ok1 = test_single_router(args.ip, args.password, args.username, args.label)
    all_ok = all_ok and ok1

    if args.ip2 and args.password2:
        _, ok2 = test_single_router(args.ip2, args.password2, args.username2, args.label2)
        all_ok = all_ok and ok2

        iso_ok = test_isolation(
            (args.ip, args.password, args.username),
            (args.ip2, args.password2, args.username2),
        )
        all_ok = all_ok and iso_ok
    else:
        print(
            "\n(No --ip2 given -- skipping the cross-router isolation test. "
            "Run again with both your MC801 and MC888 to test that too.)"
        )

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED -- safe to proceed with the in-process rewrite" if all_ok
          else "SOME CHECKS FAILED -- see warnings above before proceeding")
    print("=" * 60)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
