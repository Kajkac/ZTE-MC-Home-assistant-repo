import logging
import subprocess
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch platform."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    main_coordinator = coordinators["coordinator"]
    sms_coordinator = coordinators["sms_coordinator"]
    ip_entry = config_entry.data["router_ip"]
    password_entry = config_entry.data["router_password"]
    router_type = config_entry.data.get("router_type")

    async_add_entities([
        ZTERouterSwitch(main_coordinator, ip_entry, password_entry, router_type, "Reboot Router", "4"),
        ZTERouterSwitch(main_coordinator, ip_entry, password_entry, router_type, "Delete All SMS", "5"),
        ZTERouterSwitch(main_coordinator, ip_entry, password_entry, router_type, "Send SMS 50GB", "8"),
        ZTERouterSwitch(main_coordinator, ip_entry, password_entry, router_type, "Connect Data", "9"),
        ZTERouterSwitch(main_coordinator, ip_entry, password_entry, router_type, "Disconnect Data", "10")
    ], False)

class ZTERouterSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a switch to control the ZTE router."""

    def __init__(self, coordinator, ip_entry, password_entry, router_type, name, command):
        """Initialize the switch."""
        super().__init__(coordinator)
        self._ip = ip_entry
        self._password = password_entry
        self._router_type = router_type
        self._name = name
        self._state = False
        self._command = command

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
        return f"{DOMAIN}_{self._ip}_{self._name.replace(' ', '_').lower()}"

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
        """Turn the switch on (execute the command)."""
        await self.hass.async_add_executor_job(self._execute_command)
        self._state = False  # Switch should turn off immediately after the command
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off (does nothing)."""
        self._state = False
        self.async_write_ha_state()

    def _execute_command(self):
        """Run the mc.py script with the specified command."""
        try:
            result = subprocess.run(
                ["python3", "/config/custom_components/zte_router/mc.py", self._ip, self._password, self._command],
                capture_output=True,
                text=True,
                check=True
            )
            _LOGGER.info(f"{self._name} command output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            _LOGGER.error(f"Failed to execute {self._name} command: {e}")
