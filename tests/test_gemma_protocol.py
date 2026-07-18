"""Test parser protokol teks driver Gemma (stage REPRODUCE).

Model membalas dengan fenced block:
  ```bash ...```            -> jalankan command di sandbox
  ```file:/abs/path ...```  -> tulis file di sandbox
  ```repro.md ...```        -> artefak final repro.md
Penanda selesai: baris `SELESAI` di luar fenced block.
"""
from harness.stages.gemma_protocol import Action, has_done, parse_actions


def test_parse_bash_block():
    text = "Aku cek dulu.\n```bash\nls /testbed\n```\n"
    acts = parse_actions(text)
    assert acts == [Action(kind="bash", arg=None, body="ls /testbed")]


def test_parse_file_block_with_path():
    text = "```file:/testbed/.pipe/repro.py\nprint('hi')\n```"
    acts = parse_actions(text)
    assert acts[0].kind == "file"
    assert acts[0].arg == "/testbed/.pipe/repro.py"
    assert acts[0].body == "print('hi')"


def test_parse_repro_md_block():
    text = "```repro.md\nSYMPTOM: x\n```"
    acts = parse_actions(text)
    assert acts[0].kind == "repro.md"
    assert acts[0].body == "SYMPTOM: x"


def test_parse_multiple_blocks_order_preserved():
    text = ("```file:/testbed/.pipe/repro.py\nA\n```\n"
            "lalu jalankan:\n"
            "```bash\npython /testbed/.pipe/repro.py\n```\n")
    kinds = [a.kind for a in parse_actions(text)]
    assert kinds == ["file", "bash"]


def test_parse_no_block_returns_empty():
    assert parse_actions("cuma teks biasa tanpa block") == []


def test_parse_tolerates_crlf():
    text = "```bash\r\necho hi\r\n```\r\n"
    acts = parse_actions(text)
    assert acts[0].body == "echo hi"


def test_parse_ignores_other_languages():
    text = "```python\nprint('bukan aksi')\n```"
    assert parse_actions(text) == []


def test_has_done_outside_block():
    assert has_done("kerja beres.\nSELESAI\n")
    assert not has_done("belum selesai bekerja")


def test_has_done_ignores_inside_block():
    text = "```bash\necho SELESAI\n```\nlanjut dulu"
    assert not has_done(text)


def test_multiline_file_body_preserved():
    body = "import os\n\nif True:\n    print('x')"
    text = f"```file:/testbed/.pipe/repro.py\n{body}\n```"
    assert parse_actions(text)[0].body == body


def test_parse_localize_md_block():
    text = "```localize.md\nchosen: 1\nfile: django/utils/autoreload.py\n```"
    acts = parse_actions(text)
    assert acts[0].kind == "localize.md"
    assert acts[0].body.startswith("chosen: 1")


# --- done_rejection_reason (aturan bukti-dulu-baru-SELESAI) -----------------

def test_done_accepted_with_md_and_observed_fail():
    from harness.stages.gemma_protocol import done_rejection_reason
    assert done_rejection_reason(has_repro_md=True, observed_fail=True) is None


def test_done_rejected_without_observed_fail():
    from harness.stages.gemma_protocol import done_rejection_reason
    reason = done_rejection_reason(has_repro_md=True, observed_fail=False)
    assert reason is not None and "REPRO_STATUS: FAIL" in reason


def test_done_rejected_without_repro_md():
    from harness.stages.gemma_protocol import done_rejection_reason
    reason = done_rejection_reason(has_repro_md=False, observed_fail=True)
    assert reason is not None and "repro.md" in reason


# --- done_rejection_localize (bukti eksplorasi dulu baru SELESAI) -----------

def test_localize_done_accepted_with_md_and_exploration():
    from harness.stages.gemma_protocol import done_rejection_localize
    assert done_rejection_localize(has_localize_md=True, ran_any_bash=True) is None


def test_localize_done_rejected_without_md():
    from harness.stages.gemma_protocol import done_rejection_localize
    reason = done_rejection_localize(has_localize_md=False, ran_any_bash=True)
    assert reason is not None and "localize.md" in reason


def test_localize_done_rejected_without_exploration():
    from harness.stages.gemma_protocol import done_rejection_localize
    reason = done_rejection_localize(has_localize_md=True, ran_any_bash=False)
    assert reason is not None and "eksplorasi" in reason
