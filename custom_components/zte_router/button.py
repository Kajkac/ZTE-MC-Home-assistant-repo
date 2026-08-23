import logging
import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, MANUFACTURER, MODEL, ROUTER_TYPE_G5_ULTRA, ROUTER_TYPE_MC801
from .log_util import describe_text, redact_phone
from .router_backend import run_router_commands

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the button platform."""
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

    # Retrieve phone numbers and messages from configuration options or data
    phone_number = config_entry.options.get("phone_number") or config_entry.data.get("phone_number", "13909")
    sms_message = config_entry.options.get("sms_message") or config_entry.data.get("sms_message", "BRZINA")
    phone_number_1 = config_entry.options.get("phone_number_1", "") or config_entry.data.get("phone_number_1", "")
    message_1 = config_entry.options.get("message_1", "") or config_entry.data.get("message_1", "")
    phone_number_2 = config_entry.options.get("phone_number_2", "") or config_entry.data.get("phone_number_2", "")
    message_2 = config_entry.options.get("message_2", "") or config_entry.data.get("message_2", "")

    button_definitions = [
        ("Send SMS 50GB", "8", phone_number, sms_message),
        ("Send SMS 1", "8", phone_number_1, message_1),
        ("Send SMS 2", "8", phone_number_2, message_2),
        ("Reboot Router", "4", None, None),
        ("Delete All SMS", "5", None, None),
        ("Connect Data", "9", None, None),
        ("Disconnect Data", "10", None, None),
        ("Set LTE", "11", None, None),
        ("Set 5G SA/NSA/LTE", "12", None, None),
        ("Set 5G NSA", "13", None, None),
        ("Set 5G SA", "14", None, None),
        ("Set Auto", "15", None, None),
    ]

    if router_type == ROUTER_TYPE_G5_ULTRA:
        unsupported = {"9", "10", "11", "12", "13", "14", "15"}
        button_definitions = [entry for entry in button_definitions if entry[1] not in unsupported]

    entities = [
        ZTERouterButton(
            main_coordinator,
            ip_entry,
            password_entry,
            username_entry,
            router_type,
            phone,
            msg,
            label,
            command,
        )
        for (label, command, phone, msg) in button_definitions
    ]

    async_add_entities(entities, False)

class ZTERouterButton(CoordinatorEntity, ButtonEntity):
    """Representation of a button to control the ZTE router."""

    def __init__(
        self,
        coordinator,
        ip_entry,
        password_entry,
        username_entry,
        router_type,
        phone_number,
        sms_message,
        name,
        command,
    ):
        """Initialize the button."""
        super().__init__(coordinator)
        self._ip = ip_entry
        self._password = password_entry
        self._username = username_entry if username_entry else ""  # Ensure username is always a string
        self._router_type = router_type
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
            _LOGGER.info(f"Sending SMS to {redact_phone(self._phone_number)} with message: {describe_text(self._sms_message)}")

        await self.hass.async_add_executor_job(self._execute_command)

        await asyncio.sleep(3)

        await self.coordinator.async_request_refresh()

    def _execute_command(self):
        """Run the mc.py script with the specified command, including username handling."""
        try:
            result = run_router_commands(
                self._router_type,
                self._ip,
                self._password,
                self._username,
                self._command,
                phone_number=self._phone_number,
                message=self._sms_message,
            )
            _LOGGER.info("%s command output: %s", self._name, result)
        except Exception as err:
            _LOGGER.error("Failed to execute %s command: %s", self._name, err)
