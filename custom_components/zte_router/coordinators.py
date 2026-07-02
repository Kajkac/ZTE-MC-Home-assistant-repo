"""Data update coordinators for the ZTE Router integration."""

import json
import logging
import time
from datetime import datetime, timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .router_backend import run_router_commands

_LOGGER = logging.getLogger(__name__)


def extract_json(output):
    try:
        return output[output.index('{'):output.rindex('}')+1]
    except ValueError:
        return "{}"


class ZTERouterDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, ip, pwd, user, router_type, interval, allow_stale_data=True):
        self.ip_entry = ip
        self.password_entry = pwd
        self.username_entry = user
        self.router_type = router_type
        self.config_entry = None
        self._data = {}
        self.allow_stale_data = allow_stale_data
        _LOGGER.info(f"Initializing ZTERouterDataUpdateCoordinator with Ping check interval: {interval} seconds")
        super().__init__(
            hass, _LOGGER, name="zte_router", update_interval=timedelta(seconds=interval)
        )

    async def _async_update_data(self):
        _LOGGER.info("Starting _async_update_data in ZTERouterDataUpdateCoordinator at %s", datetime.now())
        new_data = {}
        keys = {3: "dynamic_data", 7: "status_data", 16: "client_data"}
        cmds = ','.join(map(str, keys.keys()))

        try:
            raw = await self.hass.async_add_executor_job(self.run_router_script, cmds)
            parsed = json.loads(extract_json(raw))
            if parsed:
                for cmd, label in keys.items():
                    cmd_str = str(cmd)
                    cmd_data = parsed.get(cmd_str, {})
                    if isinstance(cmd_data, dict) and "error" not in cmd_data:
                        new_data[label] = cmd_data
                        new_data.update(cmd_data)
                    else:
                        _LOGGER.warning(
                            f"[ZTE] Command {cmd} ({label}) failed or returned no data this cycle, "
                            f"keeping previous values for its fields: {cmd_data}"
                        )
            else:
                _LOGGER.warning("[ZTE] Empty overall response, no data parsed.")
        except Exception as e:
            _LOGGER.error(f"[ZTE] Failed to fetch data: {e}")
            if not self.allow_stale_data:
                raise UpdateFailed(f"[ZTE] Critical failure fetching data: {e}")
            _LOGGER.warning(f"[ZTE] Allowing stale data due to error: {e}")

        if not new_data and not self.allow_stale_data:
            raise UpdateFailed("[ZTE] No valid data obtained from router.")

        # Merge onto the existing data instead of replacing it wholesale, so a single
        # sub-command failing on one poll (e.g. a transient ubus error) doesn't wipe
        # out unrelated, still-valid fields from the last successful poll.
        self._data = {**self._data, **new_data} if new_data else self._data
        return self._data

    def run_router_script(self, cmd):
        attempt = 0
        retries = 3
        delay = 2
        while attempt < retries:
            try:
                return run_router_commands(
                    self.router_type,
                    self.ip_entry,
                    self.password_entry,
                    self.username_entry,
                    str(cmd),
                )
            except Exception as err:
                attempt += 1
                if attempt < retries:
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise err


class ZTERouterSMSUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, ip, password_entry, username_entry, router_type, sms_check_interval):
        self.ip_entry = ip
        self.password_entry = password_entry
        self.username_entry = username_entry if username_entry else ""
        self.router_type = router_type
        self._data = {}
        _LOGGER.info(f"Initializing SMSUpdateCoordinator with SMS check interval: {sms_check_interval} seconds")
        super().__init__(
            hass,
            _LOGGER,
            name="zte_router_sms",
            update_interval=timedelta(seconds=sms_check_interval),
        )

    async def _async_update_data(self):
        _LOGGER.info("Starting _async_update_data in ZTERouterSMSUpdateCoordinator at %s", datetime.now())
        new_data = {}
        keys = {6: "sms_data"}
        cmds = ','.join(map(str, keys.keys()))

        try:
            raw = await self.hass.async_add_executor_job(self.run_router_script, cmds)
            parsed = json.loads(extract_json(raw))
            _LOGGER.debug(f"SMS parsed data: {parsed}")
            if parsed:
                for cmd, label in keys.items():
                    cmd_str = str(cmd)
                    cmd_data = parsed.get(cmd_str, {})
                    if isinstance(cmd_data, dict):
                        new_data[label] = cmd_data
                        new_data.update(cmd_data)
                    else:
                        _LOGGER.warning(f"Unexpected cmd_data format for command {cmd}: {cmd_data}")

                self._data.update(new_data)
            else:
                _LOGGER.warning("SMS coordinator received empty data.")

        except Exception as err:
            _LOGGER.error(f"Error during _async_update_data (SMS): {err}")

        return self._data

    def run_router_script(self, command):
        try:
            return run_router_commands(
                self.router_type,
                self.ip_entry,
                self.password_entry,
                self.username_entry,
                str(command),
            )
        except Exception as err:
            _LOGGER.error(f"Error running SMS command {command}: {err}")
            raise
