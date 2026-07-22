"""Util transport bersama driver Gemma — pola R12 diekstrak dari run_fix_gemma.

Lever "infra-abort" (KH-22, katalog entri "bangkai ber-verdict"): driver
REPRODUCE/LOCALIZE yang crash URLError/10060 pra-turn-1 dulu tervonis
`repro-missing` biasa dan mencemari statistik wall (15902 r4-r9: 6 bangkai;
14855: 5). Modul ini menyatukan:
- klasifikasi transport + retry-backoff (R12, perilaku IDENTIK dgn versi
  run_fix_gemma sebelumnya — testnya tetap hijau);
- `write_infra_abort`: penanda mesin-terbaca di run dir, dibaca gate
  (verdict `infra-abort`) dan batch runner (`is_void_infra_run`);
- `preflight_endpoint`: ping ringan sebelum container/model dibakar —
  endpoint mati terdeteksi dalam detik, bukan setelah slot rerun hangus.
"""
from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# --- R12: konstanta timeout/retry (docs/rekomendasi-lever §7 butir 3) -------
# Bukti 12184 r11 & 15388 r9: koneksi HTTP ke vLLM jadi half-open (host
# sleep) dan driver menunggu SELAMANYA. Kebijakan: gagal CEPAT dan jujur.
CHAT_READ_TIMEOUT_S = 600   # read-timeout HTTP model — generasi bisa lama,
                            # jadi longgar TAPI berhingga.
CHAT_RETRIES = 3            # retry transport maksimal setelah gagal pertama.
CHAT_BACKOFF_BASE_S = 5     # jeda backoff naik: 5, 10, 20 dtk (x2 per retry).

# --- lever infra-abort: pre-flight ping (murah, sebelum container start) ----
PREFLIGHT_TIMEOUT_S = 10    # ping ringan; endpoint sehat menjawab jauh
                            # lebih cepat dari ini.
PREFLIGHT_RETRIES = 1       # satu retry — flapping singkat masih termaafkan.
PREFLIGHT_BACKOFF_S = 3     # jeda sebelum retry preflight.

# Nama penanda mesin-terbaca di run dir. Dibaca run_repro_gates /
# run_localize_gates (verdict `infra-abort`) dan scripts/run_rlfv_batch
# (is_void_infra_run) — JANGAN diubah tanpa menyisir konsumennya.
INFRA_ABORT_FILENAME = "infra_abort.json"


class ChatTransportError(RuntimeError):
    """R12: kegagalan TRANSPORT final ke endpoint model — kelas INFRA,
    bukan kesalahan model. Ditangkap main() driver utk abort cepat+jujur."""


def is_transport_error(e: BaseException) -> bool:
    """R12: klasifikasi retry — hanya kegagalan TRANSPORT yang boleh
    diulang (idempoten-aman). HTTPError = server MERESPONS (response valid
    walau error) -> bukan transport; error parse response juga bukan."""
    if isinstance(e, urllib.error.HTTPError):
        return False
    return isinstance(e, (urllib.error.URLError, http.client.HTTPException,
                          TimeoutError, OSError))


def chat(endpoint: str, model: str, messages: list[dict],
         timeout: int = CHAT_READ_TIMEOUT_S) -> str:
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 2048,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    # timeout = socket timeout urlopen: berlaku utk connect DAN tiap read —
    # koneksi half-open (R12) berujung timeout, bukan gantung selamanya.
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"] or ""


def chat_with_retry(endpoint: str, model: str, messages: list[dict],
                    retries: int = CHAT_RETRIES,
                    backoff_base: int = CHAT_BACKOFF_BASE_S,
                    log=None, sleep=time.sleep, chat_fn=None) -> str:
    """R12: panggilan model dengan retry-backoff KHUSUS kegagalan transport.

    Tiap percobaan MEMBUAT ULANG koneksi (urlopen tak me-reuse koneksi) —
    koneksi half-open lama tidak dipakai lagi. Kegagalan transport final ->
    ChatTransportError (kelas infra); kegagalan non-transport diteruskan
    apa adanya tanpa retry. `chat_fn` (default: chat modul ini) membiarkan
    tiap driver menyuntik chat modulnya sendiri — monkeypatch test pada
    `drv.chat` tetap bekerja."""
    if chat_fn is None:
        chat_fn = chat
    attempt = 0
    while True:
        try:
            return chat_fn(endpoint, model, messages)
        except Exception as e:
            if not is_transport_error(e):
                raise
            if attempt >= retries:
                raise ChatTransportError(
                    f"model endpoint transport failure after "
                    f"{attempt + 1} attempts: {e!r}") from e
            delay = backoff_base * (2 ** attempt)
            attempt += 1
            if log is not None:
                log(f"[driver] chat transport error: {e!r}; "
                    f"retry {attempt}/{retries} in {delay}s "
                    "(fresh connection)")
            sleep(delay)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_infra_abort(run_dir: Path | str, *, reason: str, stage: str,
                      turns_model_used: int, detail: str | None = None
                      ) -> dict:
    """Tulis penanda infra-abort mesin-terbaca di run dir (append-only:
    hanya run MILIK SENDIRI yang ditandai, tak pernah menyentuh run lama).

    Konsumen: gate (vonis `infra-abort`, bukan repro-missing/syntax-fail)
    dan batch runner (eksklusi dari denominator percobaan, KH-22)."""
    payload = {"reason": reason, "stage": stage, "ts": _now_iso(),
               "turns_model_used": turns_model_used}
    if detail is not None:
        payload["detail"] = detail
    p = Path(run_dir) / INFRA_ABORT_FILENAME
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return payload


def _urlopen(req, timeout):
    """Indirection tipis supaya test bisa menyuntik tanpa monkeypatch
    urllib global."""
    return urllib.request.urlopen(req, timeout=timeout)


def preflight_endpoint(endpoint: str, timeout: int = PREFLIGHT_TIMEOUT_S,
                       retries: int = PREFLIGHT_RETRIES,
                       backoff_s: int = PREFLIGHT_BACKOFF_S,
                       log=None, sleep=time.sleep) -> None:
    """Ping ringan GET <endpoint>/models SEBELUM container/model dibakar.

    Endpoint mati terdeteksi di sini = run dir minimal + exit cepat, bukan
    slot rerun hangus (KH-22: 5 slot terbakar dalam 2 gelombang flapping).
    HTTPError = server merespons -> hidup (klasifikasi R12 yang sama).
    Kegagalan transport final -> ChatTransportError."""
    url = endpoint.rstrip("/") + "/models"
    attempt = 0
    while True:
        try:
            with _urlopen(urllib.request.Request(url), timeout=timeout):
                pass
            return
        except urllib.error.HTTPError:
            return  # server MERESPONS (walau 4xx/5xx) -> endpoint hidup
        except Exception as e:
            if not is_transport_error(e):
                raise  # salah konfigurasi dkk — bukan urusan preflight
            if attempt >= retries:
                raise ChatTransportError(
                    f"preflight ping {url} failed after "
                    f"{attempt + 1} attempts: {e!r}") from e
            attempt += 1
            if log is not None:
                log(f"[driver] preflight transport error: {e!r}; "
                    f"retry {attempt}/{retries} in {backoff_s}s")
            sleep(backoff_s)
