#!/usr/bin/env python3
"""Generează dashboard-ul Hidroelectrica pentru un cont anume.

Utilizare:
    python3 tools/genereaza_dashboard.py 8000123456
    -> creează dashboard/hidroelectrica_8000123456.yaml (gata de lipit)

Mai multe locuri de consum? Rulează scriptul o dată pentru fiecare cont.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "0000000000"


def slug(value: str) -> str:
    """Aceeași transformare ca homeassistant.util.slugify pentru numărul contului."""
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    cont = sys.argv[1].strip()
    for name in ("hidroelectrica_dashboard.yaml", "card_grafic_consum_apexcharts.yaml"):
        src = ROOT / "dashboard" / name
        out = ROOT / "dashboard" / name.replace("hidroelectrica_dashboard", f"hidroelectrica_{cont}").replace(
            "card_grafic_consum_apexcharts", f"card_grafic_consum_{cont}"
        )
        out.write_text(src.read_text(encoding="utf-8").replace(PLACEHOLDER, slug(cont)), encoding="utf-8")
        print(f"✓ {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
