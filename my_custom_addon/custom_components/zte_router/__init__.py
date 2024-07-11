import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
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
    ip_address = entry.data.get('router_ip')
    unique_id = f"{DOMAIN}_{ip_address}"
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, unique_id)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=ip_address,
        configuration_url=f"http://{ip_address}",
        sw_version=firmware_version,
    )

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
