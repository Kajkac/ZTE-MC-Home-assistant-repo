import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    DOMAIN,
    DEFAULT_USERNAME,
    CONF_ALLOW_STALE_DATA,
    DEFAULT_ALLOW_STALE_DATA,
    SUPPORTED_ROUTER_TYPES,
    ROUTER_TYPE_MC801,
)

_LOGGER = logging.getLogger(__name__)


class ZTERouterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZTE Router."""

    VERSION = 1

    def __init__(self):
        self.selected_router_type = None
        self.has_username = False

    async def async_step_user(self, user_input=None):
        """Handle the initial step to select the router model and options."""
        errors = {}

        if user_input is not None:
            _LOGGER.debug("Config step user raw input=%r", user_input)
            selected_router_type = user_input.get("router_type")
            if not selected_router_type:
                errors["router_type"] = "required"
            elif selected_router_type not in SUPPORTED_ROUTER_TYPES:
                errors["router_type"] = "invalid_option"
            else:
                self.selected_router_type = selected_router_type
                self.has_username = user_input.get("has_username", False)
                self.context["router_type"] = self.selected_router_type
                self.context["has_username"] = self.has_username
                _LOGGER.debug(
                    "Config step user selected router_type=%r has_username=%r",
                    self.selected_router_type,
                    self.has_username,
                )
                return await self.async_step_config()

        model_schema = vol.Schema(
            {
                vol.Required("router_type"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=SUPPORTED_ROUTER_TYPES,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("has_username", default=False): bool,
            }
        )

        return self.async_show_form(step_id="user", data_schema=model_schema, errors=errors)

    async def async_step_config(self, user_input=None):
        """Handle the configuration step based on the router model."""
        errors = {}
        selected_router_type = self.selected_router_type or self.context.get("router_type") or ROUTER_TYPE_MC801
        selected_has_username = bool(self.has_username or self.context.get("has_username", False))

        if user_input is not None:
            router_ip = str(user_input.get("router_ip", "")).strip()
            router_password = str(user_input.get("router_password", "")).strip()

            if not router_ip:
                errors["router_ip"] = "required"
            if not router_password:
                errors["router_password"] = "required"

            if not errors:
                user_input["router_ip"] = router_ip
                user_input["router_password"] = router_password
                user_input.setdefault("phone_number", "13909")
                user_input.setdefault("sms_message", "BRZINA")
                user_input.setdefault("phone_number_1", "")
                user_input.setdefault("message_1", "")
                user_input.setdefault("phone_number_2", "")
                user_input.setdefault("message_2", "")
                user_input.setdefault("create_automation_sms", True)
                user_input.setdefault("create_automation_clean", False)
                user_input.setdefault("create_automation_reboot", False)
                user_input.setdefault("enable_flux_sensors", False)
                user_input.setdefault("allow_stale_data", DEFAULT_ALLOW_STALE_DATA)
                user_input["router_type"] = selected_router_type
                user_input["has_username"] = selected_has_username
                _LOGGER.debug(
                    "Creating entry router_type=%r router_ip=%r has_username=%r",
                    selected_router_type,
                    router_ip,
                    selected_has_username,
                )
                return self.async_create_entry(title=router_ip, data=user_input)

        base_schema = {
            vol.Optional("router_ip", default=(user_input or {}).get("router_ip", "")): str,
            vol.Optional("router_password", default=(user_input or {}).get("router_password", "")): str,
            vol.Optional("phone_number", default="13909"): str,
            vol.Optional("sms_message", default="BRZINA"): str,
            vol.Optional("phone_number_1", default=""): str,
            vol.Optional("message_1", default=""): str,
            vol.Optional("phone_number_2", default=""): str,
            vol.Optional("message_2", default=""): str,
            vol.Optional("create_automation_sms", default=True): bool,
            vol.Optional("create_automation_clean", default=False): bool,
            vol.Optional("create_automation_reboot", default=False): bool,
            vol.Optional("enable_flux_sensors", default=False): bool,
            vol.Optional("allow_stale_data", default=DEFAULT_ALLOW_STALE_DATA): bool,
        }

        if selected_has_username:
            base_schema[vol.Optional("router_username", default=DEFAULT_USERNAME)] = str

        return self.async_show_form(step_id="config", data_schema=vol.Schema(base_schema), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ZTERouterOptionsFlowHandler(config_entry)


class ZTERouterOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the options flow for ZTE Router."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize with the config entry without using deprecated assignment."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options for the custom integration."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self._config_entry.data
        options = self._config_entry.options

        current_data = {
            "router_ip": data.get("router_ip"),
            "router_password": data.get("router_password"),
            "router_username": options.get("router_username", data.get("router_username", DEFAULT_USERNAME)),
            "ping_interval": options.get("ping_interval", data.get("ping_interval", 100)),
            "sms_check_interval": options.get("sms_check_interval", data.get("sms_check_interval", 200)),
            "monthly_usage_threshold": options.get("monthly_usage_threshold", data.get("monthly_usage_threshold", 200)),
            "phone_number": options.get("phone_number", data.get("phone_number", "13909")),
            "sms_message": options.get("sms_message", data.get("sms_message", "BRZINA")),
            "phone_number_1": options.get("phone_number_1", data.get("phone_number_1", "")),
            "message_1": options.get("message_1", data.get("message_1", "")),
            "phone_number_2": options.get("phone_number_2", data.get("phone_number_2", "")),
            "message_2": options.get("message_2", data.get("message_2", "")),
            "create_automation_sms": options.get("create_automation_sms", data.get("create_automation_sms", True)),
            "create_automation_clean": options.get("create_automation_clean", data.get("create_automation_clean", False)),
            "create_automation_reboot": options.get("create_automation_reboot", data.get("create_automation_reboot", False)),
            "enable_flux_sensors": options.get("enable_flux_sensors", data.get("enable_flux_sensors", True)),
            "allow_stale_data": options.get("allow_stale_data", data.get("allow_stale_data", DEFAULT_ALLOW_STALE_DATA)),
        }

        options_schema = {
            vol.Optional("router_ip", default=current_data["router_ip"]): str,
            vol.Optional("router_password", default=current_data["router_password"]): str,
            vol.Optional("ping_interval", default=current_data["ping_interval"]): int,
            vol.Optional("sms_check_interval", default=current_data["sms_check_interval"]): int,
            vol.Required("monthly_usage_threshold", default=current_data["monthly_usage_threshold"]): int,
            vol.Optional("phone_number", default=current_data["phone_number"]): str,
            vol.Optional("sms_message", default=current_data["sms_message"]): str,
            vol.Optional("phone_number_1", default=current_data["phone_number_1"]): str,
            vol.Optional("message_1", default=current_data["message_1"]): str,
            vol.Optional("phone_number_2", default=current_data["phone_number_2"]): str,
            vol.Optional("message_2", default=current_data["message_2"]): str,
            vol.Optional("create_automation_sms", default=current_data["create_automation_sms"]): bool,
            vol.Optional("create_automation_clean", default=current_data["create_automation_clean"]): bool,
            vol.Optional("create_automation_reboot", default=current_data["create_automation_reboot"]): bool,
            vol.Optional("enable_flux_sensors", default=current_data["enable_flux_sensors"]): bool,
            vol.Optional("allow_stale_data", default=current_data["allow_stale_data"]): bool,
        }

        if data.get("has_username", False):
            options_schema[vol.Optional("router_username", default=current_data["router_username"])] = str

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options_schema))
