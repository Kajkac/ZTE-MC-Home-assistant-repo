import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MC_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "custom_components", "zte_router")
sys.path.insert(0, MC_DIR)

from g5_ultra_client import G5UltraRouterRunner  # noqa: E402  (must come after sys.path setup above)


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick tester for G5 Ultra client gather data.")
    parser.add_argument("--ip", default="192.168.100.1", help="Router IP address")
    parser.add_argument("--password", required=True, help="Router admin password")
    parser.add_argument(
        "--output",
        help="Optional path to write JSON output (defaults to stdout)",
    )
    args = parser.parse_args()

    runner = G5UltraRouterRunner(ip=args.ip, password=args.password)
    data = runner.gather_all_data()
    dump = json.dumps(data, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(dump, encoding="utf-8")
    else:
        print(dump)


if __name__ == "__main__":
    main()
