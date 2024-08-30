from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from .const import DOMAIN, DEFAULT_USERNAME

class ZTERouterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZTE Router."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.selected_router_type = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step to select the router model."""
        errors = {}

        if user_input is not None:
            self.selected_router_type = user_input.get("router_type")
            return await self.async_step_config()

        # Schema for selecting the router type
        model_schema = vol.Schema({
            vol.Required("router_type", default="MC801A"): vol.In(["MC801A", "MC889", "MC888", "MC888A", "MC889A"]),
        })

        return self.async_show_form(
            step_id="user", data_schema=model_schema, errors=errors
        )

    async def async_step_config(self, user_input=None):
        """Handle the configuration step based on the router model."""
        errors = {}

        if user_input is not None:
            # Add router_type to the user_input data
            user_input["router_type"] = self.selected_router_type

            # Proceed with creating the entry after validation
            return self.async_create_entry(title=user_input["router_ip"], data=user_input)

        # Base schema for all models
        base_schema = {
            vol.Required("router_ip"): str,
            vol.Required("router_password"): str,
            vol.Optional("ping_interval", default=100): int,
            vol.Optional("sms_check_interval", default=200): int,
            vol.Required("monthly_usage_threshold", default=200): int,
        }

        # Add the router_username field only if model is MC888A or MC889A
        if self.selected_router_type in ["MC888A", "MC889A"]:
            base_schema[vol.Optional("router_username", default=DEFAULT_USERNAME)] = str

        # Final schema with dynamic fields
        data_schema = vol.Schema(base_schema)

        return self.async_show_form(
            step_id="config", data_schema=data_schema, errors=errors
        )

    @staticmethod
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
            "monthly_usage_threshold": self.config_entry.options.get("monthly_usage_threshold", 200),
        }

        # Base options schema without router_type
        options_schema = {
            vol.Optional("router_ip", default=current_data["router_ip"]): str,
            vol.Optional("router_password", default=current_data["router_password"]): str,
            vol.Optional("ping_interval", default=current_data["ping_interval"]): int,
            vol.Optional("sms_check_interval", default=current_data["sms_check_interval"]): int,
            vol.Required("monthly_usage_threshold", default=current_data["monthly_usage_threshold"]): int,
        }

        # Conditionally add the router_username field for specific models
        if self.config_entry.data.get("router_type") in ["MC888A", "MC889A"]:
            options_schema[vol.Optional("router_username", default=current_data["router_username"])] = str

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options_schema))
