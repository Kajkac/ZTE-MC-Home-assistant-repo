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
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional("router_ip", default=self.config_entry.data.get("router_ip")): str,
            vol.Optional("router_password", default=self.config_entry.data.get("router_password")): str,
            vol.Optional("router_username", default=self.config_entry.data.get("router_username", DEFAULT_USERNAME)): str,
            vol.Optional("ping_interval", default=self.config_entry.data.get("ping_interval", 100)): int,
            vol.Optional("sms_check_interval", default=self.config_entry.data.get("sms_check_interval", 200)): int,
            vol.Required("router_type", default=self.config_entry.data.get("router_type", "MC801A")): vol.In(["MC801A", "MC889", "MC888"]),
        })

        return self.async_show_form(step_id="init", data_schema=options_schema)
