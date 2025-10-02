from __future__ import annotations
import base64
import hashlib
import hmac
import random
import time
from collections import OrderedDict, Counter
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse, parse_qs, quote
import aiohttp


# ===== helpers uit jouw main.py (aangepast naar async usage) =====
def now_ms() -> int:
    return int(time.time() * 1000)


_DEF_COERCERS: Dict[str, Callable[[Any], Any]] = {
    "DOUBLE": lambda v: None if v is None else float(v),
    "VARCHAR": lambda v: None if v is None else str(v),
    "TIMESTAMP": lambda v: None if v is None else int(v),
}


def _unique_columns(cols: List[str]) -> List[str]:
    """
    Zorgt dat kolomnamen uniek worden (col, col_2, col_3, ...),
    voor het geval de API dubbele kolomnamen retourneert.
    """
    seen = Counter()
    out: List[str] = []
    for c in cols:
        seen[c] += 1
        out.append(c if seen[c] == 1 else f"{c}_{seen[c]}")
    return out


def metrics_to_kv_list(
    metrics_resp: dict,
    *,
    extra_coercers: Optional[Dict[str, Callable[[Any], Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Converteert het WHES metrics-formaat (columns/rows/metadata) naar
    een lijst van dicts [{col: value, ...}, ...].
    """
    data = (metrics_resp or {}).get("data") or {}
    columns: List[str] = list(data.get("columns") or [])
    rows: List[List[Any]] = list(data.get("rows") or [])
    metadata: List[str] = list(data.get("metadata") or [])

    if not columns or not rows:
        return []

    columns = _unique_columns(columns)

    base = dict(_DEF_COERCERS)
    if extra_coercers:
        base.update(extra_coercers)

    # Bouw coercers op basis van metadata; fallback = identity
    coercers: List[Callable[[Any], Any]] = [
        base.get(str(m).upper(), lambda v: v) for m in (metadata or [None] * len(columns))
    ]
    if len(coercers) != len(columns):
        coercers = [lambda v: v] * len(columns)

    out: List[Dict[str, Any]] = []
    for r in rows:
        n = min(len(columns), len(r))
        row_dict: Dict[str, Any] = {}

        for i in range(n):
            val = r[i]
            try:
                val = coercers[i](val)
            except Exception:
                # Laat de ruwe waarde staan als coercion faalt
                pass
            row_dict[columns[i]] = val

        # Vul ontbrekende trailing kolommen met None
        for j in range(n, len(columns)):
            row_dict[columns[j]] = None

        out.append(row_dict)

    return out


def normalize_power(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keert het teken van site/grid vermogens om (optioneel),
    als jouw toepassing import/export zo verwacht.
    """
    for k in ("ac_active_power", "ac_active_powers_0", "ac_active_powers_1", "ac_active_powers_2"):
        if k in row and row[k] is not None:
            row[k] = -row[k]
    return row


def canonical_path_and_query(full_url: str, extra_params: dict | None = None) -> str:
    """
    Maakt een canonieke path+query string met alfabetisch geordende keys.
    Houdt rekening met parse_qs (lijsten) en extra_params.
    """
    extra_params = extra_params or {}
    parsed = urlparse(full_url)
    path = parsed.path

    qs_from_url = parse_qs(parsed.query)
    merged = {**qs_from_url, **extra_params} if (qs_from_url and extra_params) else (qs_from_url or extra_params)

    if not merged:
        return path

    ordered = OrderedDict(sorted(merged.items()))
    parts = []
    for k, v in ordered.items():
        if isinstance(v, list):
            joined = ",".join(quote(str(x)) for x in v)
            parts.append(f"{quote(str(k))}={joined}")
        else:
            parts.append(f"{quote(str(k))}={quote(str(v))}")

    return f"{path}?" + "&".join(parts)


class WhesClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
        api_secret: str,
        project_id: str,
        device_id: str,
        ammeter_id: str,
    ) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self._project_id = project_id
        self._device_id = device_id
        self._ammeter_id = ammeter_id

    def _signed_headers(self, method: str, full_url: str, params: dict | None = None) -> Dict[str, str]:
        headers_ordered = OrderedDict(
            [
                ("x-wts-date", str(int(time.time() * 1000))),
                ("x-wts-signature-method", "HMAC-SHA1"),
                ("x-wts-signature-nonce", str(random.randint(10_000_000, 99_999_999))),
                ("x-wts-signature-version", "1.0"),
            ]
        )

        string_to_sign = f"{method.upper()}" + "".join(f"{k}: {v}" for k, v in headers_ordered.items())
        canonical = canonical_path_and_query(full_url, params)
        string_to_sign += canonical

        digest = hmac.new(self._api_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
        signature = base64.standard_b64encode(digest).decode("utf-8")

        headers_ordered["Authorization"] = f"wts {self._api_key}:{signature}"
        return dict(headers_ordered)

    async def _post(self, path: str, json_body: dict | None = None, params: dict | None = None) -> dict:
        url = f"{self._base}{path}"
        headers = self._signed_headers("POST", url, params)
        async with self._session.post(
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def fetch_bundle(self, poll_seconds: int = 60, overlap_seconds: int = 15) -> Dict[str, Any]:
        end_ms = now_ms()
        start_ms = end_ms - (poll_seconds + overlap_seconds) * 1000
        sample_by = "10s"

        # EMS
        ems_path = f"/pangu/v1/projects/{self._project_id}/devices/{self._device_id}/ems/metrics"
        ems_body = {
            "start": start_ms,
            "end": end_ms,
            "sample_by": sample_by,
            "columns": [
                "ems_soc",
                "ems_soh",
                "ems_state",
                "ems_dc_power_neg",
                "ems_dc_power_pos",
                "ems_ac_active_power",
                "ems_ac_frequency",
                "ems_history_input_energy",
                "ems_history_output_energy",
                "ems_ac_active_power_A",
                "ems_ac_active_power_B",
                "ems_ac_active_power_C",
            ],
        }
        ems_raw = await self._post(ems_path, json_body=ems_body)
        ems_rows = metrics_to_kv_list(ems_raw)
        ems_last = ems_rows[-1] if ems_rows else {}

        # Ammeter
        ammeter_path = f"/pangu/v1/projects/{self._project_id}/ammeters/{self._ammeter_id}/metrics"
        ammeter_body = {
            "start": start_ms,
            "end": end_ms,
            "sample_by": sample_by,
            "columns": [
                "ac_active_power",
                "ac_active_powers_0",
                "ac_active_powers_1",
                "ac_active_powers_2",
            ],
        }
        amm_raw = await self._post(ammeter_path, json_body=ammeter_body)
        amm_rows = metrics_to_kv_list(amm_raw)
        amm_last = normalize_power(amm_rows[-1]) if amm_rows else {}

        # Zelfde datastructuur als jouw bundel (arrays met max 1 element)
        return {
            "ems": [ems_last] if ems_last else [],
            "ammeter": [amm_last] if amm_last else [],
        }
