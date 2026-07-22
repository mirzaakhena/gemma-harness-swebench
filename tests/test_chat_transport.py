"""Test util transport bersama (lever infra-abort — port pola R12).

Lahir dari bangkai ber-verdict 15902 r4-r9 & 14855 r4-r9 (KH-22): driver
REPRODUCE/LOCALIZE crash URLError/10060 pra-turn-1 tervonis `repro-missing`
biasa. Pola R12 (is_transport_error / chat_with_retry / ChatTransportError)
diekstrak dari run_fix_gemma ke harness/stages/chat_transport.py supaya
KETIGA driver memakai klasifikasi yang sama, plus dua primitif baru:
- write_infra_abort: penanda mesin-terbaca di run dir (dibaca gate & batch);
- preflight_endpoint: ping ringan sebelum container/model dibakar.
"""
import http.client
import json
import urllib.error

import pytest

import harness.stages.chat_transport as ct


# --- klasifikasi transport (identik dgn R12 di run_fix_gemma) ---------------

def test_is_transport_error_classification():
    # Transport (boleh retry): koneksi putus/timeout/half-open.
    assert ct.is_transport_error(urllib.error.URLError("refused"))
    assert ct.is_transport_error(TimeoutError("read timed out"))
    assert ct.is_transport_error(ConnectionResetError())
    assert ct.is_transport_error(http.client.RemoteDisconnected("closed"))
    # BUKAN transport (jangan retry): server merespons / response tak valid.
    assert not ct.is_transport_error(
        urllib.error.HTTPError("u", 400, "bad request", {}, None))
    assert not ct.is_transport_error(ValueError("bad json"))
    assert not ct.is_transport_error(KeyError("choices"))


def test_r12_constants_named():
    assert ct.CHAT_READ_TIMEOUT_S == 600
    assert ct.CHAT_RETRIES == 3
    assert ct.CHAT_BACKOFF_BASE_S >= 1


def test_chat_with_retry_backs_off_then_succeeds_via_chat_fn():
    calls, delays = [], []

    def flaky(endpoint, model, messages):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.URLError("connection reset")
        return "ok reply"

    out = ct.chat_with_retry("http://x", "m", [], sleep=delays.append,
                             chat_fn=flaky)
    assert out == "ok reply"
    assert len(calls) == 3
    assert delays == [ct.CHAT_BACKOFF_BASE_S, ct.CHAT_BACKOFF_BASE_S * 2]


def test_chat_with_retry_final_failure_raises_infra_class():
    delays = []

    def dead(endpoint, model, messages):
        raise urllib.error.URLError("host unreachable")

    with pytest.raises(ct.ChatTransportError) as ei:
        ct.chat_with_retry("http://x", "m", [], sleep=delays.append,
                           chat_fn=dead)
    assert "unreachable" in str(ei.value)
    assert len(delays) == ct.CHAT_RETRIES


def test_chat_with_retry_does_not_retry_valid_response_errors():
    calls = []

    def bad_json(endpoint, model, messages):
        calls.append(1)
        raise ValueError("invalid json body")

    with pytest.raises(ValueError):
        ct.chat_with_retry("http://x", "m", [],
                           sleep=lambda s: (_ for _ in ()).throw(
                               AssertionError("tak boleh sleep")),
                           chat_fn=bad_json)
    assert len(calls) == 1


# --- reuse lintas driver: SATU kelas, SATU klasifikasi ----------------------

def test_all_three_drivers_share_the_same_transport_primitives():
    import harness.stages.run_fix_gemma as fdrv
    import harness.stages.run_localize_gemma as ldrv
    import harness.stages.run_reproduce_gemma as rdrv
    for drv in (fdrv, rdrv, ldrv):
        assert drv.ChatTransportError is ct.ChatTransportError
        assert drv.is_transport_error is ct.is_transport_error
        assert drv.CHAT_READ_TIMEOUT_S == ct.CHAT_READ_TIMEOUT_S
        assert drv.CHAT_RETRIES == ct.CHAT_RETRIES
        assert drv.CHAT_BACKOFF_BASE_S == ct.CHAT_BACKOFF_BASE_S


# --- write_infra_abort: penanda mesin-terbaca di run dir --------------------

def test_write_infra_abort_writes_machine_readable_marker(tmp_path):
    payload = ct.write_infra_abort(tmp_path, reason="preflight",
                                   stage="reproduce", turns_model_used=0)
    p = tmp_path / "infra_abort.json"
    assert p.is_file()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data == payload
    assert data["reason"] == "preflight"
    assert data["stage"] == "reproduce"
    assert data["turns_model_used"] == 0
    assert data["ts"]  # ISO timestamp terisi


def test_write_infra_abort_carries_detail_and_turns(tmp_path):
    ct.write_infra_abort(tmp_path, reason="chat transport failure",
                         stage="localize", turns_model_used=21,
                         detail="URLError(TimeoutError(10060))")
    data = json.loads((tmp_path / "infra_abort.json")
                      .read_text(encoding="utf-8"))
    assert data["turns_model_used"] == 21
    assert "10060" in data["detail"]


def test_infra_abort_filename_constant():
    # Batch runner (is_void_infra_run) & gate mencari nama file ini.
    assert ct.INFRA_ABORT_FILENAME == "infra_abort.json"


# --- preflight_endpoint: ping ringan sebelum container/model dibakar --------

class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_preflight_constants_named():
    assert ct.PREFLIGHT_TIMEOUT_S == 10
    assert ct.PREFLIGHT_RETRIES == 1


def test_preflight_ok_hits_models_endpoint(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(ct, "_urlopen", fake_urlopen)
    ct.preflight_endpoint("http://10.8.0.86:8000/v1")  # tidak raise
    assert seen["url"] == "http://10.8.0.86:8000/v1/models"
    assert seen["timeout"] == ct.PREFLIGHT_TIMEOUT_S


def test_preflight_http_error_means_endpoint_alive(monkeypatch):
    # HTTPError = server MERESPONS (walau 4xx/5xx) -> endpoint hidup,
    # preflight lolos (klasifikasi R12 yang sama: HTTPError bukan transport).
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)

    monkeypatch.setattr(ct, "_urlopen", fake_urlopen)
    ct.preflight_endpoint("http://x/v1")  # tidak raise


def test_preflight_transport_failure_retries_once_then_raises(monkeypatch):
    calls, delays = [], []

    def dead(req, timeout):
        calls.append(1)
        raise urllib.error.URLError(TimeoutError(10060))

    monkeypatch.setattr(ct, "_urlopen", dead)
    with pytest.raises(ct.ChatTransportError) as ei:
        ct.preflight_endpoint("http://x/v1", sleep=delays.append)
    assert len(calls) == ct.PREFLIGHT_RETRIES + 1  # 1 percobaan + 1 retry
    assert len(delays) == ct.PREFLIGHT_RETRIES
    assert "preflight" in str(ei.value)


def test_preflight_recovers_on_retry(monkeypatch):
    calls = []

    def flaky(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionResetError()
        return _FakeResponse()

    monkeypatch.setattr(ct, "_urlopen", flaky)
    ct.preflight_endpoint("http://x/v1", sleep=lambda s: None)  # tidak raise
    assert len(calls) == 2
