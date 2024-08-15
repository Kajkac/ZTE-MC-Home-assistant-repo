from homeassistant import config_entries
from homeassistant.core import callback  # Make sure this import is here
import voluptuous as vol
from .const import DOMAIN, DEFAULT_USERNAME

class ZTERouterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZTE Router."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._config_entry = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=user_input["router_type"], data=user_input)

        data_schema = vol.Schema({
            vol.Required("router_ip"): str,
            vol.Required("router_password"): str,
            vol.Optional("router_username", default=DEFAULT_USERNAME): str,
            vol.Optional("ping_interval", default=100): int,
            vol.Optional("sms_check_interval", default=200): int,
            vol.Required("router_type", default="MC801A"): vol.In(["MC801A", "MC889", "MC888"]),
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod  # Update this to a static method
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return ZTERouterOptionsFlowHandler(config_entry)

class ZTERouterOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for ZTE Router."""

    def __init__(self, config_entry):
        """Initialize ZTE Router options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options for the custom integration."""
        if user_input is not None:
            # Save the options entered by the user
            return self.async_create_entry(title="", data=user_input)

        # Use existing config_entry data to populate the form
        current_data = {
            "router_ip": self.config_entry.data.get("router_ip"),
            "router_password": self.config_entry.data.get("router_password"),
            "router_username": self.config_entry.options.get("router_username", self.config_entry.data.get("router_username", DEFAULT_USERNAME)),
            "ping_interval": self.config_entry.options.get("ping_interval", self.config_entry.data.get("ping_interval", 100)),
            "sms_check_interval": self.config_entry.options.get("sms_check_interval", self.config_entry.data.get("sms_check_interval", 200)),
            "router_type": self.config_entry.options.get("router_type", self.config_entry.data.get("router_type", "MC801A")),
        }

        options_schema = vol.Schema({
            vol.Optional("router_ip", default=current_data["router_ip"]): str,
            vol.Optional("router_password", default=current_data["router_password"]): str,
            vol.Optional("router_username", default=current_data["router_username"]): str,
            vol.Optional("ping_interval", default=current_data["ping_interval"]): int,
            vol.Optional("sms_check_interval", default=current_data["sms_check_interval"]): int,
            vol.Required("router_type", default=current_data["router_type"]): vol.In(["MC801A", "MC889", "MC888"]),
        })

        return self.async_show_form(step_id="init", data_schema=options_schema)
