"""Test parser protokol teks driver Gemma (stage REPRODUCE).

Model membalas dengan fenced block:
  ```bash ...```            -> jalankan command di sandbox
  ```file:/abs/path ...```  -> tulis file di sandbox
  ```repro.md ...```        -> artefak final repro.md
Penanda selesai: baris `DONE` di luar fenced block (protokol berbahasa
Inggris penuh — keputusan Mirza 2026-07-18).
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
    assert has_done("work complete.\nDONE\n")
    assert not has_done("not done yet, still working")


def test_has_done_ignores_inside_block():
    text = "```bash\necho DONE\n```\nstill going"
    assert not has_done(text)


def test_has_done_must_be_exact_line():
    assert not has_done("DONE-ish\n")
    assert not has_done("I will be DONE soon\n")


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
    assert reason is not None and "exploration" in reason


def test_rejection_messages_are_english():
    from harness.stages.gemma_protocol import (done_rejection_localize,
                                               done_rejection_reason,
                                               observable_rejection)
    msgs = [
        done_rejection_reason(has_repro_md=False, observed_fail=True),
        done_rejection_reason(has_repro_md=True, observed_fail=False),
        done_rejection_localize(has_localize_md=False, ran_any_bash=True),
        done_rejection_localize(has_localize_md=True, ran_any_bash=False),
        observable_rejection("Detected change"),
        observable_rejection(None),
    ]
    indonesian_markers = ("Belum", "kamu", "dulu", "serahkan", "jalankan")
    for m in msgs:
        assert m is not None
        for word in indonesian_markers:
            assert word not in m, f"pesan ke model masih ber-Indonesia: {m!r}"


# --- format reminder (r11: fence non-action membakar 11 turn) ---------------

def test_has_fences_true_for_python_fence():
    from harness.stages.gemma_protocol import has_fences
    assert has_fences("```python\nprint('x')\n```") is True


def test_has_fences_false_without_fence():
    from harness.stages.gemma_protocol import has_fences
    assert has_fences("just prose, no blocks") is False


def test_format_reminder_names_valid_forms():
    from harness.stages.gemma_protocol import format_reminder
    msg = format_reminder()
    assert "```bash" in msg
    assert "```file:" in msg
    assert "```python" in msg  # menyebut bentuk yang TIDAK dieksekusi


# --- next-step nudge (r13: loop degeneratif write-run-FAIL berulang) --------

def test_next_step_nudge_fires_when_fail_seen_but_no_md():
    from harness.stages.gemma_protocol import next_step_nudge
    msg = next_step_nudge(observed_fail=True, has_repro_md=False)
    assert msg is not None
    assert "repro.md" in msg
    assert "DONE" in msg


def test_next_step_nudge_silent_otherwise():
    from harness.stages.gemma_protocol import next_step_nudge
    assert next_step_nudge(observed_fail=False, has_repro_md=False) is None
    assert next_step_nudge(observed_fail=True, has_repro_md=True) is None


# --- retry_reason (telemetri: alasan spesifik per retry di events.jsonl) ----

def test_retry_reason_carries_exit_code_and_last_line():
    from harness.stages.gemma_protocol import retry_reason
    why = retry_reason("Traceback ...\nTypeError: bad kwarg\n", 1)
    assert "exited 1" in why
    assert "TypeError: bad kwarg" in why


def test_retry_reason_handles_empty_output():
    from harness.stages.gemma_protocol import retry_reason
    why = retry_reason("", 2)
    assert "exited 2" in why
    assert "no output" in why


def test_retry_reason_truncates_long_lines():
    from harness.stages.gemma_protocol import retry_reason
    why = retry_reason("x" * 500, 0, max_len=120)
    assert len(why) <= 120


# --- fresh-sandbox pre-check 2x (r16 state-dependence; r20 flakiness) -------

def test_fresh_pair_ok_when_both_fail():
    from harness.stages.gemma_protocol import fresh_pair_rejection
    out = "blah\nREPRO_STATUS: FAIL\n"
    assert fresh_pair_rejection(out, out) is None


def test_fresh_pair_rejects_missing_token_with_self_contained_rule():
    from harness.stages.gemma_protocol import fresh_pair_rejection
    msg = fresh_pair_rejection("REPRO_STATUS: FAIL\n",
                               "Traceback ...\nFileNotFoundError: repro_project\n")
    assert msg is not None
    assert "FileNotFoundError: repro_project" in msg
    assert "inside the script itself" in msg  # quote self-contained dari kontrak


def test_fresh_pair_rejects_inconsistent_runs_with_repeatable_rule():
    from harness.stages.gemma_protocol import fresh_pair_rejection
    msg = fresh_pair_rejection("REPRO_STATUS: FAIL\n", "REPRO_STATUS: PASS\n")
    assert msg is not None
    assert "identical output" in msg  # quote repeatable dari kontrak


def test_fresh_pair_adds_positive_control_rule_when_control_mentioned():
    from harness.stages.gemma_protocol import fresh_pair_rejection
    msg = fresh_pair_rejection(
        "REPRO_STATUS: FAIL\n",
        "ERROR: Positive control failed. Settings change didn't trigger reload.\n")
    assert msg is not None
    assert "positive control" in msg


# --- PASS_OBSERVABLE (lever r10: klaim observable diverifikasi mekanis) -----

def test_parse_pass_observable_found():
    from harness.stages.gemma_protocol import parse_pass_observable
    text = ("1. The source is ...\n"
            "PASS_OBSERVABLE: changed, reloading.\n\nDONE\n")
    assert parse_pass_observable(text) == "changed, reloading."


def test_parse_pass_observable_ignores_fenced_blocks():
    from harness.stages.gemma_protocol import parse_pass_observable
    text = "```bash\necho 'PASS_OBSERVABLE: inside-fence'\n```\nDONE\n"
    assert parse_pass_observable(text) is None


def test_parse_pass_observable_missing_or_empty():
    from harness.stages.gemma_protocol import parse_pass_observable
    assert parse_pass_observable("no declaration here\nDONE") is None
    assert parse_pass_observable("PASS_OBSERVABLE:   \nDONE") is None


def test_parse_pass_observable_strips_surrounding_quotes():
    # r12 nyata: Gemma mendeklarasikan PASS_OBSERVABLE: 'changed, reloading.'
    # (dengan kutip) -> grep literal gagal padahal string-nya sah di source.
    from harness.stages.gemma_protocol import parse_pass_observable
    assert (parse_pass_observable("PASS_OBSERVABLE: 'changed, reloading.'\nDONE")
            == "changed, reloading.")
    assert (parse_pass_observable('PASS_OBSERVABLE: "Watching for file changes"\nDONE')
            == "Watching for file changes")


def test_parse_pass_observable_keeps_unmatched_quote():
    from harness.stages.gemma_protocol import parse_pass_observable
    assert (parse_pass_observable("PASS_OBSERVABLE: it's watched\nDONE")
            == "it's watched")


def test_observable_candidates_full_string_first():
    from harness.stages.gemma_protocol import observable_candidates
    cands = observable_candidates("changed, reloading.")
    assert cands[0] == "changed, reloading."


def test_observable_candidates_tolerates_rendered_suffix():
    # r14 nyata: deklarasi bentuk runtime "…with StatReloader" sedangkan
    # source menyimpan template "…with %s" — trim kata belakang harus
    # menghasilkan kandidat yang match source.
    from harness.stages.gemma_protocol import observable_candidates
    cands = observable_candidates("Watching for file changes with StatReloader")
    assert "Watching for file changes with" in cands


def test_observable_candidates_tolerates_rendered_prefix():
    from harness.stages.gemma_protocol import observable_candidates
    cands = observable_candidates("manage.py changed, reloading.")
    assert "changed, reloading." in cands


def test_observable_candidates_keeps_minimum_two_words():
    from harness.stages.gemma_protocol import observable_candidates
    cands = observable_candidates("Detected change")
    assert cands == ["Detected change"]  # tak ada trim di bawah 2 kata


def test_observable_rejection_missing_asks_for_declaration():
    from harness.stages.gemma_protocol import observable_rejection
    msg = observable_rejection(None)
    assert "PASS_OBSERVABLE:" in msg


def test_observable_rejection_not_found_names_the_string():
    from harness.stages.gemma_protocol import observable_rejection
    msg = observable_rejection("Detected change")
    assert "Detected change" in msg
    assert "source" in msg
