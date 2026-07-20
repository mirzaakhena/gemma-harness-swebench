"""Test wiring kampanye f-dev — snapshot katalog via emitter tunggal.
Populasi awal spec §9: 13 case."""
import json
import sys

from harness.make_fix_campaign import F_DEV_CASES, build_cases, main

EXPECTED = {
    "django__django-11422", "django__django-11999", "django__django-12308",
    "django__django-13401", "django__django-13220", "django__django-11964",
    "django__django-11910", "django__django-13660", "django__django-14017",
    "django__django-15400", "astropy__astropy-7746", "django__django-13768",
    "django__django-12747",
}


def test_population_matches_spec():
    assert set(F_DEV_CASES) == EXPECTED
    assert len(F_DEV_CASES) == 13


def test_build_cases_shape():
    cases = build_cases()
    assert len(cases) == 13
    assert all(set(c) == {"case_id", "dev_set"} for c in cases)
    assert all(c["dev_set"] is True for c in cases)


def test_main_writes_campaign_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv",
                        ["make_fix_campaign.py", "--artifacts",
                         str(tmp_path)])
    assert main() == 0
    data = json.loads((tmp_path / "f-dev" / "campaign.json")
                      .read_text(encoding="utf-8"))
    assert data["name"] == "f-dev"
    assert data["schema_version"] == "1.0.0"
    assert len(data["cases"]) == 13
