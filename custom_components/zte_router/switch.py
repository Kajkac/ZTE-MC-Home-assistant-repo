import asyncio
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, MANUFACTURER, MODEL, ROUTER_TYPE_G5_ULTRA, ROUTER_TYPE_MC801
from .router_backend import run_router_commands

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch platform."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    main_coordinator = coordinators["coordinator"]
    ip_entry = config_entry.data["router_ip"]
    password_entry = config_entry.data["router_password"]
    router_type = config_entry.data.get("router_type", ROUTER_TYPE_MC801)

    # Handle username (only required for certain router models)
    username_entry = (
        config_entry.data.get("router_username")
        if config_entry.data.get("router_type") in ["MC888A", "MC889A"]
        else None
    )

    # WiFi switch is only supported on MC-series routers.
    # G5 Ultra uses a different (ubus) API; its WiFi toggle is not yet implemented.
    if router_type != ROUTER_TYPE_G5_ULTRA:
        async_add_entities([
            WiFiSwitch(main_coordinator, ip_entry, password_entry, username_entry, router_type)
        ], False)


class WiFiSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity to enable or disable the router's WiFi radios.

    Confirmed working on: ZTE MC888 Ultra (firmware CR_VDFEUMC888ULTRAV1.0.0B10).
    Expected to work on all MC-series routers (MC801, MC888, MC889) that share
    the same goform HTTP API.

    State is read from the 'wifi_onoff_state' field returned by the coordinator.
    The toggle uses goformId=switchWiFiModule with SwitchOption=1 (on) / 0 (off),
    discovered by intercepting network requests from the router's own web UI.
    """

    def __init__(self, coordinator, ip_entry, password_entry, username_entry, router_type):
        """Initialize the WiFi switch."""
        super().__init__(coordinator)
        self._ip = ip_entry
        self._password = password_entry
        self._username = username_entry if username_entry else ""
        self._router_type = router_type

    @property
    def name(self):
        """Return the name of the switch."""
        return "Router WiFi"

    @property
    def unique_id(self):
        """Return a unique ID for this switch."""
        return f"{DOMAIN}_{self._ip}_wifi_switch"

    @property
    def icon(self):
        """Return an icon reflecting the current WiFi state."""
        return "mdi:wifi" if self.is_on else "mdi:wifi-off"

    @property
    def is_on(self):
        """Return True if WiFi is currently enabled."""
        data = self.coordinator.data or {}
        return data.get("wifi_onoff_state", "0") == "1"

    @property
    def device_info(self):
        """Return device info to group this switch with the router device."""
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self._ip}")},
            "name": self._ip,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown"),
        }

    async def async_turn_on(self, **kwargs):
        """Enable WiFi radios."""
        await self.hass.async_add_executor_job(self._execute_command, "17")
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Disable WiFi radios."""
        await self.hass.async_add_executor_job(self._execute_command, "18")
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()

    def _execute_command(self, command: str):
        """Run a WiFi toggle command via the router backend."""
        try:
            result = run_router_commands(
                self._router_type,
                self._ip,
                self._password,
                self._username,
                command,
            )
            _LOGGER.info("WiFi toggle command %s output: %s", command, result)
        except Exception as err:
            _LOGGER.error("WiFi toggle command %s failed: %s", command, err)
