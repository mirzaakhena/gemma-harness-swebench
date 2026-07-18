"""Test kontrak emitter — satu-satunya penulis events/verdict/runs/campaign.

Kontrak: docs/kontrak-output.md (schema_version 1.0.0).
"""
import json
from pathlib import Path

import pytest

from harness.emit import SCHEMA_VERSION, Emitter, write_campaign


@pytest.fixture()
def artifacts(tmp_path: Path) -> Path:
    return tmp_path / "artifacts"


@pytest.fixture()
def em(artifacts: Path) -> Emitter:
    return Emitter(
        artifacts_root=artifacts,
        campaign="r-dev",
        case_id="django__django-11910",
        rerun=1,
    )


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --- run_id & layout -------------------------------------------------------

def test_run_id_format(em: Emitter):
    assert em.run_id == "r-dev--django__django-11910--r1"


def test_run_dir_layout_created(em: Emitter, artifacts: Path):
    run_dir = artifacts / "r-dev" / "r-dev--django__django-11910--r1"
    assert run_dir.is_dir()
    assert (run_dir / "files").is_dir()


# --- events.jsonl ----------------------------------------------------------

def test_event_appends_valid_json_line(em: Emitter, artifacts: Path):
    em.event(phase="reproduce", event="enter")
    em.event(phase="reproduce", event="exit", verdict="pass")
    lines = read_jsonl(em.run_dir / "events.jsonl")
    assert len(lines) == 2
    first = lines[0]
    assert first["schema_version"] == SCHEMA_VERSION
    assert first["run_id"] == "r-dev--django__django-11910--r1"
    assert first["case_id"] == "django__django-11910"
    assert first["campaign"] == "r-dev"
    assert first["phase"] == "reproduce"
    assert first["event"] == "enter"
    assert first["verdict"] is None
    assert first["attempt"] == 1
    # ts ISO8601 dengan offset (bukan naive)
    assert "T" in first["ts"] and ("+" in first["ts"] or first["ts"].endswith("Z"))
    # baris exit membawa verdict
    assert lines[1]["verdict"] == "pass"


def test_events_file_utf8_lf_no_bom_no_cr(em: Emitter):
    em.event(phase="reproduce", event="enter", detail={"note": "café ☕"})
    raw = (em.run_dir / "events.jsonl").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")  # tanpa BOM
    assert b"\r" not in raw                      # LF murni
    assert raw.endswith(b"\n")


def test_event_rejects_unknown_phase_and_event(em: Emitter):
    with pytest.raises(ValueError):
        em.event(phase="compile", event="enter")
    with pytest.raises(ValueError):
        em.event(phase="reproduce", event="begin")


def test_verdict_only_allowed_on_exit(em: Emitter):
    with pytest.raises(ValueError):
        em.event(phase="reproduce", event="enter", verdict="pass")


def test_verdict_enum_closed_per_phase(em: Emitter):
    # 'pass' bukan verdict sah untuk fase fix
    with pytest.raises(ValueError):
        em.event(phase="fix", event="exit", verdict="pass")
    # 'flip' sah untuk fix
    em.event(phase="fix", event="exit", verdict="flip")
    # 'flip' tidak sah untuk reproduce
    with pytest.raises(ValueError):
        em.event(phase="reproduce", event="exit", verdict="flip")


def test_event_counters_and_budget_standard_keys(em: Emitter):
    em.event(
        phase="fix",
        event="retry",
        attempt=2,
        budget={"msg_used": 30, "msg_limit": 60},
        counters={"fix_tries": 3, "loc_tries": None, "stage_call": 1},
    )
    line = read_jsonl(em.run_dir / "events.jsonl")[0]
    assert line["budget"] == {"msg_used": 30, "msg_limit": 60}
    assert line["counters"] == {"fix_tries": 3, "loc_tries": None, "stage_call": 1}
    assert line["attempt"] == 2


def test_abort_event_carries_reason(em: Emitter):
    em.event(phase="fix", event="abort", detail={"reason": "killed by timeout"})
    line = read_jsonl(em.run_dir / "events.jsonl")[0]
    assert line["event"] == "abort"
    assert line["detail"]["reason"] == "killed by timeout"


# --- runs.jsonl ------------------------------------------------------------

def test_run_start_and_end_indexed_in_runs_jsonl(em: Emitter, artifacts: Path):
    em.run_start()
    em.event(phase="reproduce", event="enter")
    em.event(phase="reproduce", event="exit", verdict="pass")
    em.run_end(verdict={"reproduce": "pass"}, wall=None)
    lines = read_jsonl(artifacts / "r-dev" / "runs.jsonl")
    assert [l["event"] for l in lines] == ["start", "end"]
    assert lines[0]["run_id"] == em.run_id
    assert lines[1]["verdict"] == {"reproduce": "pass"}
    assert lines[1]["wall"] is None


# --- verdict.json ----------------------------------------------------------

def test_verdict_json_written_atomic_with_subset_phases(em: Emitter):
    em.run_start()
    em.event(phase="reproduce", event="enter")
    em.event(phase="reproduce", event="exit", verdict="pass")
    em.write_verdict(
        phases={"reproduce": {"verdict": "pass", "duration_s": 12}},
        wall=None,
        pass_l1=None,
        pass_l2=None,
    )
    v = json.loads((em.run_dir / "verdict.json").read_text(encoding="utf-8"))
    assert v["schema_version"] == SCHEMA_VERSION
    assert v["run_id"] == em.run_id
    assert v["phases"]["reproduce"]["verdict"] == "pass"
    assert "localize" not in v["phases"]  # subset sah (kampanye per-fase)
    assert v["wall"] is None
    assert v["files"] == "files/"
    assert v["started"] and v["finished"]
    # tidak ada file temp tersisa
    leftovers = [p for p in em.run_dir.iterdir() if p.name.startswith("verdict") and p.suffix != ".json"]
    assert leftovers == []


def test_verdict_wall_must_be_phase_abort_or_none(em: Emitter):
    with pytest.raises(ValueError):
        em.write_verdict(phases={}, wall="crash", pass_l1=None, pass_l2=None)


# --- rerun append-only -----------------------------------------------------

def test_rerun_creates_new_directory_not_mutating_old(artifacts: Path):
    r1 = Emitter(artifacts_root=artifacts, campaign="r-dev",
                 case_id="django__django-11910", rerun=1)
    r1.event(phase="reproduce", event="enter")
    r2 = Emitter(artifacts_root=artifacts, campaign="r-dev",
                 case_id="django__django-11910", rerun=2)
    r2.event(phase="reproduce", event="enter")
    assert r2.run_dir != r1.run_dir
    assert len(read_jsonl(r1.run_dir / "events.jsonl")) == 1
    assert len(read_jsonl(r2.run_dir / "events.jsonl")) == 1


# --- campaign.json ---------------------------------------------------------

def test_write_campaign_snapshot(artifacts: Path):
    write_campaign(
        artifacts_root=artifacts,
        campaign="r-dev",
        description="Fase REPRODUCE — dev loop frontier vs Gemma",
        cases=[{"case_id": "django__django-11910", "tier": "B1", "dev_set": True}],
    )
    c = json.loads((artifacts / "r-dev" / "campaign.json").read_text(encoding="utf-8"))
    assert c["schema_version"] == SCHEMA_VERSION
    assert c["name"] == "r-dev"
    assert c["created"]
    assert c["cases"][0]["case_id"] == "django__django-11910"
