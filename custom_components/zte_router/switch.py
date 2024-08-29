import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the dummy switch platform."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    main_coordinator = coordinators["coordinator"]
    ip_entry = config_entry.data["router_ip"]

    # Comment out or remove the dummy switch creation for now
    # async_add_entities([
    #     DummySwitch(main_coordinator, ip_entry, "Dummy Switch")
    # ], False)

class DummySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a dummy switch."""

    def __init__(self, coordinator, ip_entry, name):
        """Initialize the switch."""
        super().__init__(coordinator)
        self._ip = ip_entry
        self._name = name
        self._state = False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the switch."""
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self._ip}_dummy_switch"

    @property
    def device_info(self):
        """Return the device info for the switch."""
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self._ip}")},
            "name": self._ip,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown"),
        }

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = False
        self.async_write_ha_state()
