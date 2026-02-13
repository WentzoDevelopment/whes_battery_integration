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
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import *

_LOGGER = logging.getLogger(__name__)


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
        if not columns and not rows:
            _LOGGER.warning("WHES: metrics response bevat geen 'columns' en geen 'rows'.")
        elif not columns:
            _LOGGER.warning("WHES: metrics response bevat geen 'columns' (rows=%d).", len(rows))
        else:
            _LOGGER.warning("WHES: metrics response bevat geen 'rows' (columns=%d).", len(columns))
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
        _LOGGER.debug(
            "WHES: metadata/columns lengte mismatch (metadata=%d, columns=%d); gebruik identity coercers.",
            len(coercers),
            len(columns),
        )
        coercers = [lambda v: v] * len(columns)

    out: List[Dict[str, Any]] = []
    for idx, r in enumerate(rows):
        n = min(len(columns), len(r))
        if n != len(columns):
            _LOGGER.debug(
                "WHES: rij %d heeft %d waarden voor %d kolommen; trailing kolommen worden op None gezet.",
                idx, n, len(columns)
            )
        row_dict: Dict[str, Any] = {}

        for i in range(n):
            val = r[i]
            try:
                val = coercers[i](val)
            except Exception as ce:
                # Laat de ruwe waarde staan als coercion faalt
                _LOGGER.debug("WHES: coercion fout op kolom '%s': %r (behoud ruwe waarde).", columns[i], ce)
            row_dict[columns[i]] = val

        # Vul ontbrekende trailing kolommen met None
        for j in range(n, len(columns)):
            row_dict[columns[j]] = None

        out.append(row_dict)

    _LOGGER.debug("WHES: metrics_to_kv_list -> %d rijen, %d kolommen.", len(out), len(columns))
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
        t0 = time.perf_counter()
        try:
            _LOGGER.debug(
                "WHES: POST %s (params=%s, body_keys=%s)",
                path, list((params or {}).keys()), list((json_body or {}).keys())
            )
            async with self._session.post(
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                status = resp.status
                # NB: raise_for_status zal bij 4xx/5xx exception gooien (we loggen dat in except)
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                dt_ms = int((time.perf_counter() - t0) * 1000)
                # compacte shape logging zonder data te dumpen
                size_hint = len(str(data)) if data is not None else 0
                _LOGGER.debug(
                    "WHES: POST %s -> %d in %d ms (resp_size≈%d chars)",
                    path, status, dt_ms, size_hint
                )
                return data
        except aiohttp.ClientResponseError as cre:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            _LOGGER.exception("WHES: HTTP fout %s bij POST %s (na %d ms)", cre.status, path, dt_ms)
            raise
        except aiohttp.ClientError as ce:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            _LOGGER.exception("WHES: Netwerkfout bij POST %s: %r (na %d ms)", path, ce, dt_ms)
            raise
        except ValueError as ve:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            _LOGGER.exception("WHES: JSON decode fout bij POST %s: %r (na %d ms)", path, ve, dt_ms)
            raise
        except Exception as e:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            _LOGGER.exception("WHES: Onverwachte fout bij POST %s: %r (na %d ms)", path, e, dt_ms)
            raise

    async def validate(self) -> None:
        """Lichtgewicht probe-call om credentials te valideren."""
        end_ms = now_ms()
        start_ms = end_ms - 30_000
        ems_path = f"/pangu/v1/projects/{self._project_id}/devices/{self._device_id}/ems/metrics"
        await self._post(ems_path, json_body={
            "start": start_ms, "end": end_ms, "sample_by": "10s", "columns": ["ems_soc"],
        })

    async def fetch_bundle(self, poll_seconds: int = 60, overlap_seconds: int = 15, sample_by: str = "10s") -> Dict[
        str, Any]:
        end_ms = now_ms()
        start_ms = end_ms - (poll_seconds + overlap_seconds) * 1000

        _LOGGER.debug(
            "WHES: fetch_bundle window start=%d end=%d (poll=%ds, overlap=%ds, sample_by=%s)",
            start_ms, end_ms, poll_seconds, overlap_seconds, sample_by
        )

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
        if not ems_rows:
            _LOGGER.error("WHES: EMS metrics leeg voor device_id=%s (window=%d..%d).", self._device_id, start_ms,
                          end_ms)
        else:
            _LOGGER.debug("WHES: EMS metrics ontvangen: %d rijen.", len(ems_rows))

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
                "ac_history_positive_power_in_kwh",
                "ac_history_negative_power_in_kwh",
            ],
        }
        amm_raw = await self._post(ammeter_path, json_body=ammeter_body)
        amm_rows = metrics_to_kv_list(amm_raw)
        if not amm_rows:
            _LOGGER.error(
                "WHES: Ammeter metrics leeg voor ammeter_id=%s (window=%d..%d).",
                self._ammeter_id, start_ms, end_ms
            )
        else:
            _LOGGER.debug("WHES: Ammeter metrics ontvangen: %d rijen.", len(amm_rows))

        ems_last = ems_rows[-1] if ems_rows else {}
        amm_last = normalize_power(amm_rows[-1]) if amm_rows else {}

        return {"ems": ems_last, "ammeter": amm_last}


async def validate_credentials(hass: HomeAssistant, data: dict) -> tuple[bool, str | None]:
    """Probe-call om keys/IDs te valideren in de config flow."""
    session = async_get_clientsession(hass)
    client = WhesClient(
        session=session,
        base_url=data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
        api_key=data[CONF_API_KEY],
        api_secret=data[CONF_API_SECRET],
        project_id=data[CONF_PROJECT_ID],
        device_id=data[CONF_DEVICE_ID],
        ammeter_id=data[CONF_AMMETER_ID],
    )
    try:
        await client.validate()
        return True, None
    except aiohttp.ClientResponseError as e:
        if e.status in (401, 403):
            return False, "invalid_auth"
        return False, "cannot_connect"
    except Exception:
        return False, "cannot_connect"
