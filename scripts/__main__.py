"""Allow running as: python -m scripts [command]

Commands:
  auto_clean    One-click safe auto clean
  deep_scan     Full disk scan report
  clean         Selective cleanup by report
"""

import runpy
import sys

if __name__ == "__main__":
    available = {
        "auto_clean": "scripts.auto_clean",
        "deep_scan": "scripts.deep_scan",
        "clean": "scripts.clean",
    }
    if len(sys.argv) > 1 and sys.argv[1] in available:
        runpy.run_module(available[sys.argv[1]], run_name="__main__", alter_sys=True)
    else:
        print("Disk Deep Clean — available commands:\n")
        for cmd, desc in [
            ("auto_clean", "   One-click safe auto cleanup"),
            ("deep_scan", "    Full disk scan & report"),
            ("clean", "          Selective cleanup by report"),
        ]:
            print(f"  python -m scripts {cmd} --help")
            print(f"      {desc}")
            print()
