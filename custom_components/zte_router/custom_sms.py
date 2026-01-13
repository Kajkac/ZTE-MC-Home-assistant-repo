from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from typing import Any, Optional

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SEND_SMS_SERVICE = "send_custom_sms"

# >>> DODANE (START): schema zgodny z oboma wariantami pola telefonu
# - phone (nowy)
# - phone_number (stary)
SEND_SMS_SCHEMA = vol.Schema(
    {
        # możesz wypełnić JEDNO z nich:
        vol.Optional("phone"): cv.string,
        vol.Optional("phone_number"): cv.string,
        vol.Required("message"): cv.string,
    }
)
# >>> DODANE (END)


def _merge_config(entry: ConfigEntry) -> dict[str, Any]:
    data = dict(getattr(entry, "data", {}) or {})
    opts = dict(getattr(entry, "options", {}) or {})
    data.update(opts)
    return data


async def _run_mc_send_sms(
    ip: str,
    password: str,
    username: Optional[str],
    phone: str,
    message: str,
) -> int:
    """
    Uruchamia mc.py jako osobny proces:
      python3 mc.py <ip> <password> 8 [username] <phone> <message>

    mc.py potrafi wypisać śmieci przed JSON-em (np. "Commands received: ['8']")
    więc wycinamy OSTATNI blok JSON ze stdout.
    """
    mc_path = os.path.join(os.path.dirname(__file__), "mc.py")
    if not os.path.exists(mc_path):
        raise RuntimeError(f"mc.py not found at {mc_path}")

    py = sys.executable or "python3"

    args: list[str] = [py, mc_path, ip, password, "8"]
    # mc.py w Twojej wersji przy username=None oczekuje pustego stringa jako placeholder
    if username is None:
        args += ["", phone, message]
    else:
        args += [username, phone, message]

    _LOGGER.debug("Launching mc.py: %s", " ".join(repr(a) for a in args))

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()
    stdout = (stdout_b or b"").decode(errors="replace").strip()
    stderr = (stderr_b or b"").decode(errors="replace").strip()

    _LOGGER.debug("mc.py returncode=%s, stderr=%s", proc.returncode, stderr)

    if proc.returncode != 0:
        raise RuntimeError(f"mc.py exited with code {proc.returncode}. stderr={stderr or 'n/a'}")

    # --- Parsowanie: weź ostatni blok JSON ze stdout ---
    # 1) spróbuj pełny stdout
    try:
        data = json.loads(stdout)
    except Exception:
        # 2) wytnij od ostatniego '{' i dopasuj {...} do końca
        idx = stdout.rfind("{")
        if idx == -1:
            raise RuntimeError(f"mc.py output has no JSON object. raw={stdout[:400]}")
        candidate = stdout[idx:].strip()
        m = re.search(r"\{.*\}\s*\Z", candidate, flags=re.DOTALL)
        if m:
            candidate = m.group(0)
        data = json.loads(candidate)

    status = data.get("8")
    if status is None:
        raise RuntimeError(f"mc.py JSON has no key '8': {data}")

    return int(status)


async def register_custom_sms_service(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rejestruje usługę: zte_router.send_custom_sms"""

    async def _handle(call: ServiceCall) -> None:
        cfg = _merge_config(entry)
        ip = cfg.get("router_ip") or cfg.get("host")
        password = cfg.get("router_password")
        username = cfg.get("router_username")  # opcjonalny

        if not ip or not password:
            raise RuntimeError("ZTE send_custom_sms: missing router_ip/host or router_password in config")

        # >>> DODANE (START): kompatybilność phone vs phone_number
        phone = (call.data.get("phone") or call.data.get("phone_number") or "").strip()
        if not phone:
            raise RuntimeError("ZTE send_custom_sms: provide 'phone' or 'phone_number'")
        # >>> DODANE (END)

        message = (call.data.get("message") or "").strip()
        if not message:
            raise RuntimeError("ZTE send_custom_sms: 'message' is required and cannot be empty")

        status = await _run_mc_send_sms(ip, password, username, phone, message)

        _LOGGER.debug("mc.py SEND_SMS HTTP status: %s", status)
        if status != 200:
            raise RuntimeError(f"ZTE SEND_SMS HTTP status != 200 (got {status})")

    # ważne: nie rejestruj ponownie jeśli już istnieje
    if hass.services.has_service(DOMAIN, SEND_SMS_SERVICE):
        _LOGGER.debug("Service %s.%s already registered", DOMAIN, SEND_SMS_SERVICE)
        return

    hass.services.async_register(
        DOMAIN,
        SEND_SMS_SERVICE,
        _handle,
        schema=SEND_SMS_SCHEMA,
    )
    _LOGGER.info("Registered service %s.%s", DOMAIN, SEND_SMS_SERVICE)
