"""Test API JSON UI log viewer (ui/server.py) — serialisasi + HTTP layer."""
import json

from ui.server import run_index_verdict


# --- fixture artifacts sintetis ---------------------------------------------

def mk_run(root, campaign, case, rerun, verdict=None, pass_l1=None,
           started="2026-07-21T14:03:00+07:00"):
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
                                "verdict": verdict, "wall": 12.3}) + "\n")
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
    assert fail["wall"] == 12.3
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
