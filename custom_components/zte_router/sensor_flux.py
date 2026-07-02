"""FLUX data-usage statistics sensors."""

import logging

from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, SENSOR_NAMES, UNITS, FLUX_KEYS, FLUX_ICON_MAP
from .sensor_base import ZTERouterEntity, guard_stale_data

_LOGGER = logging.getLogger(__name__)

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
