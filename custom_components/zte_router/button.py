import logging
import asyncio
import subprocess
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the button platform."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    main_coordinator = coordinators["coordinator"]
    ip_entry = config_entry.data["router_ip"]
    password_entry = config_entry.data["router_password"]

    # Retrieve phone numbers and messages from configuration options or data
    phone_number = config_entry.options.get("phone_number") or config_entry.data.get("phone_number", "13909")
    sms_message = config_entry.options.get("sms_message") or config_entry.data.get("sms_message", "BRZINA")
    phone_number_1 = config_entry.options.get("phone_number_1", "") or config_entry.data.get("phone_number_1", "")
    message_1 = config_entry.options.get("message_1", "") or config_entry.data.get("message_1", "")
    phone_number_2 = config_entry.options.get("phone_number_2", "") or config_entry.data.get("phone_number_2", "")
    message_2 = config_entry.options.get("message_2", "") or config_entry.data.get("message_2", "")

    async_add_entities([
        ZTERouterButton(main_coordinator, ip_entry, password_entry, phone_number, sms_message, "Send SMS 50GB", "8"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, phone_number_1, message_1, "Send SMS 1", "8"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, phone_number_2, message_2, "Send SMS 2", "8"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, None, None, "Reboot Router", "4"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, None, None, "Delete All SMS", "5"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, None, None, "Connect Data", "9"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, None, None, "Disconnect Data", "10"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, None, None, "Set 5G SA", "11"),
        ZTERouterButton(main_coordinator, ip_entry, password_entry, None, None, "Set 5G NSA", "12")
    ], False)

class ZTERouterButton(CoordinatorEntity, ButtonEntity):
    """Representation of a button to control the ZTE router."""

    def __init__(self, coordinator, ip_entry, password_entry, phone_number, sms_message, name, command):
        """Initialize the button."""
        super().__init__(coordinator)
        self._ip = ip_entry
        self._password = password_entry
        self._phone_number = phone_number
        self._sms_message = sms_message
        self._name = name
        self._command = command

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self._ip}_{self._name.replace(' ', '_').lower()}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self._ip}")},
            "name": self._ip,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown"),
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info(f"Button '{self._name}' was pressed.")
        if self._command == "8":
            if not self._phone_number or not self._sms_message:
                _LOGGER.error(f"Phone number or message not set for {self._name}")
                return
            _LOGGER.info(f"Sending SMS to {self._phone_number} with message: {self._sms_message}")

        await self.hass.async_add_executor_job(self._execute_command)

        await asyncio.sleep(3)

        await self.coordinator.async_request_refresh()

    def _execute_command(self):
        """Run the mc.py script with the specified command."""
        try:
            cmd = [
                "python3",
                "/config/custom_components/zte_router/mc.py",
                self._ip,
                self._password,
                self._command,
                self._phone_number or "",
                self._sms_message or ""
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            _LOGGER.info(f"{self._name} command output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            _LOGGER.error(f"Failed to execute {self._name} command: {e}")
