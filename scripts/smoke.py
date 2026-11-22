"""Smoke tests for the running ControlMap API."""

import sys
import urllib.error
import urllib.request

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"

ENDPOINTS = ["/health", "/docs"]


def main() -> int:
    failed = False

    for endpoint in ENDPOINTS:
        url = f"{BASE_URL}{endpoint}"

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.status == 200:
                    print(f"PASS {endpoint}: HTTP {response.status}")
                else:
                    print(f"FAIL {endpoint}: HTTP {response.status}")
                    failed = True
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"FAIL {endpoint}: {error}")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
