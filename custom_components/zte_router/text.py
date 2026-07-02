"""Text platform for ZTE router integration (G5 Ultra cell lock inputs)."""

import logging

from homeassistant.components.text import TextEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, ROUTER_TYPE_G5_ULTRA, ROUTER_TYPE_MC801

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the text platform. G5 Ultra only."""
    router_type = config_entry.data.get("router_type", ROUTER_TYPE_MC801)
    if router_type != ROUTER_TYPE_G5_ULTRA:
        return

    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    main_coordinator = coordinators["coordinator"]
    ip_entry = config_entry.data["router_ip"]

    async_add_entities(
        [
            CellLockTextEntity(main_coordinator, ip_entry, config_entry.entry_id, "4g"),
            CellLockTextEntity(main_coordinator, ip_entry, config_entry.entry_id, "5g"),
        ],
        False,
    )


class CellLockTextEntity(CoordinatorEntity, TextEntity):
    """Input for a 4G/5G cell lock target.

    Type a value here ("pci,earfcn" for 4G, "pci,earfcn,band" for 5G), then
    turn on the matching "Cell Lock 4G"/"Cell Lock 5G" switch (switch.py) to
    apply it. While a lock is active, this reflects the currently-applied
    value; otherwise it shows whatever was last typed (pending).
    """

    def __init__(self, coordinator, ip_entry, entry_id, technology: str):
        super().__init__(coordinator)
        self._ip = ip_entry
        self._entry_id = entry_id
        self._technology = technology  # "4g" or "5g"

    @property
    def name(self):
        return f"Cell Lock {self._technology.upper()} Input"

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self._ip}_g5ultra_cell_lock_{self._technology}_text"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        key = "lock_lte_cell" if self._technology == "4g" else "lock_nr_cell"
        active = str(data.get(key) or "").strip()
        if active:
            return active
        return (
            self.hass.data.get(DOMAIN, {})
            .get(self._entry_id, {})
            .get(f"cell_lock_{self._technology}_text", "")
        )

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self._ip}")},
            "name": self._ip,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": (self.coordinator.data or {}).get("wa_inner_version", "Unknown"),
        }

    async def async_set_value(self, value: str) -> None:
        value = (value or "").strip()
        expected_parts = 2 if self._technology == "4g" else 3
        parts = [p for p in value.split(",") if p.strip()]
        if value and len(parts) != expected_parts:
            fmt = "pci,earfcn" if self._technology == "4g" else "pci,earfcn,band"
            raise ValueError(f"Expected format '{fmt}', got: {value!r}")

        self.hass.data.setdefault(DOMAIN, {}).setdefault(self._entry_id, {})[
            f"cell_lock_{self._technology}_text"
        ] = value
        self.async_write_ha_state()
