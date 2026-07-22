"""Test API JSON UI log viewer (ui/server.py) — serialisasi + HTTP layer."""
import json

from ui.server import run_index_verdict


# --- fixture artifacts sintetis ---------------------------------------------

def mk_run(root, campaign, case, rerun, verdict=None, pass_l1=None,
           started="2026-07-21T14:03:00+07:00", wall="reproduce"):
    """Satu run sintetis: dir + events.jsonl + runs.jsonl (+ verdict.json).

    verdict None -> run hidup tanpa verdict.json.
    """
    camp = root / campaign
    run_id = f"{campaign}--{case}--{rerun}"
    rd = camp / run_id
    rd.mkdir(parents=True)
    (rd / "events.jsonl").write_text(
        json.dumps({"ts": started, "event": "start"}) + "\n",
        encoding="utf-8")
    with (camp / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"run_id": run_id, "event": "start"}) + "\n")
        if verdict is not None:
            f.write(json.dumps({"run_id": run_id, "event": "end",
                                "verdict": verdict, "wall": wall}) + "\n")
    if verdict is not None:
        vj = {"phases": {"reproduce": {"verdict": verdict}},
              "started": started, "finished": started}
        if pass_l1 is not None:
            vj["pass_l1"] = pass_l1
        (rd / "verdict.json").write_text(json.dumps(vj), encoding="utf-8")
    return run_id


# --- run_index_verdict ------------------------------------------------------

def test_run_index_verdict_missing_verdict(tmp_path):
    assert run_index_verdict("r-dev", tmp_path) == ("-", "")


def test_run_index_verdict_broken_verdict(tmp_path):
    (tmp_path / "verdict.json").write_text("{rusak", encoding="utf-8")
    text, icon = run_index_verdict("r-dev", tmp_path)
    assert text == "(verdict.json rusak)" and icon == ""


def test_run_index_verdict_pass(tmp_path):
    rid = mk_run(tmp_path, "r-dev", "django__django-1", "r1",
                 verdict="pass", pass_l1=True)
    text, icon = run_index_verdict("r-dev", tmp_path / "r-dev" / rid)
    assert text == "pass" and icon.startswith("✅")


def test_run_index_verdict_merges_gold_wrong_file(tmp_path):
    rid = mk_run(tmp_path, "l-dev", "django__django-1", "r1", verdict="pass")
    run_dir = tmp_path / "l-dev" / rid
    (run_dir / "gold_eval.json").write_text(
        json.dumps({"qualified": False}), encoding="utf-8")
    text, icon = run_index_verdict("l-dev", run_dir)
    assert text == "wrong-file" and icon.startswith("❌")


# --- api_campaigns ----------------------------------------------------------

def test_api_campaigns_pipeline_order_and_labels(tmp_path):
    from ui.server import api_campaigns
    (tmp_path / "r-dev").mkdir()
    (tmp_path / "z-lain").mkdir()
    out = api_campaigns(tmp_path)
    names = [c["name"] for c in out["campaigns"]]
    # stage pipeline selalu tampil (walau dir belum ada), urut pipeline;
    # kampanye non-pipeline menyusul
    assert names == ["r-dev", "l-dev", "f-dev", "z-lain"]
    assert out["campaigns"][0] == {"name": "r-dev", "label": "REPRODUCE",
                                   "phase": "R"}
    assert out["campaigns"][2]["label"] == "FIX and VERIFY"
    assert out["campaigns"][3] == {"name": "z-lain", "label": "z-lain",
                                   "phase": ""}


def test_api_campaigns_empty_root(tmp_path):
    from ui.server import api_campaigns
    names = [c["name"] for c in api_campaigns(tmp_path)["campaigns"]]
    assert names == ["r-dev", "l-dev", "f-dev"]


# --- api_runs ---------------------------------------------------------------

def test_api_runs_fields_and_order(tmp_path):
    from ui.server import api_runs
    mk_run(tmp_path, "r-dev", "django__django-1", "r1",
           verdict="pass", pass_l1=True,
           started="2026-07-20T10:00:00+07:00")
    mk_run(tmp_path, "r-dev", "sympy__sympy-2", "r1",
           verdict="wrong-logic",
           started="2026-07-21T14:03:00+07:00")
    out = api_runs(tmp_path, "r-dev")
    assert out["campaign"] == "r-dev"
    assert out["total"] == 2 and out["total_pages"] == 1
    # urut started desc: run terbaru dulu
    assert [r["case"] for r in out["runs"]] == \
        ["sympy__sympy-2", "django__django-1"]
    fail = out["runs"][0]
    assert fail["rerun"] == "r1"
    assert fail["verdict"] == "wrong-logic"
    assert fail["status"] == "FAIL" and fail["category"] == "wrong-logic"
    assert fail["wall"] == "reproduce"
    assert fail["started"] == "2026-07-21 14:03"
    ok = out["runs"][1]
    assert ok["status"] == "PASS" and ok["verdict"] == "pass"


def test_api_runs_filter_status_and_q(tmp_path):
    from ui.server import api_runs
    mk_run(tmp_path, "r-dev", "django__django-1", "r1",
           verdict="pass", pass_l1=True)
    mk_run(tmp_path, "r-dev", "django__django-1", "r2",
           verdict="wrong-logic")
    mk_run(tmp_path, "r-dev", "sympy__sympy-2", "r1",
           verdict="wrong-logic")
    out = api_runs(tmp_path, "r-dev", status="FAIL")
    assert out["total"] == 2
    assert all(r["status"] == "FAIL" for r in out["runs"])
    out = api_runs(tmp_path, "r-dev", status="FAIL", q="django")
    assert out["total"] == 1
    assert out["runs"][0]["run_id"] == "r-dev--django__django-1--r2"


def test_api_runs_paging_clamps(tmp_path):
    from ui.server import api_runs
    for i in range(4):
        mk_run(tmp_path, "r-dev", f"case-{i}", "r1",
               verdict="pass", pass_l1=True)
    out = api_runs(tmp_path, "r-dev", page=99, per_page=3)
    assert out["total"] == 4 and out["total_pages"] == 2
    assert out["page"] == 2 and len(out["runs"]) == 1


def test_api_runs_unknown_campaign_empty(tmp_path):
    from ui.server import api_runs
    out = api_runs(tmp_path, "tidak-ada")
    assert out["runs"] == [] and out["total"] == 0


def test_api_runs_run_without_verdict_is_unknown(tmp_path):
    from ui.server import api_runs
    mk_run(tmp_path, "r-dev", "django__django-1", "r1")  # tanpa verdict
    out = api_runs(tmp_path, "r-dev")
    r = out["runs"][0]
    assert r["status"] == "?" and r["verdict"] == "-"
    assert r["category"] == "tanpa verdict.json"


# --- api_cases --------------------------------------------------------------

def test_api_cases_ever_qualified_semantics(tmp_path):
    from ui.server import api_cases
    # case A: r1 gagal, r2 pass -> status case PASS (pernah qualified)
    mk_run(tmp_path, "r-dev", "case-A", "r1", verdict="wrong-logic",
           started="2026-07-20T10:00:00+07:00")
    mk_run(tmp_path, "r-dev", "case-A", "r2", verdict="pass", pass_l1=True,
           started="2026-07-21T10:00:00+07:00")
    # case B: hanya gagal
    mk_run(tmp_path, "r-dev", "case-B", "r1", verdict="wrong-logic")
    out = api_cases(tmp_path, "r-dev")
    assert out["summary"] == {"PASS": 1, "FAIL": 1, "WAIT": 0,
                              "ANOMALY": 0, "?": 0}
    by_id = {c["case_id"]: c for c in out["cases"]}
    assert by_id["case-A"]["status"] == "PASS"
    assert by_id["case-A"]["runs"] == 2
    assert by_id["case-B"]["status"] == "FAIL"
    assert by_id["case-B"]["category"] == "wrong-logic"
    assert by_id["case-B"]["latest_run"] == "r-dev--case-B--r1"


def test_api_cases_summary_stable_under_status_filter(tmp_path):
    from ui.server import api_cases
    mk_run(tmp_path, "r-dev", "case-A", "r1", verdict="pass", pass_l1=True)
    mk_run(tmp_path, "r-dev", "case-B", "r1", verdict="wrong-logic")
    out = api_cases(tmp_path, "r-dev", status="FAIL")
    # summary TIDAK berubah oleh filter status; daftar cases berubah
    assert out["summary"]["PASS"] == 1 and out["summary"]["FAIL"] == 1
    assert out["total"] == 1
    assert out["cases"][0]["case_id"] == "case-B"


def test_api_cases_q_filter_and_paging(tmp_path):
    from ui.server import api_cases
    for i in range(3):
        mk_run(tmp_path, "r-dev", f"django-{i}", "r1",
               verdict="pass", pass_l1=True)
    mk_run(tmp_path, "r-dev", "sympy-9", "r1", verdict="pass", pass_l1=True)
    out = api_cases(tmp_path, "r-dev", q="django", per_page=2, page=2)
    assert out["summary"]["PASS"] == 3      # sympy tersaring oleh q
    assert out["total"] == 3 and out["total_pages"] == 2
    assert len(out["cases"]) == 1


def test_api_cases_empty_campaign(tmp_path):
    from ui.server import api_cases
    out = api_cases(tmp_path, "r-dev")
    assert out["cases"] == [] and out["total"] == 0
    assert out["summary"] == {"PASS": 0, "FAIL": 0, "WAIT": 0,
                              "ANOMALY": 0, "?": 0}


# --- HTTP layer /api/* ------------------------------------------------------

def _get_json(root, path):
    """Start server port-0, GET path, return (status_code, parsed_json)."""
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    from ui.server import make_handler
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{srv.server_port}{path}"
    try:
        try:
            with urllib.request.urlopen(url) as resp:
                assert resp.headers["Content-Type"].startswith(
                    "application/json")
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = json.loads(e.read().decode("utf-8"))
            return e.code, body
    finally:
        srv.shutdown()
        srv.server_close()


def test_http_api_campaigns(tmp_path):
    code, body = _get_json(tmp_path, "/api/campaigns")
    assert code == 200
    assert [c["name"] for c in body["campaigns"]] == \
        ["r-dev", "l-dev", "f-dev"]


def test_http_api_runs_full_roundtrip(tmp_path):
    mk_run(tmp_path, "r-dev", "django__django-1", "r1",
           verdict="pass", pass_l1=True)
    mk_run(tmp_path, "r-dev", "sympy__sympy-2", "r1", verdict="wrong-logic")
    code, body = _get_json(
        tmp_path, "/api/runs?c=r-dev&status=FAIL&q=sympy&page=1&per_page=5")
    assert code == 200
    assert body["total"] == 1
    assert body["runs"][0]["case"] == "sympy__sympy-2"


def test_http_api_cases_roundtrip(tmp_path):
    mk_run(tmp_path, "r-dev", "case-A", "r1", verdict="pass", pass_l1=True)
    code, body = _get_json(tmp_path, "/api/cases?c=r-dev")
    assert code == 200 and body["summary"]["PASS"] == 1


def test_http_api_missing_c_is_400(tmp_path):
    code, body = _get_json(tmp_path, "/api/runs")
    assert code == 400 and "error" in body


def test_http_api_bad_campaign_name_is_400(tmp_path):
    code, body = _get_json(tmp_path, "/api/runs?c=../etc")
    assert code == 400 and "error" in body


def test_http_api_bad_status_is_400(tmp_path):
    code, body = _get_json(tmp_path, "/api/runs?c=r-dev&status=MAYBE")
    assert code == 400 and "error" in body


def test_http_api_unknown_path_is_404_json(tmp_path):
    code, body = _get_json(tmp_path, "/api/tidak-ada")
    assert code == 404 and "error" in body


def test_http_api_bad_page_falls_back(tmp_path):
    mk_run(tmp_path, "r-dev", "case-A", "r1", verdict="pass", pass_l1=True)
    code, body = _get_json(tmp_path, "/api/runs?c=r-dev&page=xx&per_page=yy")
    assert code == 200 and body["page"] == 1


def test_http_api_internal_error_returns_json_500(tmp_path, monkeypatch):
    # api_runs meledak -> klien tetap dapat JSON 500, bukan koneksi putus
    import ui.server as srv

    def boom(*args, **kwargs):
        raise RuntimeError("meledak")

    monkeypatch.setattr(srv, "api_runs", boom)
    code, body = _get_json(tmp_path, "/api/runs?c=r-dev")
    assert code == 500 and "error" in body


def test_http_api_campaigns_internal_error_returns_json_500(
        tmp_path, monkeypatch):
    # api_campaigns meledak -> JSON 500 juga (paritas guard api_runs)
    import ui.server as srv

    def boom(*args, **kwargs):
        raise RuntimeError("meledak")

    monkeypatch.setattr(srv, "api_campaigns", boom)
    code, body = _get_json(tmp_path, "/api/campaigns")
    assert code == 500 and "error" in body


# --- bundle minor final review ---------------------------------------------

def test_paginate_per_page_zero_is_safe():
    from ui.server import paginate
    items = list(range(3))
    page_items, total = paginate(items, 1, per_page=0)
    assert page_items == [0] and total == 3   # per_page<=0 -> 1


def test_http_api_status_unknown_enum_url_encoded(tmp_path):
    # status "?" ter-URL-encode (%3F) harus lolos enum dan menyaring
    # hanya run tanpa verdict.json
    mk_run(tmp_path, "r-dev", "case-live", "r1")  # tanpa verdict -> "?"
    mk_run(tmp_path, "r-dev", "case-ok", "r1",
           verdict="pass", pass_l1=True)
    code, body = _get_json(tmp_path, "/api/runs?c=r-dev&status=%3F")
    assert code == 200 and body["total"] == 1
    assert body["runs"][0]["case"] == "case-live"


# --- filter status server-side page_index (permintaan Mirza 2026-07-22) ----

def test_page_index_status_filter_across_pages(tmp_path):
    from ui.server import page_index
    # 16 FAIL + 5 PASS: tanpa filter 21 run; dengan status=FAIL paging
    # dihitung dari set terfilter (16 -> 2 halaman) dan PASS tak tampil
    for i in range(16):
        mk_run(tmp_path, "r-dev", f"failcase-{i:02d}", "r1",
               verdict="wrong-logic",
               started=f"2026-07-01T10:{i:02d}:00+07:00")
    for i in range(5):
        mk_run(tmp_path, "r-dev", f"okcase-{i}", "r1", verdict="pass",
               pass_l1=True, started=f"2026-07-02T10:0{i}:00+07:00")
    out = page_index(tmp_path, tab="r-dev", page=1, status="FAIL")
    assert "okcase-" not in out
    assert "16 run cocok" in out
    assert "hal 1/2" in out               # paging ikut set terfilter
    page2 = page_index(tmp_path, tab="r-dev", page=2, status="FAIL")
    assert "failcase-" in page2 and "okcase-" not in page2


def test_page_index_status_carried_in_links(tmp_path):
    from ui.server import page_index
    for i in range(16):
        mk_run(tmp_path, "r-dev", f"failcase-{i:02d}", "r1",
               verdict="wrong-logic",
               started=f"2026-07-01T10:{i:02d}:00+07:00")
    out = page_index(tmp_path, tab="r-dev", page=1, status="FAIL")
    # link tab lain membawa status (filter global lintas stage)
    assert "/?tab=l-dev&status=FAIL" in out
    # pager membawa status
    assert "status=FAIL&page=2" in out
    # radio tercentang sesuai param
    assert "value='FAIL' checked" in out


def test_page_index_status_empty_result_safe(tmp_path):
    from ui.server import page_index
    mk_run(tmp_path, "r-dev", "case-ok", "r1", verdict="pass",
           pass_l1=True)
    out = page_index(tmp_path, tab="r-dev", status="FAIL")
    assert "tidak ada run dengan status ini" in out


def test_page_index_no_status_regression(tmp_path):
    from ui.server import page_index
    mk_run(tmp_path, "r-dev", "case-ok", "r1", verdict="pass",
           pass_l1=True)
    mk_run(tmp_path, "r-dev", "case-bad", "r1", verdict="wrong-logic")
    out = page_index(tmp_path, tab="r-dev")
    assert "case-ok" in out and "case-bad" in out


def test_page_index_case_name_links_to_q_filter(tmp_path):
    from ui.server import page_index
    mk_run(tmp_path, "r-dev", "django__django-1", "r1",
           verdict="pass", pass_l1=True)
    out = page_index(tmp_path, tab="r-dev")
    assert "href='/?tab=r-dev&q=django__django-1'" in out


def test_page_index_case_link_carries_status(tmp_path):
    from ui.server import page_index
    mk_run(tmp_path, "r-dev", "case-bad", "r1", verdict="wrong-logic")
    out = page_index(tmp_path, tab="r-dev", status="FAIL")
    assert "href='/?tab=r-dev&q=case-bad&status=FAIL'" in out


# --- kartu statistik ringkasan + posisi radio (Mirza 2026-07-22) --------

def test_render_stage_summary_cards_markup():
    from ui.server import render_stage_summary
    s = {"total": 4, "pass": 3, "fail": 1, "unknown": 0,
         "items": [
             {"case": "case-a", "rerun": "r2", "status": "PASS",
              "category": "pass", "reasons": []},
             {"case": "case-b", "rerun": "r1", "status": "FAIL",
              "category": "wrong-logic", "reasons": ["x"]},
         ]}
    out = render_stage_summary(s)
    assert "class='scards'" in out
    assert "<div class='num'>4</div><div class='lbl'>cases</div>" in out
    assert "✅ 3" in out and "PASS 75%" in out
    assert "❌ 1" in out and "FAIL 25%" in out
    # bar proporsi + [info] tetap
    assert "class='sbar'" in out and "width:75%" in out
    assert "[info]" in out and "showInfo()" in out


def test_render_stage_summary_cards_wait_only_when_present():
    from ui.server import render_stage_summary
    s = {"total": 2, "pass": 1, "fail": 1, "unknown": 0, "wait": 0,
         "anomaly": 0,
         "items": [
             {"case": "a", "rerun": "r1", "status": "PASS",
              "category": "pass", "reasons": []},
             {"case": "b", "rerun": "r1", "status": "FAIL",
              "category": "fail", "reasons": []},
         ]}
    out = render_stage_summary(s)
    assert "WAIT" not in out.replace("menunggu VERIFY", "")
    s2 = dict(s, wait=1, fail=0,
              items=[{"case": "a", "rerun": "r1", "status": "PASS",
                      "category": "pass", "reasons": []},
                     {"case": "b", "rerun": "r1", "status": "WAIT",
                      "category": "product-pass", "reasons": [],
                      "started": "?"}])
    out2 = render_stage_summary(s2)
    assert "⏳ 1" in out2 and "WAIT 50%" in out2


def test_page_index_radio_directly_below_search(tmp_path):
    from ui.server import page_index
    mk_run(tmp_path, "r-dev", "case-a", "r1", verdict="pass",
           pass_l1=True)
    out = page_index(tmp_path, tab="r-dev")
    i_search = out.index("class='search'")
    i_radio = out.index("class='rfilter'")
    i_summary = out.index("class='summary'")
    assert i_search < i_radio < i_summary


def test_render_stage_summary_fail_zero_card_still_shown():
    # kartu FAIL tetap tampil saat 0 (kampanye 100% pass) — temuan review
    from ui.server import render_stage_summary
    s = {"total": 2, "pass": 2, "fail": 0, "unknown": 0,
         "items": [
             {"case": "a", "rerun": "r1", "status": "PASS",
              "category": "pass", "reasons": []},
             {"case": "b", "rerun": "r1", "status": "PASS",
              "category": "pass", "reasons": []},
         ]}
    out = render_stage_summary(s)
    assert "❌ 0" in out and "FAIL 0%" in out
    assert "✅ 2" in out and "PASS 100%" in out
