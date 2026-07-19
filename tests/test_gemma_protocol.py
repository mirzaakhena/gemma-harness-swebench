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


# --- is_repro_run (r20-r22: heredoc write terhitung "run gagal" phantom) ----

def test_is_repro_run_true_for_actual_runs():
    from harness.stages.gemma_protocol import is_repro_run
    assert is_repro_run("python /testbed/.pipe/repro.py")
    assert is_repro_run("python3 /testbed/.pipe/repro.py 2>&1 | tail -20")
    assert is_repro_run("cd /testbed && python .pipe/repro.py")


def test_is_repro_run_false_for_writes_and_reads():
    from harness.stages.gemma_protocol import is_repro_run
    assert not is_repro_run("cat << 'EOF' > /testbed/.pipe/repro.py\nx\nEOF")
    assert not is_repro_run("cat /testbed/.pipe/repro.py")
    assert not is_repro_run("ls -la /testbed/.pipe/repro.py")


# --- repeated_error_note (r21: error identik 6x berturut-turut) -------------

def test_repeated_error_note_fires_on_identical_consecutive_why():
    from harness.stages.gemma_protocol import repeated_error_note
    why = "repro run exited 1 without REPRO_STATUS: FAIL; last output line: TypeError: bad kwarg"
    note = repeated_error_note(why, why)
    assert note is not None
    assert "again" in note
    assert "TypeError: bad kwarg" in note


def test_repeated_error_note_silent_on_first_or_different():
    from harness.stages.gemma_protocol import repeated_error_note
    assert repeated_error_note(None, "x") is None
    assert repeated_error_note("a", "b") is None


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


# --- judge review (paket hardening bag.2 + ide Mirza: reviewer fresh-context)

def test_parse_review_ok():
    from harness.stages.gemma_protocol import parse_review
    ok, issues = parse_review("Some reasoning...\nREVIEW: OK\n")
    assert ok is True and issues is None


def test_parse_review_issues_carries_list():
    from harness.stages.gemma_protocol import parse_review
    ok, issues = parse_review(
        "REVIEW: ISSUES\n1. The trigger fires before the watcher settles.\n"
        "2. PASS observable is not produced by any source line.\n")
    assert ok is False
    assert "watcher settles" in issues


def test_parse_review_fail_open_on_garbage():
    # Judge bersifat ADVISORY (vonis tetap mekanis) — balasan tak
    # ter-parse tidak boleh memblokir DONE.
    from harness.stages.gemma_protocol import parse_review
    ok, issues = parse_review("I think everything looks fine overall.")
    assert ok is True and issues is None


def test_review_feedback_wraps_issues():
    from harness.stages.gemma_protocol import review_feedback
    msg = review_feedback("1. Trigger too early.")
    assert "review" in msg.lower()
    assert "Trigger too early." in msg
    assert "DONE" in msg


# --- literal_emitted_by_script (r26: lubang self-match token hantu) ---------

def test_literal_emitted_true_for_print_lines():
    from harness.stages.gemma_protocol import literal_emitted_by_script
    script = 'x = 1\nprint("MARKER: watched")\n'
    assert literal_emitted_by_script(script, "MARKER: watched") is True


def test_literal_emitted_false_for_search_lines():
    # Kasus nyata r26: 'Restarting...' hanya ada di baris pencarian
    # `if ... in line` -> bukan marker milik skenario, token hantu.
    from harness.stages.gemma_protocol import literal_emitted_by_script
    script = 'if "Restarting..." in line_inner:\n    ok = True\n'
    assert literal_emitted_by_script(script, "Restarting...") is False


def test_literal_emitted_false_when_absent():
    from harness.stages.gemma_protocol import literal_emitted_by_script
    assert literal_emitted_by_script("print('other')", "MARKER") is False


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


def test_parse_actions_recognizes_candidates_md():
    # Lever L#2 LOCALIZE: blok setoran kandidat baru.
    from harness.stages.gemma_protocol import parse_actions
    acts = parse_actions("```candidates.md\nCANDIDATE 1\nfile: x.py\n```")
    assert len(acts) == 1 and acts[0].kind == "candidates.md"


def test_done_rejection_localize_blocks_on_candidates_error():
    from harness.stages.gemma_protocol import done_rejection_localize
    msg = done_rejection_localize(
        has_localize_md=True, ran_any_bash=True,
        candidates_error="Not done yet: submit candidates.md first.")
    assert msg == "Not done yet: submit candidates.md first."
    assert done_rejection_localize(
        has_localize_md=True, ran_any_bash=True,
        candidates_error=None) is None


def test_parse_pass_observable_strips_surrounding_backticks():
    # r5 nyata (11797, re-test pasca-Paket-Predikat): Gemma membungkus
    # deklarasi dengan backtick markdown -> grep literal gagal -> 51
    # penolakan DONE identik, 60 turn habis (artefak sah, gate qualified).
    # Backtick = kutip markdown, perlakuannya sama dengan '/" (r12).
    from harness.stages.gemma_protocol import parse_pass_observable
    assert (parse_pass_observable("PASS_OBSERVABLE: `OBSERVABLE: GROUP_BY_PRESERVED`\nDONE")
            == "OBSERVABLE: GROUP_BY_PRESERVED")


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


# --- mixed bash block (kelas r35: sed + repro run dalam satu blok) ---------

def test_mixed_block_note_fires_when_extra_commands_present():
    from harness.stages.gemma_protocol import mixed_block_note
    note = mixed_block_note(
        "sed -i 's/x/y/' django/utils/autoreload.py\n"
        "python /testbed/.pipe/repro.py")
    assert note is not None
    assert "fresh sandbox" in note
    assert "were not run" in note


def test_mixed_block_note_silent_for_pure_repro_run():
    from harness.stages.gemma_protocol import mixed_block_note
    assert mixed_block_note("python /testbed/.pipe/repro.py") is None
    assert mixed_block_note(
        "\n# comment\npython /testbed/.pipe/repro.py\n") is None


# --- standar token tunggal + telemetri pair (audit 2026-07-19) -------------

def test_exact_status_requires_exact_line():
    from harness.stages.gemma_protocol import exact_status
    assert exact_status("blah\nREPRO_STATUS: FAIL\n") == "FAIL"
    assert exact_status("REPRO_STATUS: FAIL (Got foo instead)\n") is None
    assert exact_status("REPRO_STATUS: PASS\nREPRO_STATUS: FAIL\n") == "FAIL"
    assert exact_status("no token here") is None


def test_token_format_note_fires_on_trailing_text():
    from harness.stages.gemma_protocol import token_format_note
    note = token_format_note("REPRO_STATUS: FAIL (Got foo instead)\n")
    assert note is not None
    assert "exact" in note.lower()


def test_token_format_note_silent_when_exact_or_absent():
    from harness.stages.gemma_protocol import token_format_note
    assert token_format_note("REPRO_STATUS: FAIL\n") is None
    assert token_format_note("no token at all") is None


def test_fresh_pair_meta_structured():
    from harness.stages.gemma_protocol import fresh_pair_meta
    meta = fresh_pair_meta("x\nREPRO_STATUS: FAIL\n",
                           "REPRO_STATUS: FAIL (extra)\n", 0, 1)
    assert meta["status1"] == "FAIL"
    assert meta["status2"] is None
    assert meta["exit1"] == 0 and meta["exit2"] == 1
    assert "extra" in meta["run2_tail"]
