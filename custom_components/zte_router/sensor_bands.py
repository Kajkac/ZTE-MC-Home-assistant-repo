"""Carrier-aggregation band formatting helpers and the Connected Bands sensor."""

import logging
from datetime import datetime

from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, MANUFACTURER, MODEL, ROUTER_TYPE_G5_ULTRA
from .sensor_base import ZTERouterEntity, guard_stale_data

_LOGGER = logging.getLogger(__name__)


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
                # Format is pci,band,cellid,arfcn,bandwidth (confirmed against
                # live G5 Ultra data) -- band_info[0] is the PCI, not the band.
                # The old code read band_info[0] here, which showed the PCI
                # (e.g. "B281") repeated for every carrier instead of the
                # actual bands (B3/B1/B20).
                band_id = band_info[1]
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
            "band": first[1],
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
