"""Test driver LOCALIZE — Lever L-a: cek rentang localize.md saat DONE.

Lahir dari baseline 12747 l-dev r1-r3: model menyetor localize.md dengan
rentang baris melewati akhir file (380-450 pada file 445 baris; juga
713-844). Gate L1 menangkap SETELAH run selesai ("extend beyond the end of
file") tapi driver menerima DONE tanpa cek -> nol retry, run hangus.
Lever: mirror vonis gate di jalur DONE acceptance (standar tunggal dengan
localize_gates), panjang file via docker `wc -l`, fail-closed bila file
tak terbaca.
"""
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


def test_tool_call_marker_triggers_strong_reminder():
    """R3/KH-12: driver LOCALIZE kini menangani mode gagal yang sama (native
    tool-call tanpa fence) dengan pengingat bentuk KUAT (English)."""
    from harness.stages.gemma_protocol import no_action_feedback
    reply = '<|tool_call|>\n{"name": "open", "path": "x.py"}'
    msg = no_action_feedback(reply, drv._ACTION_FORMS)
    assert "```file:" in msg and "```bash" in msg
    for w in ("kamu", "jalankan", "tulis", "berkas"):
        assert w not in msg.lower()
