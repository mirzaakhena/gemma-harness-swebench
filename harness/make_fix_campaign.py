"""Wiring kampanye f-dev: tulis campaign.json via emitter tunggal.

Populasi awal (spec §9): 13 case — 12 daftar handoff + 12747 (3/3 pasca
lever L-a). Menyusul opsional (15320, 13158) ditambah lewat edit daftar
ini + rerun script (campaign.json snapshot ditulis atomic).

Pemakaian (dari root main):
    python harness/make_fix_campaign.py [--artifacts ../artifacts]
"""
from __future__ import annotations

import argparse
import sys

from harness.emit import write_campaign

F_DEV_CASES = [
    "django__django-11422", "django__django-11999", "django__django-12308",
    "django__django-13401", "django__django-13220", "django__django-11964",
    "django__django-11910", "django__django-13660", "django__django-14017",
    "django__django-15400", "astropy__astropy-7746", "django__django-13768",
    "django__django-12747",
]


def build_cases() -> list[dict]:
    return [{"case_id": c, "dev_set": True} for c in F_DEV_CASES]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="../artifacts")
    args = ap.parse_args()
    write_campaign(args.artifacts, "f-dev",
                   "Fase FIX — dev loop Gemma (iterasi kandidat shortlist)",
                   build_cases())
    print("campaign.json f-dev written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
