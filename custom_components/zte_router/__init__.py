import logging
import yaml
import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.components.http import HomeAssistantView
from .const import DOMAIN, MANUFACTURER, MODEL
from .sensor import ZTERouterDataUpdateCoordinator, ZTERouterSMSUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class IconView(HomeAssistantView):
    url = "/api/zte_router/icon"
    name = "api:zte_router:icon"

    async def get(self, request):
        return self.file_response("/config/custom_components/zte_router/static/router_icon.png")

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the ZTE Router component."""
    hass.http.register_view(IconView)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up ZTE Router from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    ping_interval = entry.data.get("ping_interval", 60)
    sms_check_interval = entry.data.get("sms_check_interval", 100)

    coordinator = ZTERouterDataUpdateCoordinator(hass, entry.data["router_ip"], entry.data["router_password"], ping_interval)
    sms_coordinator = ZTERouterSMSUpdateCoordinator(hass, entry.data["router_ip"], entry.data["router_password"], sms_check_interval)

    await coordinator.async_config_entry_first_refresh()
    await sms_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "sms_coordinator": sms_coordinator,
    }

    # Fetch initial data to get firmware version
    await coordinator.async_refresh()
    firmware_version = coordinator.data.get("wa_inner_version", "Unknown")

    # Forward entry setup to relevant platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch"])

    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Register the icon view
    hass.http.register_view(IconView)

    # Register the device in the device registry
    device_registry = async_get_device_registry(hass)
    entity_registry = async_get_entity_registry(hass)
    ip_address = entry.data.get('router_ip')
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
    switch_entity_id = "switch.send_sms_50gb"

    for entity in entity_registry.entities.values():
        if entity.device_id == device.id and entity.platform == DOMAIN:
            if entity.original_name == "Last SMS":
                sensor_entity_id = entity.entity_id

    if not sensor_entity_id:
        _LOGGER.error("Could not find the necessary entities for automation.")
        return False

    # Define the automation configuration with dynamic device_id and entity_id
    automation_config = {
        "id": f"{DOMAIN}_automatic_sms_sender_{entry.entry_id}",
        "alias": "Automatic SMS Sender T-Mobile HR",
        "trigger": [
            {
                "platform": "state",
                "entity_id": sensor_entity_id,
                "to": "Za nastavak surfanja po maksimalnoj dostupnoj brzini posaljite rijec BRZINA na broj 13909. Vas Hrvatski Telekom"
            }
        ],
        "condition": [
            {
                "condition": "state",
                "entity_id": sensor_entity_id,
                "state": "Za nastavak surfanja po maksimalnoj dostupnoj brzini posaljite rijec BRZINA na broj 13909. Vas Hrvatski Telekom"
            }
        ],
        "action": [
            {
                "service": "switch.turn_on",
                "target": {
                    "entity_id": switch_entity_id
                }
            }
        ],
        "mode": "single"
    }

    def automation_exists():
        automations_file = hass.config.path("automations.yaml")
        try:
            if os.path.exists(automations_file):
                with open(automations_file, 'r') as file:
                    automations = yaml.safe_load(file) or []
                for automation in automations:
                    if automation.get("alias") == "Automatic SMS Sender T-Mobile HR":
                        return True
            return False
        except Exception as e:
            _LOGGER.error(f"Failed to read automation file: {e}")
            return False

    def write_automation():
        automations_file = hass.config.path("automations.yaml")
        try:
            if os.path.exists(automations_file):
                with open(automations_file, 'r') as file:
                    automations = yaml.safe_load(file) or []
            else:
                automations = []

            # Remove any existing automation with the same ID
            automations = [a for a in automations if a.get("id") != automation_config["id"]]

            automations.append(automation_config)

            with open(automations_file, 'w') as file:
                yaml.dump(automations, file, default_flow_style=False)

            return True

        except Exception as e:
            _LOGGER.error(f"Failed to write automation: {e}")
            return False

    if not await hass.async_add_executor_job(automation_exists):
        success = await hass.async_add_executor_job(write_automation)
        if success:
            # Reload automations
            await hass.services.async_call("automation", "reload")
            _LOGGER.info("Automation 'Automatic SMS Sender T-Mobile HR' created successfully")
        else:
            return False
    else:
        _LOGGER.info("Automation 'Automatic SMS Sender T-Mobile HR' already exists")

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "switch")
    hass.data[DOMAIN].pop(entry.entry_id)
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
