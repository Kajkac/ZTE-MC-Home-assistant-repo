import json
import time
import logging
import asyncio
from datetime import datetime, timedelta
from homeassistant.helpers.entity_registry import async_get
from homeassistant.helpers.entity import Entity, EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from .const import (
    DOMAIN,
    SENSOR_NAMES,
    MANUFACTURER,
    MODEL,
    UNITS,
    DISABLED_SENSORS_MC889,
    DISABLED_SENSORS_MC888,
    DISABLED_SENSORS_MC801A,
    DISABLED_SENSORS_G5_ULTRA,
    DIAGNOSTICS_SENSORS,
    FLUX_KEYS,
    FLUX_ICON_MAP,
    CONF_ALLOW_STALE_DATA,
    DEFAULT_ALLOW_STALE_DATA,
    ROUTER_TYPE_MC801,
    ROUTER_TYPE_MC888,
    ROUTER_TYPE_MC889,
    ROUTER_TYPE_G5_ULTRA,
)
from .router_backend import run_router_commands
_LOGGER = logging.getLogger(__name__)

def guard_stale_data(update_func):
    async def wrapper(self, *args, **kwargs):
        if not self.coordinator.last_update_success and not self.coordinator.allow_stale_data:
            _LOGGER.warning(f"{self._name}: Clearing state due to failed update and stale data disabled.")
            self._state = None
            if hasattr(self, '_attributes'):
                self._attributes.clear()
            self.async_write_ha_state()
            return
        await update_func(self, *args, **kwargs)
        self.async_write_ha_state()  # <-- ensure state always updates after success
    return wrapper


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.info("Setting up ZTE Router integration")
    
    # Hole die existierenden Coordinators aus hass.data
    coordinators = hass.data[DOMAIN][entry.entry_id]
    coordinator = coordinators["coordinator"]
    sms_coordinator = coordinators["sms_coordinator"]

    config = {**entry.data, **entry.options}
    router_type = entry.data.get("router_type", ROUTER_TYPE_MC801)
    enable_flux = config.get("enable_flux_sensors", True)

    # Extract required config values
    ip = entry.data["router_ip"]
    pwd = entry.data["router_password"]
    user = entry.data.get("router_username", "")
    sms_check_interval = config.get("sms_check_interval", 100)

    disabled_sensors = {
        ROUTER_TYPE_MC889: DISABLED_SENSORS_MC889,
        ROUTER_TYPE_MC888: DISABLED_SENSORS_MC888,
        ROUTER_TYPE_G5_ULTRA: DISABLED_SENSORS_G5_ULTRA,
    }.get(router_type, DISABLED_SENSORS_MC801A)

    sensors = []
    handled_keys = set()

    # Core Sensors
    sensors.extend([
        ConnectedBandsSensor(coordinator, disabled_sensors.get("connected_bands", False)),
        WiFiClientsSensor(coordinator),
        LANClientsSensor(coordinator),
        ConnectedDevicesSensor(coordinator),
        MonthlyUsageSensor(coordinator),
        monthly_tx_gb(coordinator),
        monthly_rx_gb(coordinator),
        DataLeftSensor(coordinator),
        ConnectionUptimeSensor(coordinator),
    ])
    handled_keys.update(["station_list", "lan_station_list", "all_devices"])
    if router_type == ROUTER_TYPE_G5_ULTRA:
        # These keys already back a dedicated switch entity (switch.py); skip
        # them here so the generic sensor loop below doesn't create a
        # redundant duplicate sensor for the same underlying state.
        handled_keys.update(
            ["wifi_onoff", "mobile_data_enable", "upnp_enabled", "dmz_enabled", "dmz_ip", "nat_enabled"]
        )

    # Create and store the SMS coordinator (if not already created)
    sms_coordinator = ZTERouterSMSUpdateCoordinator(hass, ip, pwd, user, router_type, sms_check_interval)
    await sms_coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id]["sms_coordinator"] = sms_coordinator

    # SMS Sensor
    sms_data = sms_coordinator.data.get("sms_data", {}) or {}
    sensors.append(LastSMSSensor(sms_coordinator, sms_data, disabled_sensors.get("last_sms", False)))


    # FLUX Sensors (bleibt wie bisher)
    registry = async_get(hass)
    if enable_flux:
        for key in FLUX_KEYS:
            if key not in handled_keys:
                if key in {"flux_total_usage", "flux_monthly_usage"}:
                    if "flux_total_usage" not in handled_keys:
                        sensors.append(ZTEFluxTotalUsageSensor(coordinator))
                        handled_keys.add("flux_total_usage")
                else:
                    sensors.append(ZTEFluxSensor(coordinator, key))
                    handled_keys.add(key)
    else:
        # Clean up previously created FLUX sensors if they're now disabled
        entity_ids = list(registry.entities.keys())
        for key in FLUX_KEYS:
            unique_id = f"{DOMAIN}_{entry.data['router_ip']}_stat_{key}"
            for eid in entity_ids:
                entity = registry.entities.get(eid)
                if entity and entity.unique_id == unique_id:
                    registry.async_remove(eid)

    # Weiterer Sensor-Setup-Code unverändert...
    diagnostic_keys_to_skip = {
        "session_created", "session_expires_in", "last_command",
        "last_successful_cmd", "last_error", "total_requests", "fetch_latency_ms"
    }

    for key, value in coordinator.data.items():
        if (
            key in handled_keys or
            key in FLUX_KEYS or
            key in diagnostic_keys_to_skip or
            isinstance(value, dict)
        ):
            continue

        name = SENSOR_NAMES.get(key, key)
        sensors.append(ZTERouterSensor(coordinator, name, key, disabled_sensors.get(key, False)))
        handled_keys.add(key)

    async_add_entities(sensors, False)


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
            #_LOGGER.warning(f"_____DATA {parsed}")
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
            update_interval=timedelta(seconds=sms_check_interval),  # Use sms_check_interval
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

class ZTERouterEntity(RestoreEntity, Entity):
    """Base class for ZTE Router sensors to ensure consistent MRO."""

    async def async_added_to_hass(self):
        _LOGGER.info(f"Entity {self.name} added to hass at {datetime.now()}")
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            if hasattr(self, "_attributes"):
                self._attributes.update(last_state.attributes)
            _LOGGER.debug(f"Restored state for {self.name}: {self._state}")
        self.async_on_remove(self.coordinator.async_add_listener(
            lambda: asyncio.ensure_future(self.async_handle_coordinator_update())
        ))
        await self.async_handle_coordinator_update()

    def _get_value(self, key):
        """Strict fetch that respects allow_stale_data."""
        if not self.coordinator.last_update_success and not self.coordinator.allow_stale_data:
            _LOGGER.debug(f"[STRICT MODE] {self.name}: blocked access to stale key '{key}'")
            return None
        return self.coordinator.data.get(key)

    @property
    def is_diagnostics(self) -> bool:
        return getattr(self, "_attr_is_diagnostics", False)

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC if self.is_diagnostics else None

    @property
    def extra_state_attributes(self):
        # Only return attributes if self._attributes is defined
        return getattr(self, "_attributes", {})

# Long delimited-list fields: (separator, unit label for the summarized state).
# The full value is preserved in the "raw_value" attribute.
LIST_SUMMARY_KEYS = {
    "lte_band": (",", "bands"),
    "nr5g_nsa_band_lock": (",", "bands"),
    "nr5g_sa_band_lock": (",", "bands"),
    "lteca": (";", "carriers"),
    "ltecasig": (";", "readings"),
    "nr_neighbor_cell": (";", "neighbors"),
    "lte_neighbor_cell": (";", "neighbors"),
}

class ZTERouterSensor(ZTERouterEntity):
    def __init__(self, coordinator, name, key, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = name
        self._key = key
        self._state = None
        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_is_diagnostics = key in DIAGNOSTICS_SENSORS
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing sensor {self._name} with key {self._key}")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_{self._key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        return self.coordinator.last_update_success or self.coordinator.allow_stale_data

    @property
    def unit_of_measurement(self):
        return UNITS.get(self._key)

    @property
    def is_diagnostics(self):
        return self._attr_is_diagnostics

    @property
    def entity_category(self):
        if self.is_diagnostics:
            return EntityCategory.DIAGNOSTIC
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for sensor {self._name} at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        state_changed = False

        if self.coordinator.data:
            new_state = self.coordinator.data.get(self._key, None)

            if isinstance(new_state, str):
                raw_state = new_state  # Preserve the raw incoming string
                display_state = new_state if new_state.strip() else "n/a"

                # Try to convert PCI from hex if applicable and not empty
                if "pci" in self._key.lower() and new_state.strip():
                    try:
                        raw_state = int(new_state, 16)
                        display_state = raw_state
                        _LOGGER.debug(
                            f"Converted hex PCI value to decimal for key '{self._key}': {raw_state}"
                        )
                    except (ValueError, TypeError):
                        _LOGGER.warning(
                            f"Failed to convert value for key '{self._key}' (expected hex string): {new_state}"
                        )
                        raw_state = new_state
                        display_state = new_state if new_state.strip() else "n/a"

                elif "ngbr_cell_info" in self._key.lower():
                    max_length = 255
                    if len(new_state) > max_length:
                        raw_state = new_state[:max_length]
                        display_state = raw_state
                        _LOGGER.debug(
                            f"Truncated 'ngbr_cell_info' to {max_length} characters for key '{self._key}'."
                        )

                elif self._key in LIST_SUMMARY_KEYS and new_state.strip():
                    # Long delimited lists (band masks, carrier-aggregation legs,
                    # neighbor cells) look ugly as a raw state string on the
                    # device page. Show a short count instead; the full value
                    # is still available as the "raw_value" attribute.
                    separator, unit = LIST_SUMMARY_KEYS[self._key]
                    items = [item for item in new_state.split(separator) if item.strip()]
                    raw_state = f"{len(items)} {unit}"
                    display_state = raw_state
                    self._attributes = {"raw_value": new_state}

                # Compare raw values to detect change
                if raw_state != old_state:
                    self._state = raw_state
                    state_changed = True
                    _LOGGER.info(
                        f"Sensor '{self._name}' updated. Old state: {old_state}, New state: {self._state} (Displayed as: {display_state})"
                    )
                else:
                    _LOGGER.debug(
                        f"Sensor '{self._name}' state unchanged."
                    )

            elif isinstance(new_state, (int, float, bool)):
                if new_state != old_state:
                    self._state = new_state
                    state_changed = True
                    _LOGGER.info(
                        f"Sensor '{self._name}' updated. Old state: {old_state}, New state: {self._state}"
                    )
            else:
                _LOGGER.debug(
                    f"Invalid value type for key '{self._key}' in coordinator data: {type(new_state)}"
                )
        else:
            _LOGGER.warning(
                f"No coordinator data available for sensor '{self._name}'. Retaining last state."
            )

        if state_changed:
            # Optionally expose display value to HA
            self.async_write_ha_state()


class LastSMSSensor(ZTERouterEntity):
    def __init__(self, coordinator, sms_data, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = "Last SMS"

        # Gracefully handle missing or incomplete sms_data
        self._state = self._derive_state_value(sms_data)
        self._attributes = {}

        # Copy all valid keys except "id" to attributes
        if sms_data:
            self._attributes = {k: v for k, v in sms_data.items() if k != "id"}
            self._attributes["content"] = sms_data.get("content", "NO CONTENT")
            if "date" in self._attributes:
                self._attributes["formatted_date"] = self.format_date(self._attributes["date"])
        else:
            self._attributes["content"] = "NO CONTENT"

        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Last SMS sensor with state: {self._state} (SMS ID)")


        # Parse and format the date attribute
        if "date" in self._attributes:
            self._attributes["formatted_date"] = self.format_date(self._attributes["date"])

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state  # Now returning the SMS ID as the state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_last_sms"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        return self.coordinator.last_update_success or self.coordinator.allow_stale_data

    @property
    def extra_state_attributes(self):
        return self._attributes  # Return the content and other attributes

    @property
    def is_diagnostics(self):
        return True  # LastSMS is a diagnostic sensor

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Last SMS sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        sms_data = self.coordinator.data.get("sms_data", {})
        _LOGGER.debug(f"Updating LastSMS sensor with new data: {sms_data}")
        if sms_data:
            self._state = self._derive_state_value(sms_data)
            self._attributes = {k: v for k, v in sms_data.items() if k != "id"}
            self._attributes["content"] = sms_data.get("content", "NO CONTENT")
            if "date" in self._attributes:
                self._attributes["formatted_date"] = self.format_date(self._attributes["date"])
            _LOGGER.info(f"Last SMS sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning("Last SMS sensor: No valid data or update failed. Setting state to Unavailable")
            self._state = "UNKNOWN"
        self.async_write_ha_state()

    def format_date(self, date_str):
        try:
            # Extract the date parts from the string
            parts = date_str.split(',')
            if len(parts) == 7 and all(parts):
                year = int(parts[0]) + 2000  # Assuming the year is in the format 'YY'
                month = int(parts[1])
                day = int(parts[2])
                hour = int(parts[3])
                minute = int(parts[4])
                second = int(parts[5])
                timezone_offset = parts[6]

                # Create a datetime object
                dt = datetime(year, month, day, hour, minute, second)

                # Format the date to a more readable format
                formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")

                # Append timezone offset
                formatted_date += f" UTC{timezone_offset}"

                return formatted_date
            else:
                return date_str  # Return the original string if it doesn't match the expected format
        except ValueError as e:
            _LOGGER.error(f"Error parsing date string {date_str}: {e}")
            return date_str

    @staticmethod
    def _derive_state_value(sms_payload):
        if not sms_payload:
            return "NO DATA"
        candidate = sms_payload.get("id")
        if candidate in (None, ""):
            fallback = sms_payload.get("content") or sms_payload.get("timestamp") or sms_payload.get("date")
            if isinstance(fallback, str):
                candidate = fallback.strip()[:255] or "NO DATA"
            elif fallback is not None:
                candidate = str(fallback)
            else:
                candidate = "NO DATA"
        return str(candidate)
#fixed indent outside of a class
def format_ca_bands(ca_bands, nr5g_action_band):
    _LOGGER.debug(f"Raw ca_bands input: {ca_bands}")
    _LOGGER.debug(f"Raw nr5g_action_band input: {nr5g_action_band}")

    if not ca_bands:
        _LOGGER.debug("No CA bands provided. Returning 'No CA'")
        return "No CA"

    ca_bands_formatted = []

    for band in ca_bands.strip(';').split(';'):
        if not band:
            continue  # Skip empty strings after split

        band_info = band.split(',')
        _LOGGER.debug(f"Parsing CA band string: {band} -> split: {band_info}")

        try:
            if len(band_info) >= 6:
                band_id = band_info[3]
                bandwidth = band_info[5]
            elif len(band_info) >= 5:
                band_id = band_info[0]
                bandwidth = band_info[4]
            else:
                _LOGGER.warning(f"Band info has insufficient parts: {band_info}")
                continue

            formatted_band = f"B{band_id}@{bandwidth}MHz"
            ca_bands_formatted.append(formatted_band)
            _LOGGER.debug(f"Formatted band: {formatted_band}")
        except Exception as e:
            _LOGGER.warning(f"Failed to format band '{band}' due to: {e}")

    if nr5g_action_band:
        ca_bands_formatted.append(nr5g_action_band)
        _LOGGER.debug(f"Appended NR5G action band: {nr5g_action_band}")

    formatted_result = "+".join(ca_bands_formatted)
    _LOGGER.debug(f"Final formatted CA bands string: {formatted_result}")
    return formatted_result


def derive_primary_band_from_lteca(lteca: str):
    if not lteca:
        return None
    chunks = [chunk for chunk in lteca.strip(";").split(";") if chunk]
    if not chunks:
        return None
    first = chunks[0].split(",")
    if len(first) >= 5:
        return {
            "band": first[0],
            "bandwidth": first[4],
        }
    return None

def calculate_enodeb_id(cell_id_value):
    if not cell_id_value:
        return ""
    try:
        if isinstance(cell_id_value, str):
            stripped = cell_id_value.strip()
            if not stripped:
                return ""
            lower = stripped.lower()
            if lower.startswith("0x"):
                numeric = int(lower, 16)
            elif any(ch in lower for ch in "abcdef"):
                numeric = int(lower, 16)
            else:
                numeric = int(lower, 10)
        else:
            numeric = int(cell_id_value)
        return numeric // 256
    except (ValueError, TypeError):
        _LOGGER.debug("Unable to derive eNB ID from cell_id %s", cell_id_value)
        return ""

class ConnectedBandsSensor(ZTERouterEntity):
    def __init__(self, coordinator, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = "Connected Bands"
        self._state = None
        self._attributes = {}
        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_is_diagnostics = True  # Ensure ConnectedBands is marked as diagnostics
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Connected Bands sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_connected_bands"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        return self.coordinator.last_update_success or self.coordinator.allow_stale_data

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def is_diagnostics(self):
        return self._attr_is_diagnostics

    @property
    def entity_category(self):
        if self.is_diagnostics:
            return EntityCategory.DIAGNOSTIC
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Connected Bands sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            rmcc = data.get("rmcc", "")
            rmnc = data.get("rmnc", "")
            cell_id_raw = data.get("cell_id", "")
            cell_id = "" if cell_id_raw in (None, "") else str(cell_id_raw)
            wan_ip = data.get("wan_ipaddr", "")
            main_band = data.get("lte_ca_pcell_band", "")
            main_bandwidth = data.get("lte_ca_pcell_bandwidth", "")
            ca_bands = (
                data.get("lte_multi_ca_scell_info")
                or data.get("lte_multi_ca_scell_sig_info")
                or ""
            )
            if not ca_bands and data.get("lteca"):
                ca_bands = data.get("lteca")
            ca_bands_formatted = format_ca_bands(ca_bands, data.get("nr5g_action_band", ""))

            if getattr(self.coordinator, "router_type", None) == ROUTER_TYPE_G5_ULTRA:
                lteca_block = data.get("lteca", "")
                if (not main_band or not main_bandwidth) and lteca_block:
                    primary = derive_primary_band_from_lteca(lteca_block)
                    if primary:
                        main_band = primary.get("band", main_band)
                        main_bandwidth = primary.get("bandwidth", main_bandwidth)

            # Calculate enbid
            enb_id = calculate_enodeb_id(cell_id_raw if cell_id_raw not in ("", None) else cell_id)

            if main_band and main_bandwidth:
                self._state = f"MAIN:B{main_band}@{main_bandwidth}MHz CA:{ca_bands_formatted}"
            else:
                self._state = "No Bands Connected"

            self._attributes = {
                "rmcc": rmcc or "--",
                "rmnc": rmnc or "--",
                "cell_id": cell_id or "--",
                "wan_ip": wan_ip or "--",
                "main_band": main_band or "--",
                "main_bandwidth": main_bandwidth or "--",
                "ca_bands": ca_bands_formatted or "--",
                "enb_id": enb_id or "--",
            }
            _LOGGER.info(f"Connected Bands sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning("Connected Bands sensor: No valid data or update failed. Setting state to Unavailable")
            self._state = None
        self.async_write_ha_state()


class MonthlyUsageSensor(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Monthly Usage"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Monthly Usage sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_monthly_usage"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        return self.coordinator.last_update_success or self.coordinator.allow_stale_data

    @property
    def unit_of_measurement(self):
        return "GB"

    @property
    def is_diagnostics(self):
        return False  # MonthlyUsage is not a diagnostic sensor

    @property
    def entity_category(self):
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Monthly Usage sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            monthly_tx_bytes = float(data.get("monthly_tx_bytes", 0) or 0)
            monthly_rx_bytes = float(data.get("monthly_rx_bytes", 0) or 0)
            monthly_usage_gb = (monthly_tx_bytes + monthly_rx_bytes) / 1024 / 1024 / 1024
            self._state = round(monthly_usage_gb, 2)
            _LOGGER.info(f"Monthly Usage sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"Monthly Usage sensor: No valid data or update failed. Setting state to Unavailable")
            self._state = None
        self.async_write_ha_state()

#define GB TX sensor
class monthly_tx_gb(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Monthly TX GB"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Monthly TX GB sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_monthly_tx_gb"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        return self.coordinator.last_update_success or self.coordinator.allow_stale_data

    @property
    def unit_of_measurement(self):
        return "GB"

    @property
    def is_diagnostics(self):
        return False  #Monthly GB Sensor is not a diagnostic sensor

    @property
    def entity_category(self):
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Monthly TX GB sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            monthly_tx_bytes = float(data.get("monthly_tx_bytes", 0) or 0)
            monthly_tx_gb = monthly_tx_bytes / 1024 / 1024 / 1024
            self._state = round(monthly_tx_gb, 2)
            _LOGGER.info(f"Monthly TX GB sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"Monthly TX GB sensor: No valid data or update failed. Setting state to Unavailable")
            self._state = None
        self.async_write_ha_state()

#define GB RX sensor
class monthly_rx_gb(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Monthly RX GB"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Monthly RX GB sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_monthly_rx_gb"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        return self.coordinator.last_update_success or self.coordinator.allow_stale_data

    @property
    def unit_of_measurement(self):
        return "GB"

    @property
    def is_diagnostics(self):
        return False  #Monthly GB Sensor is not a diagnostic sensor

    @property
    def entity_category(self):
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Monthly RX GB sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            monthly_rx_bytes = float(data.get("monthly_rx_bytes", 0) or 0)
            monthly_rx_gb = monthly_rx_bytes / 1024 / 1024 / 1024
            self._state = round(monthly_rx_gb, 2)
            _LOGGER.info(f"Monthly RX GB sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"Monthly RX GB sensor: No valid data or update failed. Setting state to Unavailable")
            self._state = None
        self.async_write_ha_state()

#define DataLeftSensor
class DataLeftSensor(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Data Left"
        self._state = None
        self.entity_registry_enabled_default = True
        self._attr_should_poll = False
        self._attr_is_diagnostics = True
        _LOGGER.info(f"Initializing Data Left sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_data_left"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        return self.coordinator.last_update_success or self.coordinator.allow_stale_data

    @property
    def unit_of_measurement(self):
        return "GB"

    @property
    def is_diagnostics(self):
        return True

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Data Left sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        threshold = self.coordinator.config_entry.options.get("monthly_usage_threshold", 200)

        try:
            use_flux = "flux_monthly_tx_bytes" in self.coordinator.data and "flux_monthly_rx_bytes" in self.coordinator.data
            if use_flux:
                tx_bytes = float(self.coordinator.data.get("flux_monthly_tx_bytes") or 0)
                rx_bytes = float(self.coordinator.data.get("flux_monthly_rx_bytes") or 0)
            else:
                tx_bytes = float(self.coordinator.data.get("monthly_tx_bytes") or 0)
                rx_bytes = float(self.coordinator.data.get("monthly_rx_bytes") or 0)

            usage_gb = (tx_bytes + rx_bytes) / 1024 / 1024 / 1024

            # Standard logic
            if usage_gb < threshold:
                data_left = threshold - usage_gb
            else:
                data_left = 50 - (usage_gb % 50)

            self._state = round(data_left, 2)
            _LOGGER.info(f"Data Left sensor updated. Old state: {old_state}, New state: {self._state} (Using FLUX: {use_flux})")

        except Exception as e:
            _LOGGER.warning(f"Failed to calculate Data Left: {e}")
            self._state = None
        
        self._attributes = {
            "usage_source": "FLUX" if use_flux else "NATIVE",
            "used_gb": round(usage_gb, 2),
            "threshold_gb": threshold
        }

        self.async_write_ha_state()


class ConnectionUptimeSensor(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Connection Uptime"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Connection Uptime sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_connection_uptime"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        return self.coordinator.last_update_success or self.coordinator.allow_stale_data

    @property
    def unit_of_measurement(self):
        return UNITS.get("connection_uptime")

    @property
    def is_diagnostics(self):
        return True  # ConnectionUptime is a diagnostic sensor

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Connection Uptime sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            realtime_time = float(self.coordinator.data.get("realtime_time", 0) or 0)
            uptime_hours = realtime_time / 3600
            self._state = round(uptime_hours, 2)
            _LOGGER.info(f"Connection Uptime sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning("Connection Uptime sensor: No valid data or update failed. Setting state to Unavailable")
            self._state = None
        self.async_write_ha_state()

class ConnectedDevicesSensor(ZTERouterEntity):
    def __init__(self, coordinator, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = "Connected Devices"
        self._state = None
        self._attributes = {}
        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_should_poll = False
        _LOGGER.info("Initializing Connected Devices sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_connected_devices"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        return self.coordinator.last_update_success or self.coordinator.allow_stale_data

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def is_diagnostics(self):
        return False  # ✅ This fixes the crash

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Connected Devices sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        if self.coordinator.data:
            station_list = self.coordinator.data.get("station_list", [])
            lan_station_list = self.coordinator.data.get("lan_station_list", [])
            all_devices = self.coordinator.data.get("all_devices")

            if isinstance(all_devices, list) and all_devices:
                total_devices = len(all_devices)
            else:
                total_devices = len(station_list) + len(lan_station_list)
                if total_devices == 0:
                    try:
                        total_devices = int(str(self.coordinator.data.get("wifi_access_sta_num", "0")).strip())
                    except Exception:
                        total_devices = 0

            self._state = total_devices
            self._attributes["station_list"] = station_list
            self._attributes["lan_station_list"] = lan_station_list
            self._attributes["all_devices"] = all_devices if isinstance(all_devices, list) else (station_list + lan_station_list)
            _LOGGER.info(f"Connected Devices updated: {total_devices} devices")
        else:
            _LOGGER.warning("No data available for Connected Devices")
        self.async_write_ha_state()

class WiFiClientsSensor(ZTERouterEntity):
    def __init__(self, coordinator, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = "WiFi Clients"
        self._state = None
        self._attributes = {}
        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_should_poll = False
        _LOGGER.info("Initializing WiFi Clients sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_wifi_clients"

    @property
    def available(self):
        # Add this to clearly indicate availability
        return self._state is not None

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def is_diagnostics(self):
        return False

    async def async_update(self):
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        data = self.coordinator.data if self.coordinator.data else {}
        wifi_clients = data.get("station_list") or []

        formatted_clients = []
        for client in wifi_clients:
            formatted_clients.append({
                "Hostname": client.get("hostname", "--"),
                "MAC Address": client.get("mac_addr", client.get("mac", "--")),
                "IP Address": client.get("ip_addr", client.get("ip", "--")),
                "Speed": f"{client.get('agreed_rate', client.get('speed', '--'))} Mbps",
                "Connected": format_seconds(client.get("connect_time", client.get("online_time", 0))),
                "Address Type": client.get("addr_type", client.get("address_type", "--")),
                "Type": client.get("type", "WiFi"),
            })

        # Firmware BD_A1EUMC888AV1.0.0B06 may not expose station_list reliably.
        if formatted_clients:
            self._state = len(formatted_clients)
            self._attributes["wifi_clients"] = formatted_clients
        else:
            def _as_int(value):
                try:
                    return int(str(value).strip())
                except Exception:
                    return 0

            fallback_count = max(
                _as_int(data.get("wifi_access_sta_num")),
                _as_int(data.get("wifi_chip1_ssid1_access_sta_num")) +
                _as_int(data.get("wifi_chip2_ssid1_access_sta_num")) +
                _as_int(data.get("wifi_chip1_ssid2_access_sta_num")) +
                _as_int(data.get("wifi_chip2_ssid2_access_sta_num")),
            )
            self._state = fallback_count
            self._attributes["wifi_clients"] = []
            self._attributes["fallback_count_source"] = "wifi_access_sta_num"

        _LOGGER.info(f"WiFi Clients sensor updated: {self._state} devices")
        self.async_write_ha_state()


class LANClientsSensor(ZTERouterEntity):
    def __init__(self, coordinator, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = "LAN Clients"
        self._state = None
        self._attributes = {}
        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_should_poll = False
        _LOGGER.info("Initializing LAN Clients sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def available(self):
        # Add this to clearly indicate availability
        return self._state is not None

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_lan_clients"

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def is_diagnostics(self):
        return False

    async def async_update(self):
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        data = self.coordinator.data if self.coordinator.data else {}
        lan_clients = data.get("lan_station_list") or []

        formatted_clients = []
        for client in lan_clients:
            formatted_clients.append({
                "Hostname": client.get("hostname", "--"),
                "MAC Address": client.get("mac_addr", client.get("mac", "--")),
                "IP Address": client.get("ip_addr", client.get("ip", "--")),
                "Speed": f"{client.get('agreed_rate', client.get('speed', '--'))} Mbps",
                "Connected": format_seconds(client.get("connect_time", client.get("online_time", 0))),
                "Address Type": client.get("addr_type", client.get("address_type", "--")),
                "Type": client.get("type", "LAN"),
            })

        self._state = len(formatted_clients)
        self._attributes["lan_clients"] = formatted_clients
        _LOGGER.info(f"LAN Clients sensor updated: {self._state} devices")
        self.async_write_ha_state()



def format_seconds(seconds):
    try:
        seconds = int(seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, sec = divmod(remainder, 60)

        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if sec or not parts:
            parts.append(f"{sec}s")

        return " ".join(parts)
    except (TypeError, ValueError):
        return "--"

BYTE_KEYS = {
    "flux_realtime_tx_bytes",
    "flux_realtime_rx_bytes",
    "flux_monthly_tx_bytes",
    "flux_monthly_rx_bytes",
}

THROUGHPUT_KEYS = {
    "flux_realtime_tx_thrpt",
    "flux_realtime_rx_thrpt",
}

# Fields that hold a descriptive string (e.g. "GB") rather than a number.
# G5 Ultra's ubus backend already resolves these to text; treating them as
# numeric like the rest of the FLUX fields crashes the float() conversion.
TEXT_KEYS = {
    "flux_data_volume_limit_unit",
    "data_volume_limit_unit",
}

class ZTEDataStatisticsSensor(ZTERouterEntity):
    def __init__(self, coordinator, key):
        self.coordinator = coordinator
        self._key = key
        self._name = SENSOR_NAMES.get(key, key)
        self._unit = UNITS.get(key)
        self._state = None
        self.entity_registry_enabled_default = True
        self._attr_should_poll = False
        self._attr_is_diagnostics = key in FLUX_KEYS
        _LOGGER.debug(f"[FLUX] Initialized ZTEDataStatisticsSensor: {self._name} | Diagnostic: {self._attr_is_diagnostics}")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        raw = self._get_value(self._key)
        _LOGGER.debug(f"[FLUX] {self._name}: Raw value = {repr(raw)}")

        if raw in [None, "", "null"]:
            _LOGGER.warning(f"[FLUX] {self._name}: Missing or empty value")
            return None if not self.coordinator.allow_stale_data else "N/A"

        if self._key in TEXT_KEYS:
            return str(raw).strip()

        try:
            clean_raw = str(raw).strip()
            value = int(float(clean_raw))
            _LOGGER.debug(f"[FLUX] {self._name}: Parsed value = {value}")

            if self._key in BYTE_KEYS:
                gb_value = value / 1024 / 1024 / 1024
                self._unit = "GB"
                if gb_value >= 1024:
                    self._unit = "TB"
                    result = round(gb_value / 1024, 2)
                else:
                    result = round(gb_value, 2)
                return result

            elif self._key.endswith("_time"):
                return self.format_seconds(value)

            elif self._key in THROUGHPUT_KEYS:
                return self.format_throughput(value)

            elif self._key == "date_month":
                return f"{clean_raw[:4]}-{clean_raw[4:6]}" if len(clean_raw) == 8 else clean_raw

            return value

        except (ValueError, TypeError) as e:
            _LOGGER.warning(f"[FLUX] {self._name}: Failed to convert value '{raw}' - {e}")
            return None if not self.coordinator.allow_stale_data else "N/A"


    @property
    def unit_of_measurement(self):
        if self._key in BYTE_KEYS:
            return self._unit
        elif self._key in THROUGHPUT_KEYS:
            return None
        return self._unit

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_stat_{self._key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": "ZTE",
            "model": "MC Series",
        }

    @property
    def is_diagnostics(self):
        return self._attr_is_diagnostics

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC if self.is_diagnostics else None

    async def async_update(self):
        _LOGGER.debug(f"[FLUX] Manual update requested for {self._name}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        _LOGGER.debug(f"[FLUX] Coordinator update triggered for {self._name}")
        self.async_write_ha_state()

    def format_seconds(self, seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        sec = seconds % 60
        return f"{hours}h {minutes}m {sec}s"

    def format_throughput(self, bps):
        if bps >= 1_000_000:
            return f"{bps / 1_000_000:.2f} Mbps"
        elif bps >= 1_000:
            return f"{bps / 1_000:.2f} Kbps"
        return f"{bps} bps"

class ZTEFluxSensor(ZTEDataStatisticsSensor):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self._attr_is_diagnostics = True
        self._attr_should_poll = False
        _LOGGER.debug(f"[FLUX] Initialized ZTEFluxSensor: {self._name}")

    @property
    def icon(self):
        return FLUX_ICON_MAP.get(self._key, "mdi:chart-bar")

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

class ZTEFluxTotalUsageSensor(ZTEFluxSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "flux_total_usage")
        self._name = "FLUX Monthly Usage"
        self._unit = "GB"
        _LOGGER.debug(f"[FLUX] Initialized ZTEFluxTotalUsageSensor")

    @property
    def state(self):
        if not self.coordinator.last_update_success and not self.coordinator.allow_stale_data:
            _LOGGER.warning("[FLUX] Total Usage: Clearing state due to failed update and stale data disabled.")
            return None
        try:
            tx_raw = self._get_value("flux_monthly_tx_bytes")
            rx_raw = self._get_value("flux_monthly_rx_bytes")

            tx = int(float(str(tx_raw).strip())) if tx_raw else 0
            rx = int(float(str(rx_raw).strip())) if rx_raw else 0

            total_gb = (tx + rx) / 1024 / 1024 / 1024
            return round(total_gb, 2)

        except Exception as e:
            _LOGGER.warning(f"[FLUX] Total Usage calculation failed: {e}")
            return None

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_stat_flux_total_usage"
