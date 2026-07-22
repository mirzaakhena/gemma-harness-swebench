"""Test driver LOCALIZE — Lever L-a: cek rentang localize.md saat DONE.

Lahir dari baseline 12747 l-dev r1-r3: model menyetor localize.md dengan
rentang baris melewati akhir file (380-450 pada file 445 baris; juga
713-844). Gate L1 menangkap SETELAH run selesai ("extend beyond the end of
file") tapi driver menerima DONE tanpa cek -> nol retry, run hangus.
Lever: mirror vonis gate di jalur DONE acceptance (standar tunggal dengan
localize_gates), panjang file via docker `wc -l`, fail-closed bila file
tak terbaca.
"""
import subprocess

import harness.stages.run_localize_gemma as drv

MD = """chosen: 1
file: sympy/printing/pretty/pretty.py
lines: {lines}
what: adjust the printing branch that renders the reported object.
why: this branch owns the wrong output the user reports.
evidence: the print function around this range builds the wrong string; proven by probe.
"""


def _md(lines: str) -> str:
    return MD.format(lines=lines)


def _mock_exec(monkeypatch, out: str, code: int):
    calls = []

    def fake_exec(container, cmd, timeout=180):
        calls.append((container, cmd))
        return out, code

    monkeypatch.setattr(drv, "docker_exec", fake_exec)
    return calls


def test_range_beyond_eof_rejected_with_concrete_facts(monkeypatch):
    # Reproduksi kasus 12747: rentang 380-450 pada file 445 baris.
    _mock_exec(monkeypatch, "445\n", 0)
    err = drv.localize_range_error("c1", _md("380-450"))
    assert err is not None
    assert err.startswith("Not done yet:")
    assert "extend beyond the end of file" in err  # frasa vonis gate
    assert "380-450" in err                        # rentang yang diminta
    assert "445" in err                            # panjang file aktual
    assert "sympy/printing/pretty/pretty.py" in err


def test_valid_range_accepted(monkeypatch):
    _mock_exec(monkeypatch, "445\n", 0)
    assert drv.localize_range_error("c1", _md("380-445")) is None


def test_line_count_measured_on_pointed_file(monkeypatch):
    calls = _mock_exec(monkeypatch, "445\n", 0)
    drv.localize_range_error("c1", _md("380-445"))
    assert calls
    assert "/testbed/sympy/printing/pretty/pretty.py" in calls[0][1]
    assert "wc -l" in calls[0][1]


def test_unreadable_file_fails_closed(monkeypatch):
    _mock_exec(monkeypatch, "", 1)
    err = drv.localize_range_error("c1", _md("1-10"))
    assert err is not None and "could not be read" in err


def test_garbage_wc_output_fails_closed(monkeypatch):
    _mock_exec(monkeypatch, "not-a-number\n", 0)
    err = drv.localize_range_error("c1", _md("1-10"))
    assert err is not None and "could not be read" in err


def test_span_wider_than_gate_max_rejected(monkeypatch):
    # Mirror aturan gate <=200 baris (standar tunggal dgn localize_gates).
    _mock_exec(monkeypatch, "1000\n", 0)
    err = drv.localize_range_error("c1", _md("1-300"))
    assert err is not None and "too wide" in err


def test_zero_start_rejected(monkeypatch):
    _mock_exec(monkeypatch, "445\n", 0)
    err = drv.localize_range_error("c1", _md("0-10"))
    assert err is not None


def test_malformed_localize_md_rejected_before_docker(monkeypatch):
    calls = _mock_exec(monkeypatch, "445\n", 0)
    err = drv.localize_range_error("c1", "chosen: 1\nfile: x.py\n")
    assert err is not None and "localize.md" in err
    assert not calls  # tanpa slot lengkap tidak ada yang bisa diukur


def test_docker_write_file_sends_lf_only_bytes(monkeypatch):
    # R7: port fix CRLF dari driver R/F. text=True di Windows menerjemahkan
    # \n -> \r\n saat menulis ke pipe docker; file tulisan model rusak
    # retroaktif (kontrak §2: byte \r di file adalah BUG).
    captured = {}

    def fake_run(argv, **kwargs):
        captured["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    drv.docker_write_file("c1", "/tmp/x", "line1\nline2\r\nline3\n")
    assert isinstance(captured["input"], bytes)
    assert b"\r" not in captured["input"]
    assert captured["input"] == b"line1\nline2\nline3\n"


def test_tool_call_marker_triggers_strong_reminder():
    """R3/KH-12: driver LOCALIZE kini menangani mode gagal yang sama (native
    tool-call tanpa fence) dengan pengingat bentuk KUAT (English)."""
    from harness.stages.gemma_protocol import no_action_feedback
    reply = '<|tool_call|>\n{"name": "open", "path": "x.py"}'
    msg = no_action_feedback(reply, drv._ACTION_FORMS)
    assert "```file:" in msg and "```bash" in msg
    for w in ("kamu", "jalankan", "tulis", "berkas"):
        assert w not in msg.lower()


# --- Lever N2: audit evidence<->file saat candidates.md dibekukan -----------
# Reproduksi 12184: kandidat #1 base.py dgn evidence URLPattern.resolve
# (simbol adanya di resolvers.py, kandidat #2) meracuni urutan attempt FIX.

CANDS_12184 = """CANDIDATE 1
file: django/urls/base.py
evidence: URLPattern.resolve strips the script prefix before matching the route.
expectation: reverse() would honor the changed urlconf as the user expects.

CANDIDATE 2
file: django/urls/resolvers.py
evidence: URLPattern.resolve owns the per-pattern match the issue reports.
expectation: resolving would pick the right pattern as the user expects.
"""

BASE_PY = "def resolve(path, urlconf=None):\n    return get_resolver(urlconf)\n"
RESOLVERS_PY = "class URLPattern:\n    def resolve(self, path):\n        pass\n"


def _mock_cat(monkeypatch, bodies: dict, fail_paths=()):
    calls = []

    def fake_exec(container, cmd, timeout=180):
        calls.append((container, cmd))
        for path, body in bodies.items():
            if path in cmd:
                return body, 0
        return "cat: no such file\n", 1

    monkeypatch.setattr(drv, "docker_exec", fake_exec)
    return calls


def test_evidence_audit_demotes_wrong_file_candidate(monkeypatch):
    _mock_cat(monkeypatch, {"django/urls/base.py": BASE_PY,
                            "django/urls/resolvers.py": RESOLVERS_PY})
    text, rows = drv.audit_candidates_evidence("c1", CANDS_12184)
    from harness.stages.localize_gates import parse_candidates_md
    cands = parse_candidates_md(text)
    # resolvers.py (evidence cocok) naik ke urutan 1; base.py didemosi
    assert [c["file"] for c in cands] == [
        "django/urls/resolvers.py", "django/urls/base.py"]
    by_file = {r["file"]: r for r in rows}
    assert by_file["django/urls/base.py"]["evidence_mismatch"] is True
    assert by_file["django/urls/base.py"]["missing"] == ["URLPattern"]
    assert by_file["django/urls/base.py"]["new_rank"] == 2
    assert by_file["django/urls/resolvers.py"]["evidence_mismatch"] is False
    assert by_file["django/urls/resolvers.py"]["new_rank"] == 1


def test_evidence_audit_reads_via_container_readonly_path(monkeypatch):
    calls = _mock_cat(monkeypatch, {"django/urls/base.py": BASE_PY,
                                    "django/urls/resolvers.py": RESOLVERS_PY})
    drv.audit_candidates_evidence("c1", CANDS_12184)
    assert any("cat '/testbed/django/urls/base.py'" in c for _, c in calls)
    assert any("cat '/testbed/django/urls/resolvers.py'" in c
               for _, c in calls)


def test_evidence_audit_unreadable_file_never_demotes(monkeypatch):
    # Gagal-aman: cat gagal utk base.py -> kandidat TIDAK didemosi.
    _mock_cat(monkeypatch, {"django/urls/resolvers.py": RESOLVERS_PY})
    text, rows = drv.audit_candidates_evidence("c1", CANDS_12184)
    assert text == CANDS_12184  # urutan asli utuh
    by_file = {r["file"]: r for r in rows}
    assert by_file["django/urls/base.py"]["checked"] is False
    assert by_file["django/urls/base.py"]["evidence_mismatch"] is False


def test_evidence_audit_clean_shortlist_untouched(monkeypatch):
    _mock_cat(monkeypatch, {"django/urls/base.py": RESOLVERS_PY,
                            "django/urls/resolvers.py": RESOLVERS_PY})
    text, rows = drv.audit_candidates_evidence("c1", CANDS_12184)
    assert text == CANDS_12184
    assert all(r["evidence_mismatch"] is False for r in rows)


def test_evidence_audit_malformed_candidates_passthrough(monkeypatch):
    calls = _mock_cat(monkeypatch, {})
    text, rows = drv.audit_candidates_evidence("c1", "bukan candidates.md")
    assert text == "bukan candidates.md" and rows is None
    assert not calls  # bentuk salah -> biar cek DONE/gate yang memvonis


def test_evidence_audit_event_name_in_emit_whitelist():
    """Regresi insiden 2026-07-22: driver memanggil em.event('localize',
    'evidence-audit') tapi whitelist emit.EVENTS belum memuatnya -> ValueError
    runtime SETELAH model selesai (slot l-dev r2 12184 hangus parsial). Test
    unit lain tak menangkap karena emit di-mock. Kunci nama event driver ke
    whitelist sungguhan, tanpa mock."""
    from harness import emit
    assert "evidence-audit" in emit.EVENTS
