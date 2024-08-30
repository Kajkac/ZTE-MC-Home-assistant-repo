import logging
import subprocess
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the button platform."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    main_coordinator = coordinators["coordinator"]
    ip_entry = config_entry.data["router_ip"]
    password_entry = config_entry.data["router_password"]
    router_type = config_entry.data.get("router_type")
    username_entry = config_entry.data.get("router_username", None) if router_type in ["MC888A", "MC889A"] else None

    async_add_entities([
        ZTERouterButton(main_coordinator, ip_entry, password_entry, username_entry, router_type, "Reboot Router", "4"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, username_entry, router_type, "Delete All SMS", "5"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, username_entry, router_type, "Send SMS 50GB", "8"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, username_entry, router_type, "Connect Data", "9"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, username_entry, router_type, "Disconnect Data", "10"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, username_entry, router_type, "Set 5G SA", "11"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, username_entry, router_type, "Set 5G NSA", "12")
    ], False)

class ZTERouterButton(CoordinatorEntity, ButtonEntity):
    """Representation of a button to control the ZTE router."""

    def __init__(self, coordinator, ip_entry, password_entry, username_entry, router_type, name, command):
        """Initialize the button."""
        super().__init__(coordinator)
        self._ip = ip_entry
        self._password = password_entry
        self._username = username_entry if router_type in ["MC888A", "MC889A"] else ""
        self._router_type = router_type
        self._name = name
        self._command = command

    @property
    def name(self):
        """Return the name of the button."""
        return self._name

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self._ip}_{self._name.replace(' ', '_').lower()}"

    @property
    def device_info(self):
        """Return the device info for the button."""
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self._ip}")},
            "name": self._ip,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown"),
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.hass.async_add_executor_job(self._execute_command)

    def _execute_command(self):
        """Run the mc.py script with the specified command."""
        try:
            cmd = [
                "python3",
                "/config/custom_components/zte_router/mc.py",
                self._ip,
                self._password,
                self._command,
                self._username  # Include username if applicable
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            _LOGGER.info(f"{self._name} command output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            _LOGGER.error(f"Failed to execute {self._name} command: {e}")
