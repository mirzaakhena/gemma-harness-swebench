"""Test lever infra-abort sisi GATE + emit (KH-22, entri "bangkai ber-verdict").

Insiden 2026-07-22: run driver yang crash transport (endpoint mati,
URLError/10060) tervonis `repro-missing`/`syntax-fail` biasa oleh gate ->
statistik wall tercemar (15902: 9 tercatat vs 3 riil). Kontrak baru:
- driver menulis penanda `infra_abort.json` di run dir;
- gate MENGHORMATI penanda itu SEBELUM cek artefak: verdict `infra-abort`,
  pass_l1=false, wall="abort", field verdict.json `infra_abort: true`
  (downstream mengecualikan dari denominator tanpa parsing label).
Backward-compatible: tanpa penanda, vonis lama tak berubah.
"""
import json
import subprocess
import sys

import pytest

import harness.stages.chat_transport as ct
import harness.stages.run_localize_gates as lgate
import harness.stages.run_repro_gates as rgate
from harness import emit
from harness.emit import Emitter


# --- emit: label & field baru (backward-compatible) -------------------------

def test_infra_abort_verdict_whitelisted_for_reproduce_and_localize():
    assert "infra-abort" in emit.VERDICTS["reproduce"]
    assert "infra-abort" in emit.VERDICTS["localize"]


def test_write_verdict_infra_abort_field(tmp_path):
    em = Emitter(tmp_path, "r-dev", "django__django-15902", 4)
    em.write_verdict(phases={"reproduce": {"verdict": "infra-abort",
                                           "duration_s": None}},
                     wall="abort", pass_l1=False, pass_l2=None,
                     infra_abort=True)
    v = json.loads((em.run_dir / "verdict.json").read_text(encoding="utf-8"))
    assert v["infra_abort"] is True
    assert v["pass_l1"] is False


def test_write_verdict_without_infra_flag_keeps_legacy_shape(tmp_path):
    # Konsumen lama membaca pass_l1 saja — verdict non-infra TIDAK berubah
    # bentuk (field baru hanya hadir saat true).
    em = Emitter(tmp_path, "r-dev", "django__django-15902", 1)
    em.write_verdict(phases={}, wall=None, pass_l1=True, pass_l2=None)
    v = json.loads((em.run_dir / "verdict.json").read_text(encoding="utf-8"))
    assert "infra_abort" not in v


# --- gate REPRODUCE ---------------------------------------------------------

def _repro_gate_run(monkeypatch, art):
    monkeypatch.setattr(sys, "argv", [
        "run_repro_gates.py", "--case", "django__django-15902",
        "--rerun", "4", "--image", "img", "--artifacts", str(art)])
    assert rgate.main() == 0
    run_dir = art / "r-dev" / "r-dev--django__django-15902--r4"
    return run_dir, json.loads(
        (run_dir / "verdict.json").read_text(encoding="utf-8"))


def _no_docker(monkeypatch, module):
    def boom(*a, **k):
        raise AssertionError("tak boleh menjalankan docker/sandbox utk "
                             "run ber-penanda infra")
    monkeypatch.setattr(module.subprocess, "run", boom)


def test_repro_gate_honors_infra_marker_over_missing_artifacts(
        monkeypatch, tmp_path):
    # Bangkai 15902 r4-r9: files/ kosong + penanda -> BUKAN repro-missing.
    art = tmp_path / "artifacts"
    run_dir = art / "r-dev" / "r-dev--django__django-15902--r4"
    run_dir.mkdir(parents=True)
    ct.write_infra_abort(run_dir, reason="preflight", stage="reproduce",
                         turns_model_used=0)
    run_dir2, v = _repro_gate_run(monkeypatch, art)
    assert v["phases"]["reproduce"]["verdict"] == "infra-abort"
    assert v["pass_l1"] is False
    assert v["wall"] == "abort"
    assert v["infra_abort"] is True
    events = [json.loads(l) for l in
              (run_dir2 / "events.jsonl").read_text(encoding="utf-8")
              .splitlines()]
    exits = [e for e in events if e["event"] == "exit"]
    assert exits and exits[-1]["verdict"] == "infra-abort"
    assert "preflight" in json.dumps(exits[-1]["detail"])


def test_repro_gate_marker_wins_even_with_salvaged_artifacts(
        monkeypatch, tmp_path):
    # Varian 14855 r7 era-baru: artefak TERSALVAGE ada, tapi run tetap
    # bangkai infra — penanda menang, sandbox gate tak pernah dibakar.
    art = tmp_path / "artifacts"
    run_dir = art / "r-dev" / "r-dev--django__django-15902--r4"
    files = run_dir / "files"
    files.mkdir(parents=True)
    (files / "repro.py").write_text("print('x')\n", encoding="utf-8")
    (files / "repro.md").write_text("SYMPTOM: x\n", encoding="utf-8")
    ct.write_infra_abort(run_dir, reason="chat transport failure",
                         stage="reproduce", turns_model_used=21,
                         detail="URLError(TimeoutError(10060))")
    _no_docker(monkeypatch, rgate)
    _, v = _repro_gate_run(monkeypatch, art)
    assert v["phases"]["reproduce"]["verdict"] == "infra-abort"
    assert v["infra_abort"] is True


def test_repro_gate_without_marker_keeps_repro_missing(monkeypatch, tmp_path):
    # Regresi R2 split-verdict: tanpa penanda, vonis lama tak berubah.
    art = tmp_path / "artifacts"
    (art / "r-dev" / "r-dev--django__django-15902--r4" / "files").mkdir(
        parents=True)
    _, v = _repro_gate_run(monkeypatch, art)
    assert v["phases"]["reproduce"]["verdict"] == "repro-missing"
    assert v["pass_l1"] is False
    assert v["wall"] == "reproduce"
    assert "infra_abort" not in v


# --- gate LOCALIZE ----------------------------------------------------------

def _localize_gate_run(monkeypatch, art):
    monkeypatch.setattr(sys, "argv", [
        "run_localize_gates.py", "--case", "django__django-15902",
        "--rerun", "4", "--image", "img", "--artifacts", str(art)])
    assert lgate.main() == 0
    run_dir = art / "l-dev" / "l-dev--django__django-15902--r4"
    return run_dir, json.loads(
        (run_dir / "verdict.json").read_text(encoding="utf-8"))


def test_localize_gate_honors_infra_marker(monkeypatch, tmp_path):
    art = tmp_path / "artifacts"
    run_dir = art / "l-dev" / "l-dev--django__django-15902--r4"
    run_dir.mkdir(parents=True)
    ct.write_infra_abort(run_dir, reason="chat transport failure",
                         stage="localize", turns_model_used=3)
    _no_docker(monkeypatch, lgate)
    run_dir2, v = _localize_gate_run(monkeypatch, art)
    assert v["phases"]["localize"]["verdict"] == "infra-abort"
    assert v["pass_l1"] is False
    assert v["wall"] == "abort"
    assert v["infra_abort"] is True
    events = [json.loads(l) for l in
              (run_dir2 / "events.jsonl").read_text(encoding="utf-8")
              .splitlines()]
    exits = [e for e in events if e["event"] == "exit"]
    assert exits and exits[-1]["verdict"] == "infra-abort"


def test_localize_gate_without_marker_keeps_syntax_fail(monkeypatch, tmp_path):
    art = tmp_path / "artifacts"
    (art / "l-dev" / "l-dev--django__django-15902--r4" / "files").mkdir(
        parents=True)
    _, v = _localize_gate_run(monkeypatch, art)
    assert v["phases"]["localize"]["verdict"] == "syntax-fail"
    assert v["pass_l1"] is False
    assert "infra_abort" not in v
