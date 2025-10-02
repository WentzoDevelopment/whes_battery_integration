from __future__ import annotations

import asyncio
import base64, hashlib, hmac, random, time
from collections import OrderedDict, Counter
from typing import Any, Dict, List
from urllib.parse import parse_qs, quote, urlparse
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta

from .const import *

def _unique_columns(cols: List[str]) -> List[str]:
    seen = Counter(); out=[]
    for c in cols:
        seen[c]+=1; out.append(c if seen[c]==1 else f"{c}_{seen[c]}")
    return out

def metrics_to_kv_list(metrics_resp: dict) -> List[Dict[str, Any]]:
    data = (metrics_resp or {}).get("data") or {}
    columns = list(data.get("columns") or [])
    rows = list(data.get("rows") or [])
    metadata = list(data.get("metadata") or [])

    if not columns or not rows:
        return []

    columns = _unique_columns(columns)
    out=[]
    for r in rows:
        row={}
        for i, col in enumerate(columns):
            row[col] = r[i] if i < len(r) else None
        out.append(row)
    return out

def normalize_power_row(row: Dict[str, Any]) -> Dict[str, Any]:
    for k in ("ac_active_power","ac_active_powers_0","ac_active_powers_1","ac_active_powers_2"):
        if k in row and row[k] is not None:
            try: row[k] = -float(row[k])
            except: pass
    return row

def _canonical_path_and_query(full_url: str, extra_params: dict | None = None) -> str:
    extra_params = extra_params or {}
    parsed = urlparse(full_url); path = parsed.path
    qs_from_url = parse_qs(parsed.query)
    merged = extra_params if not qs_from_url else (qs_from_url if not extra_params else {**qs_from_url, **extra_params})
    if not merged: return path
    ordered = OrderedDict(sorted(merged.items()))
    parts=[]
    for k,v in ordered.items():
        if isinstance(v,list):
            joined = ",".join(quote(str(x)) for x in v); parts.append(f"{quote(str(k))}={joined}")
        else:
            parts.append(f"{quote(str(k))}={quote(str(v))}")
    return f"{path}?" + "&".join(parts)

def _signed_headers(api_key: str, api_secret: str, method: str, full_url: str, params: dict | None = None) -> Dict[str,str]:
    headers = OrderedDict([
        ("x-wts-date", str(int(time.time()*1000))),
        ("x-wts-signature-method","HMAC-SHA1"),
        ("x-wts-signature-nonce", str(random.randint(10_000_000, 99_999_999))),
        ("x-wts-signature-version","1.0"),
    ])
    s = f"{method.upper()}\n" + "".join(f"{k}:{v}\n" for k,v in headers.items())
    s += _canonical_path_and_query(full_url, params)
    sig = base64.standard_b64encode(hmac.new(api_secret.encode(), s.encode(), hashlib.sha1).digest()).decode()
    headers["Authorization"] = f"wts {api_key}:{sig}"
    return dict(headers)

async def _post_json(session: aiohttp.ClientSession, base_url: str, api_key: str, api_secret: str, path: str, json_body: dict | None = None, params: dict | None = None) -> dict:
    url = f"{base_url}{path}"
    headers = _signed_headers(api_key, api_secret, "POST", url, params)
    async with session.post(url, headers=headers, params=params, json=json_body, timeout=aiohttp.ClientTimeout(total=30)) as r:
        txt = await r.text()
        if r.status != 200:
            raise RuntimeError(f"WHES HTTP {r.status}: {txt}")
        return await r.json()

async def validate_credentials(hass: HomeAssistant, data: dict) -> tuple[bool, str | None]:
    """Kleine probe-call om keys/IDs te valideren in de config flow."""
    session = async_get_clientsession(hass)
    try:
        # lichtgewicht: korte window met 1 kolom
        end_ms = int(time.time()*1000); start_ms = end_ms-30000
        body={"start": start_ms, "end": end_ms, "sample_by": data.get(CONF_SAMPLE_BY, DEFAULT_SAMPLE_BY), "columns": ["ems_soc"]}
        path=f"/pangu/v1/projects/{data[CONF_PROJECT_ID]}/devices/{data[CONF_DEVICE_ID]}/ems/metrics"
        await _post_json(session, data.get(CONF_BASE_URL, DEFAULT_BASE_URL).rstrip("/"),
                         data[CONF_API_KEY], data[CONF_API_SECRET], path, json_body=body)
        return True, None
    except Exception as e:
        msg = str(e).lower()
        if "401" in msg or "403" in msg: return False, "invalid_auth"
        return False, "cannot_connect"

class WhesCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        self.session = async_get_clientsession(hass)
        interval = max(MIN_SCAN_INTERVAL, int(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        super().__init__(hass, logger=None, name="whes_coordinator", update_interval=timedelta(seconds=interval))

    async def _async_update_data(self) -> dict:
        d = self.entry.data
        end_ms = int(time.time()*1000); start_ms = end_ms - (int(d.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)) + 15)*1000
        sample = d.get(CONF_SAMPLE_BY, DEFAULT_SAMPLE_BY)
        base = d.get(CONF_BASE_URL, DEFAULT_BASE_URL).rstrip("/")

        ems_body = {"start": start_ms, "end": end_ms, "sample_by": sample, "columns": [
            "ems_soc","ems_soh","ems_dc_power_neg","ems_dc_power_pos","ems_ac_active_power",
            "ems_ac_frequency","ems_history_input_energy","ems_history_output_energy",
            "ems_ac_active_power_A","ems_ac_active_power_B","ems_ac_active_power_C"
        ]}
        amm_body = {"start": start_ms, "end": end_ms, "sample_by": sample, "columns": [
            "ac_active_power","ac_active_powers_0","ac_active_powers_1","ac_active_powers_2"
        ]}

        ems_path = f"/pangu/v1/projects/{d[CONF_PROJECT_ID]}/devices/{d[CONF_DEVICE_ID]}/ems/metrics"
        amm_path = f"/pangu/v1/projects/{d[CONF_PROJECT_ID]}/ammeters/{d[CONF_AMMETER_ID]}/metrics"

        try:
            ems_json, amm_json = await asyncio.gather(
                _post_json(self.session, base, d[CONF_API_KEY], d[CONF_API_SECRET], ems_path, json_body=ems_body),
                _post_json(self.session, base, d[CONF_API_KEY], d[CONF_API_SECRET], amm_path, json_body=amm_body),
            )
            ems_rows = metrics_to_kv_list(ems_json)
            amm_rows = [normalize_power_row(r) for r in metrics_to_kv_list(amm_json)]
            return {"ems": (ems_rows[-1] if ems_rows else {}), "ammeter": (amm_rows[-1] if amm_rows else {})}
        except Exception as e:
            raise UpdateFailed(str(e)) from e
