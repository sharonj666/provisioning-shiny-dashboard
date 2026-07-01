"""Check whether the dashboard environment can import required packages."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from time import perf_counter


REQUIRED_MODULES = [
    "shiny",
    "pandas",
    "numpy",
    "openpyxl",
    "matplotlib",
    "seaborn",
]


def main() -> None:
    os.environ.setdefault("MPLCONFIGDIR", str(Path.cwd() / ".cache" / "matplotlib"))
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    print(f"Python: {sys.version.split()[0]}")
    failed: list[str] = []
    for module_name in REQUIRED_MODULES:
        start = perf_counter()
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            failed.append(module_name)
            print(f"FAIL {module_name}: {exc}")
            continue
        elapsed = perf_counter() - start
        version = getattr(module, "__version__", "installed")
        print(f"OK   {module_name:<10} {version} ({elapsed:.2f}s)")

    if failed:
        raise SystemExit(f"Missing or broken modules: {', '.join(failed)}")

    import app  # noqa: PLC0415

    print("OK   app imports successfully")
    print("Setup check complete.")


if __name__ == "__main__":
    main()
