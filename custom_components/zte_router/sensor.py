import logging
from datetime import datetime
from homeassistant.helpers.entity_registry import async_get
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    ROUTER_TYPE_MC801,
    ROUTER_TYPE_MC888,
    ROUTER_TYPE_MC889,
    ROUTER_TYPE_G5_ULTRA,
)
from .sensor_base import ZTERouterEntity, guard_stale_data
from .sensor_bands import ConnectedBandsSensor
from .sensor_flux import ZTEFluxSensor, ZTEFluxTotalUsageSensor
from .coordinators import (
    ZTERouterDataUpdateCoordinator,
    ZTERouterSMSUpdateCoordinator,
    extract_json,
)

_LOGGER = logging.getLogger(__name__)

# Re-exported for backwards compatibility -- these used to live in this file
# and other modules (or third-party tooling) may still import them from here.
__all__ = [
    "ZTERouterDataUpdateCoordinator",
    "ZTERouterSMSUpdateCoordinator",
    "extract_json",
    "ConnectedBandsSensor",
    "ZTEFluxSensor",
    "ZTEFluxTotalUsageSensor",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Setting up ZTE Router integration")

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
            [
                "wifi_onoff", "mobile_data_enable", "upnp_enabled", "dmz_enabled", "dmz_ip", "nat_enabled",
                "wifi_2g_enabled", "wifi_5g_enabled", "lock_lte_cell", "lock_nr_cell",
            ]
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
        _LOGGER.debug(f"Initializing sensor {self._name} with key {self._key}")

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
        _LOGGER.debug(f"Manual update requested for sensor {self._name} at {datetime.now()}")
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
                    _LOGGER.debug(
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
                    _LOGGER.debug(
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
        _LOGGER.debug(f"Initializing Last SMS sensor with state: {self._state} (SMS ID)")

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
        _LOGGER.debug(f"Manual update requested for Last SMS sensor at {datetime.now()}")
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
            _LOGGER.debug(f"Last SMS sensor updated. Old state: {old_state}, New state: {self._state}")
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


class MonthlyUsageSensor(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Monthly Usage"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.debug(f"Initializing Monthly Usage sensor")

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
        _LOGGER.debug(f"Manual update requested for Monthly Usage sensor at {datetime.now()}")
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
            _LOGGER.debug(f"Monthly Usage sensor updated. Old state: {old_state}, New state: {self._state}")
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
        _LOGGER.debug(f"Initializing Monthly TX GB sensor")

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
        _LOGGER.debug(f"Manual update requested for Monthly TX GB sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            monthly_tx_bytes = float(data.get("monthly_tx_bytes", 0) or 0)
            monthly_tx_gb = monthly_tx_bytes / 1024 / 1024 / 1024
            self._state = round(monthly_tx_gb, 2)
            _LOGGER.debug(f"Monthly TX GB sensor updated. Old state: {old_state}, New state: {self._state}")
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
        _LOGGER.debug(f"Initializing Monthly RX GB sensor")

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
        _LOGGER.debug(f"Manual update requested for Monthly RX GB sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            monthly_rx_bytes = float(data.get("monthly_rx_bytes", 0) or 0)
            monthly_rx_gb = monthly_rx_bytes / 1024 / 1024 / 1024
            self._state = round(monthly_rx_gb, 2)
            _LOGGER.debug(f"Monthly RX GB sensor updated. Old state: {old_state}, New state: {self._state}")
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
        _LOGGER.debug(f"Initializing Data Left sensor")

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
        _LOGGER.debug(f"Manual update requested for Data Left sensor at {datetime.now()}")
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
            _LOGGER.debug(f"Data Left sensor updated. Old state: {old_state}, New state: {self._state} (Using FLUX: {use_flux})")

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
        _LOGGER.debug(f"Initializing Connection Uptime sensor")

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
        _LOGGER.debug(f"Manual update requested for Connection Uptime sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    @guard_stale_data
    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            realtime_time = float(self.coordinator.data.get("realtime_time", 0) or 0)
            uptime_hours = realtime_time / 3600
            self._state = round(uptime_hours, 2)
            _LOGGER.debug(f"Connection Uptime sensor updated. Old state: {old_state}, New state: {self._state}")
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
        _LOGGER.debug("Initializing Connected Devices sensor")

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
        _LOGGER.debug(f"Manual update requested for Connected Devices sensor at {datetime.now()}")
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
            _LOGGER.debug(f"Connected Devices updated: {total_devices} devices")
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
        _LOGGER.debug("Initializing WiFi Clients sensor")

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

        _LOGGER.debug(f"WiFi Clients sensor updated: {self._state} devices")
        self.async_write_ha_state()


class LANClientsSensor(ZTERouterEntity):
    def __init__(self, coordinator, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = "LAN Clients"
        self._state = None
        self._attributes = {}
        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_should_poll = False
        _LOGGER.debug("Initializing LAN Clients sensor")

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
        _LOGGER.debug(f"LAN Clients sensor updated: {self._state} devices")
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
