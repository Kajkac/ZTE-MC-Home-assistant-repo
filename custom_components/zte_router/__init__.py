import json
import logging
import os

import voluptuous as vol
import yaml
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    CONF_ALLOW_STALE_DATA,
    DEFAULT_ALLOW_STALE_DATA,
    ROUTER_TYPE_MC801,
    ROUTER_TYPE_MC888,
    ROUTER_TYPE_MC889,
    ROUTER_TYPE_G5_ULTRA,
)
from .g5_ultra_client import G5UltraRouterRunner
from .router_backend import run_router_commands
from .sensor import ZTERouterDataUpdateCoordinator, ZTERouterSMSUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
SERVICE_UBUS_CALL = "ubus_call"
SERVICE_SEND_CUSTOM_SMS = "send_custom_sms"
SERVICE_REG_KEY = "__zte_router_service_registered"
SERVICE_UBUS_CALL_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("module"): cv.string,
        vol.Required("method"): cv.string,
        vol.Optional("params", default={}): dict,
    }
)
SERVICE_SEND_CUSTOM_SMS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Optional("phone"): cv.string,
        vol.Optional("phone_number"): cv.string,
        vol.Required("message"): cv.string,
    }
)
SERVICE_SET_NETWORK_MODE = "set_network_mode"
SERVICE_SET_NETWORK_MODE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("mode"): vol.In(["ONLY_3G", "ONLY_4G", "ONLY_5G", "4G_AND_5G"]),
    }
)
SERVICE_LOCK_CELL = "lock_cell"
SERVICE_LOCK_CELL_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("technology"): vol.In(["4g", "5g"]),
        vol.Required("pci"): cv.string,
        vol.Required("earfcn"): cv.string,
        vol.Optional("band"): cv.string,
    }
)
SERVICE_SET_BAND_LOCK = "set_band_lock"
SERVICE_SET_BAND_LOCK_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("technology"): vol.In(["4g", "5g"]),
        vol.Optional("band_mask"): cv.string,
        vol.Optional("nr_type"): vol.In(["nsa", "sa"]),
        vol.Optional("bands"): cv.string,
    }
)
SERVICE_RESET_BAND_CELL_LOCKS = "reset_band_cell_locks"
SERVICE_RESET_BAND_CELL_LOCKS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
    }
)
SERVICE_SEND_USSD = "send_ussd"
SERVICE_SEND_USSD_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("code"): cv.string,
    }
)
SERVICE_SET_FIREWALL = "set_firewall"
SERVICE_SET_FIREWALL_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("enable"): cv.boolean,
    }
)
SERVICE_SET_NAT = "set_nat"
SERVICE_SET_NAT_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("enable"): cv.boolean,
    }
)
SERVICE_SET_UPNP = "set_upnp"
SERVICE_SET_UPNP_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("enable"): cv.boolean,
    }
)
SERVICE_SET_DMZ = "set_dmz"
SERVICE_SET_DMZ_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("enable"): cv.boolean,
        vol.Optional("dmz_ip", default=""): cv.string,
    }
)
SERVICE_SET_WAN_DNS = "set_wan_dns"
SERVICE_SET_WAN_DNS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("mode"): vol.In(["auto", "manual"]),
        vol.Optional("prefer_dns", default=""): cv.string,
        vol.Optional("standby_dns", default=""): cv.string,
    }
)
SERVICE_SET_WAN_MTU = "set_wan_mtu"
SERVICE_SET_WAN_MTU_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("mtu"): vol.All(vol.Coerce(int), vol.Range(min=576, max=9000)),
    }
)
SERVICE_SET_DDNS = "set_ddns"
SERVICE_SET_DDNS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("enable"): cv.boolean,
        vol.Optional("service", default=""): cv.string,
        vol.Optional("domain", default=""): cv.string,
        vol.Optional("account", default=""): cv.string,
        vol.Optional("password", default=""): cv.string,
    }
)
SERVICE_SET_APN_MODE = "set_apn_mode"
SERVICE_SET_APN_MODE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("mode"): vol.In(["auto", "manual"]),
    }
)
SERVICE_ADD_APN_PROFILE = "add_apn_profile"
SERVICE_ADD_APN_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("profile_name"): cv.string,
        vol.Required("apn"): cv.string,
        vol.Optional("username", default=""): cv.string,
        vol.Optional("password", default=""): cv.string,
        vol.Optional("pdp_type", default="ipv4"): vol.In(["ipv4", "ipv6", "both"]),
        vol.Optional("auth_mode", default="none"): vol.In(["none", "pap", "chap"]),
    }
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up ZTE Router from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    _ensure_services_registered(hass)

    # Merge entry.data with entry.options. entry.options will override any values in entry.data.
    config = {**entry.data, **entry.options}

    #ping_interval = config.get("ping_interval", 60)
    #sms_check_interval = config.get("sms_check_interval", 100)
    ping_interval = entry.options.get("ping_interval", 60)
    sms_check_interval = entry.options.get("sms_check_interval", 100)
    router_type = config.get("router_type", ROUTER_TYPE_MC801)
    username = config.get("router_username") if router_type in [ROUTER_TYPE_MC888, ROUTER_TYPE_MC889] else None

    phone_number = config.get("phone_number", "13909")
    sms_message = config.get("sms_message", "BRZINA")
    create_automation_sms = config.get("create_automation_sms", True)
    create_automation_clean = config.get("create_automation_clean", False)
    create_automation_reboot = config.get("create_automation_reboot", False)

    # Initialize coordinators with username if applicable
    allow_stale_data = config.get(CONF_ALLOW_STALE_DATA, DEFAULT_ALLOW_STALE_DATA)
    coordinator = ZTERouterDataUpdateCoordinator(
        hass, config["router_ip"], config["router_password"], username, router_type, ping_interval, allow_stale_data
    )
    coordinator.config_entry = entry
    sms_coordinator = ZTERouterSMSUpdateCoordinator(
        hass, config["router_ip"], config["router_password"], username, router_type, sms_check_interval
    )

    await coordinator.async_config_entry_first_refresh()
    await sms_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "sms_coordinator": sms_coordinator,
        "phone_number": phone_number,
        "sms_message": sms_message,
        "create_automation_sms": create_automation_sms,
        "create_automation_clean": create_automation_clean,
        "create_automation_reboot": create_automation_reboot,
    }

    # Fetch initial data to get firmware version
    await coordinator.async_refresh()
    firmware_version = coordinator.data.get("wa_inner_version", "Unknown")

    # Forward entry setup to relevant platforms, including button
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch", "button", "device_tracker"])

    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Register the device in the device registry
    device_registry = async_get_device_registry(hass)
    entity_registry = async_get_entity_registry(hass)
    ip_address = config.get('router_ip')
    unique_id = f"{DOMAIN}_{ip_address}"
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, unique_id)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=ip_address,
        configuration_url=f"http://{ip_address}",
        sw_version=firmware_version,
    )

    # Find the entity_id for a specific sensor, e.g., "sensor.last_sms"
    sensor_entity_id = None
    for entity in entity_registry.entities.values():
        if entity.device_id == device.id and entity.platform == DOMAIN:
            if entity.original_name == "Last SMS":
                sensor_entity_id = entity.entity_id

    if not sensor_entity_id:
        _LOGGER.error("Could not find the necessary entities for automation.")
        return False

    # Define the automation configurations based on the user's selections
    automations_config = []
    if create_automation_sms:
        automations_config.append({
            "id": f"{DOMAIN}_automatic_sms_sender_{entry.entry_id}",
            "alias": f"Automatic SMS Sender {ip_address}",
            "trigger": [
                {"platform": "time_pattern", "minutes": "/5"}
            ],
            "condition": [
                {
                    "condition": "template",
                    "value_template": "{{ state_attr('sensor.last_sms', 'content') == 'Za nastavak surfanja po maksimalnoj dostupnoj brzini posaljite rijec BRZINA na broj 13909. Vas Hrvatski Telekom' }}"
                }
            ],
            "action": [
                {
                    "service": "button.press",
                    "target": {
                        "entity_id": "button.send_sms_50gb"
                    }
                }
            ],
            "mode": "single"
        })

    if create_automation_clean:
        automations_config.append({
            "id": f"{DOMAIN}_clean_sms_memory_{entry.entry_id}",
            "alias": f"Clean SMS Memory {ip_address}",
            "trigger": [
                {"platform": "state", "entity_id": "sensor.sms_capacity_left", "to": "5"}
            ],
            "condition": [
                {"condition": "state", "entity_id": "sensor.sms_capacity_left", "state": "5"}
            ],
            "action": [
                {
                    "service": "button.press",
                    "target": {"entity_id": "button.delete_all_sms"}
                }
            ],
            "mode": "single"
        })

    if create_automation_reboot:
        automations_config.append({
            "id": f"{DOMAIN}_zte_reboot_7hrs_{entry.entry_id}",
            "alias": f"ZTE Reboot {ip_address}",
            "trigger": [
                {"platform": "time", "at": "07:00:00"}
            ],
            "condition": [],
            "action": [
                {
                    "service": "button.press",
                    "target": {"entity_id": "button.reboot_router"}
                }
            ],
            "mode": "single"
        })

    def automation_exists(alias):
        automations_file = hass.config.path("automations.yaml")
        try:
            if os.path.exists(automations_file):
                with open(automations_file, 'r') as file:
                    automations = yaml.safe_load(file) or []
                for automation in automations:
                    if automation.get("alias") == alias:
                        return True
            return False
        except Exception as e:
            _LOGGER.error(f"Failed to read automation file: {e}")
            return False

    def write_automations():
        automations_file = hass.config.path("automations.yaml")
        try:
            if os.path.exists(automations_file):
                with open(automations_file, 'r') as file:
                    automations = yaml.safe_load(file) or []
            else:
                automations = []

            for automation_config in automations_config:
                alias = automation_config["alias"]
                existing_automation = next((a for a in automations if a.get("alias") == alias), None)
                if existing_automation:
                    initial_state = existing_automation.get("initial_state")
                    if initial_state is not None:
                        automation_config["initial_state"] = initial_state
                    else:
                        automation_config.pop("initial_state", None)
                else:
                    automation_config.pop("initial_state", None)

                automations = [a for a in automations if a.get("alias") != alias]
                automations.append(automation_config)

            with open(automations_file, 'w') as file:
                yaml.dump(automations, file, default_flow_style=False)

            return True

        except Exception as e:
            _LOGGER.error(f"Failed to write automations: {e}")
            return False

    automation_exists_results = []
    for alias in [automation["alias"] for automation in automations_config]:
        automation_exists_results.append(await hass.async_add_executor_job(automation_exists, alias))

    if not all(automation_exists_results):
        success = await hass.async_add_executor_job(write_automations)
        if success:
            await hass.services.async_call("automation", "reload")
            _LOGGER.info("Automations created successfully")
        else:
            return False
    else:
        _LOGGER.info("Automations already exist")

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "switch")
    await hass.config_entries.async_forward_entry_unload(entry, "button")
    await hass.config_entries.async_forward_entry_unload(entry, "device_tracker")
    hass.data[DOMAIN].pop(entry.entry_id)
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _resolve_config_entry(hass: HomeAssistant, entry_id: str | None) -> ConfigEntry:
    """Resolve the target config entry for a service call, defaulting to the only active one."""
    active_entries = [
        eid for eid in hass.data[DOMAIN]
        if isinstance(hass.data[DOMAIN].get(eid), dict)
    ]
    if not entry_id:
        if len(active_entries) == 1:
            entry_id = active_entries[0]
        else:
            raise HomeAssistantError(
                "Multiple ZTE Router entries found. Specify entry_id in the service call."
            )
    if entry_id not in hass.data[DOMAIN]:
        raise HomeAssistantError(f"Unknown ZTE Router entry_id: {entry_id}")

    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise HomeAssistantError(f"No config entry found for id {entry_id}")
    return entry


def _ensure_services_registered(hass: HomeAssistant) -> None:
    storage = hass.data.setdefault(DOMAIN, {})
    if storage.get(SERVICE_REG_KEY):
        return

    async def async_handle_ubus_call(call: ServiceCall):
        entry = _resolve_config_entry(hass, call.data.get("entry_id"))
        merged = {**entry.data, **entry.options}
        router_type = merged.get("router_type", ROUTER_TYPE_MC801)
        if router_type != ROUTER_TYPE_G5_ULTRA:
            raise HomeAssistantError("The ubus_call service is only available for G5 Ultra router entries.")

        module = call.data["module"]
        method = call.data["method"]
        params = call.data.get("params") or {}
        runner = G5UltraRouterRunner(merged["router_ip"], merged["router_password"])
        try:
            response = await hass.async_add_executor_job(
                runner.call_module_method,
                module,
                method,
                params,
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed executing ubus call {module}.{method}: {err}") from err

        hass.bus.async_fire(
            f"{DOMAIN}_ubus_response",
            {
                "entry_id": entry.entry_id,
                "module": module,
                "method": method,
                "params": params,
                "result": response.get("result"),
                "raw": response.get("raw"),
            },
        )

    async def async_handle_send_custom_sms(call: ServiceCall):
        entry = _resolve_config_entry(hass, call.data.get("entry_id"))
        merged = {**entry.data, **entry.options}
        router_type = merged.get("router_type", ROUTER_TYPE_MC801)
        username = merged.get("router_username") if router_type in [ROUTER_TYPE_MC888, ROUTER_TYPE_MC889] else None

        phone = (call.data.get("phone") or call.data.get("phone_number") or "").strip()
        if not phone:
            raise HomeAssistantError("send_custom_sms: provide 'phone' or 'phone_number'")
        message = call.data["message"].strip()
        if not message:
            raise HomeAssistantError("send_custom_sms: 'message' cannot be empty")

        try:
            raw = await hass.async_add_executor_job(
                run_router_commands,
                router_type,
                merged["router_ip"],
                merged["router_password"],
                username,
                "8",
                phone,
                message,
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to send SMS: {err}") from err

        try:
            parsed = json.loads(raw)
        except Exception as err:
            raise HomeAssistantError(f"Unexpected response from router: {raw}") from err

        result = parsed.get("8")
        if result is None:
            raise HomeAssistantError(f"No result returned for send SMS command: {parsed}")
        if isinstance(result, dict) and result.get("error"):
            raise HomeAssistantError(f"Failed to send SMS: {result['error']}")
        if isinstance(result, int) and not (200 <= result < 300):
            raise HomeAssistantError(f"Router returned HTTP status {result} while sending SMS")

        _LOGGER.info("send_custom_sms: sent SMS via entry %s", entry.entry_id)

    def _resolve_g5_ultra_runner(call: ServiceCall) -> G5UltraRouterRunner:
        entry = _resolve_config_entry(hass, call.data.get("entry_id"))
        merged = {**entry.data, **entry.options}
        if merged.get("router_type") != ROUTER_TYPE_G5_ULTRA:
            raise HomeAssistantError("This service is only available for G5 Ultra router entries.")
        return G5UltraRouterRunner(merged["router_ip"], merged["router_password"])

    async def async_handle_set_network_mode(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(runner.set_network_mode, call.data["mode"])
        except Exception as err:
            raise HomeAssistantError(f"Failed to set network mode: {err}") from err
        if isinstance(result, dict) and result.get("error"):
            raise HomeAssistantError(f"Failed to set network mode: {result['error']}")

    async def async_handle_lock_cell(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        technology = call.data["technology"]
        try:
            if technology == "4g":
                result = await hass.async_add_executor_job(
                    runner.lock_lte_cell, call.data["pci"], call.data["earfcn"]
                )
            else:
                band = call.data.get("band")
                if not band:
                    raise HomeAssistantError("lock_cell: 'band' is required for technology '5g'")
                result = await hass.async_add_executor_job(
                    runner.lock_nr_cell, call.data["pci"], call.data["earfcn"], band
                )
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(f"Failed to lock cell: {err}") from err
        if isinstance(result, dict) and result.get("error"):
            raise HomeAssistantError(f"Failed to lock cell: {result['error']}")

    async def async_handle_set_band_lock(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        technology = call.data["technology"]
        try:
            if technology == "4g":
                band_mask = call.data.get("band_mask")
                if not band_mask:
                    raise HomeAssistantError("set_band_lock: 'band_mask' is required for technology '4g'")
                result = await hass.async_add_executor_job(runner.set_lte_band_lock, band_mask)
            else:
                nr_type = call.data.get("nr_type")
                bands = call.data.get("bands")
                if not nr_type or not bands:
                    raise HomeAssistantError("set_band_lock: 'nr_type' and 'bands' are required for technology '5g'")
                result = await hass.async_add_executor_job(runner.set_nr_band_lock, nr_type, bands)
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(f"Failed to set band lock: {err}") from err
        if isinstance(result, dict) and result.get("error"):
            raise HomeAssistantError(f"Failed to set band lock: {result['error']}")

    async def async_handle_reset_band_cell_locks(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(runner.reset_band_cell_locks)
        except Exception as err:
            raise HomeAssistantError(f"Failed to reset band/cell locks: {err}") from err
        if isinstance(result, dict) and result.get("error"):
            raise HomeAssistantError(f"Failed to reset band/cell locks: {result['error']}")

    async def async_handle_send_ussd(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(runner.send_ussd, call.data["code"])
        except Exception as err:
            raise HomeAssistantError(f"Failed to send USSD code: {err}") from err
        if isinstance(result, dict) and result.get("error"):
            raise HomeAssistantError(f"Failed to send USSD code: {result['error']}")
        hass.bus.async_fire(f"{DOMAIN}_ussd_response", {"code": call.data["code"], "result": result})

    def _raise_if_error(result, action: str):
        if isinstance(result, dict) and result.get("error"):
            raise HomeAssistantError(f"Failed to {action}: {result['error']}")

    async def async_handle_set_firewall(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(runner.set_firewall, call.data["enable"])
        except Exception as err:
            raise HomeAssistantError(f"Failed to set firewall: {err}") from err
        _raise_if_error(result, "set firewall")

    async def async_handle_set_nat(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(runner.set_nat, call.data["enable"])
        except Exception as err:
            raise HomeAssistantError(f"Failed to set NAT: {err}") from err
        _raise_if_error(result, "set NAT")

    async def async_handle_set_upnp(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(runner.set_upnp, call.data["enable"])
        except Exception as err:
            raise HomeAssistantError(f"Failed to set UPnP: {err}") from err
        _raise_if_error(result, "set UPnP")

    async def async_handle_set_dmz(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(
                runner.set_dmz, call.data["enable"], call.data.get("dmz_ip", "")
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to set DMZ: {err}") from err
        _raise_if_error(result, "set DMZ")

    async def async_handle_set_wan_dns(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(
                runner.set_wan_dns,
                call.data["mode"],
                call.data.get("prefer_dns", ""),
                call.data.get("standby_dns", ""),
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to set WAN DNS: {err}") from err
        _raise_if_error(result, "set WAN DNS")

    async def async_handle_set_wan_mtu(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(runner.set_wan_mtu, call.data["mtu"])
        except Exception as err:
            raise HomeAssistantError(f"Failed to set WAN MTU: {err}") from err
        _raise_if_error(result, "set WAN MTU")

    async def async_handle_set_ddns(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        try:
            result = await hass.async_add_executor_job(
                runner.set_ddns,
                call.data["enable"],
                call.data.get("service", ""),
                call.data.get("domain", ""),
                call.data.get("account", ""),
                call.data.get("password", ""),
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to set DDNS: {err}") from err
        _raise_if_error(result, "set DDNS")

    async def async_handle_set_apn_mode(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        mode_code = "1" if call.data["mode"] == "manual" else "0"
        try:
            result = await hass.async_add_executor_job(runner.set_apn_mode, mode_code)
        except Exception as err:
            raise HomeAssistantError(f"Failed to set APN mode: {err}") from err
        _raise_if_error(result, "set APN mode")

    async def async_handle_add_apn_profile(call: ServiceCall):
        runner = _resolve_g5_ultra_runner(call)
        pdp_type_map = {"ipv4": 0, "ipv6": 1, "both": 2}
        auth_mode_map = {"none": 0, "pap": 1, "chap": 2}
        try:
            result = await hass.async_add_executor_job(
                runner.add_apn_profile,
                call.data["profile_name"],
                call.data["apn"],
                call.data.get("username", ""),
                call.data.get("password", ""),
                pdp_type_map[call.data.get("pdp_type", "ipv4")],
                auth_mode_map[call.data.get("auth_mode", "none")],
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to add APN profile: {err}") from err
        _raise_if_error(result, "add APN profile")

    hass.services.async_register(
        DOMAIN,
        SERVICE_UBUS_CALL,
        async_handle_ubus_call,
        schema=SERVICE_UBUS_CALL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_CUSTOM_SMS,
        async_handle_send_custom_sms,
        schema=SERVICE_SEND_CUSTOM_SMS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_NETWORK_MODE,
        async_handle_set_network_mode,
        schema=SERVICE_SET_NETWORK_MODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOCK_CELL,
        async_handle_lock_cell,
        schema=SERVICE_LOCK_CELL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BAND_LOCK,
        async_handle_set_band_lock,
        schema=SERVICE_SET_BAND_LOCK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_BAND_CELL_LOCKS,
        async_handle_reset_band_cell_locks,
        schema=SERVICE_RESET_BAND_CELL_LOCKS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_USSD,
        async_handle_send_ussd,
        schema=SERVICE_SEND_USSD_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FIREWALL,
        async_handle_set_firewall,
        schema=SERVICE_SET_FIREWALL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_NAT,
        async_handle_set_nat,
        schema=SERVICE_SET_NAT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_UPNP,
        async_handle_set_upnp,
        schema=SERVICE_SET_UPNP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DMZ,
        async_handle_set_dmz,
        schema=SERVICE_SET_DMZ_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_WAN_DNS,
        async_handle_set_wan_dns,
        schema=SERVICE_SET_WAN_DNS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_WAN_MTU,
        async_handle_set_wan_mtu,
        schema=SERVICE_SET_WAN_MTU_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DDNS,
        async_handle_set_ddns,
        schema=SERVICE_SET_DDNS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_APN_MODE,
        async_handle_set_apn_mode,
        schema=SERVICE_SET_APN_MODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_APN_PROFILE,
        async_handle_add_apn_profile,
        schema=SERVICE_ADD_APN_PROFILE_SCHEMA,
    )
    storage[SERVICE_REG_KEY] = True
