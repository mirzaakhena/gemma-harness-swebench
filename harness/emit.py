"""Emitter tunggal — SATU-SATUNYA modul yang boleh menulis events.jsonl,
verdict.json, runs.jsonl, dan campaign.json.

Kontrak: docs/kontrak-output.md (schema_version 1.0.0).
Encoding: UTF-8 tanpa BOM, newline LF. verdict.json & campaign.json ditulis
atomic (temp -> os.replace). Semua stream append-only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = "1.0.0"

PHASES = ("reproduce", "localize", "fix", "verify")
# 2026-07-22: + "evidence-audit" (lever N2 — audit evidence↔file shortlist
# LOCALIZE). Insiden: run_localize_gemma memakai nama ini saat whitelist belum
# memuatnya → ValueError runtime SETELAH model selesai (slot l-dev 12184 r2
# hangus parsial); test unit tak menangkap karena emit di-mock.
EVENTS = ("enter", "exit", "retry", "skip", "abort", "evidence-audit")
VERDICTS = {
    # R2 split-verdict: symptom-identifying REPRODUCE labels
    # (repro-missing/vacuous-repro/syntax-error/gold-wont-flip/gold-flip-crash)
    # supplement the legacy catch-all buckets. Any verdict emitted MUST be
    # listed here or event() raises ValueError.
    # 2026-07-22: + "infra-abort" (reproduce & localize) — lever infra-abort
    # KH-22: run ber-penanda infra_abort.json (driver crash transport /
    # preflight gagal) divonis kelasnya sendiri, BUKAN repro-missing/
    # syntax-fail, supaya statistik wall tak tercemar bangkai endpoint mati.
    "reproduce": ("pass", "fail", "syntax-fail", "wrong-logic", "timeout", "abort",
                  "repro-missing", "vacuous-repro", "syntax-error",
                  "gold-wont-flip", "gold-flip-crash", "infra-abort"),
    "localize": ("pass", "fail", "syntax-fail", "wrong-logic", "timeout", "abort",
                 "infra-abort"),
    "verify": ("pass", "fail", "syntax-fail", "wrong-logic", "timeout", "abort"),
    "fix": ("flip", "no-flip", "empty-patch", "timeout", "abort"),
}
WALLS = PHASES + ("abort",)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _append_jsonl(path: Path, obj: dict) -> None:
    line = json.dumps(obj, ensure_ascii=False)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def _write_atomic_json(path: Path, obj: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


class Emitter:
    def __init__(self, artifacts_root: Path | str, campaign: str,
                 case_id: str, rerun: int) -> None:
        self.campaign = campaign
        self.case_id = case_id
        self.run_id = f"{campaign}--{case_id}--r{rerun}"
        self.campaign_dir = Path(artifacts_root) / campaign
        self.run_dir = self.campaign_dir / self.run_id
        (self.run_dir / "files").mkdir(parents=True, exist_ok=True)
        self._started = _now_iso()

    def _base(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "ts": _now_iso(),
            "run_id": self.run_id,
            "case_id": self.case_id,
            "campaign": self.campaign,
        }

    def event(self, phase: str, event: str, verdict: str | None = None,
              attempt: int = 1, budget: dict | None = None,
              counters: dict | None = None, detail: dict | None = None) -> None:
        if phase not in PHASES:
            raise ValueError(f"phase tidak dikenal: {phase!r} (sah: {PHASES})")
        if event not in EVENTS:
            raise ValueError(f"event tidak dikenal: {event!r} (sah: {EVENTS})")
        if verdict is not None:
            if event != "exit":
                raise ValueError("verdict hanya boleh terisi saat event='exit'")
            if verdict not in VERDICTS[phase]:
                raise ValueError(
                    f"verdict {verdict!r} tidak sah untuk fase {phase!r} "
                    f"(sah: {VERDICTS[phase]})")
        _append_jsonl(self.run_dir / "events.jsonl", {
            **self._base(),
            "phase": phase,
            "event": event,
            "verdict": verdict,
            "attempt": attempt,
            "budget": budget,
            "counters": counters,
            "detail": detail if detail is not None else {},
        })

    def run_start(self) -> None:
        self._started = _now_iso()
        _append_jsonl(self.campaign_dir / "runs.jsonl",
                      {**self._base(), "event": "start"})

    def run_end(self, verdict: dict, wall: str | None) -> None:
        _append_jsonl(self.campaign_dir / "runs.jsonl",
                      {**self._base(), "event": "end",
                       "verdict": verdict, "wall": wall})

    def write_verdict(self, phases: dict, wall: str | None,
                      pass_l1: bool | None, pass_l2: bool | None,
                      infra_abort: bool = False) -> None:
        if wall is not None and wall not in WALLS:
            raise ValueError(f"wall {wall!r} tidak sah (sah: {WALLS} atau None)")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "campaign": self.campaign,
            "phases": phases,
            "wall": wall,
            "pass_l1": pass_l1,
            "pass_l2": pass_l2,
            "started": self._started,
            "finished": _now_iso(),
            "files": "files/",
        }
        # Lever infra-abort (KH-22): field baru HANYA hadir saat true —
        # bentuk verdict lama tak berubah; downstream (batch runner, papan
        # skor) mengecualikan run infra dari denominator tanpa parsing label.
        if infra_abort:
            payload["infra_abort"] = True
        _write_atomic_json(self.run_dir / "verdict.json", payload)


def write_campaign(artifacts_root: Path | str, campaign: str,
                   description: str, cases: list[dict]) -> None:
    campaign_dir = Path(artifacts_root) / campaign
    campaign_dir.mkdir(parents=True, exist_ok=True)
    _write_atomic_json(campaign_dir / "campaign.json", {
        "schema_version": SCHEMA_VERSION,
        "name": campaign,
        "created": _now_iso(),
        "description": description,
        "cases": cases,
    })
