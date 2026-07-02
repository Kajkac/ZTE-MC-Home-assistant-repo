"""Device tracker platform for ZTE Router.

Each device (WiFi or wired) seen by the router gets a tracked entity.
State is 'home' when the device is in the current poll's client list,
'not_home' when absent.
"""
import logging

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZTE Router device trackers from a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    coordinator = coordinators["coordinator"]

    # Track which MAC addresses already have an entity so we don't duplicate.
    tracked_macs: set[str] = set()

    @callback
    def _async_discover_devices() -> None:
        """Create tracker entities for any newly seen devices."""
        new_entities = []
        for device in _all_devices(coordinator.data):
            mac = _device_mac(device)
            if not mac or mac in tracked_macs:
                continue
            tracked_macs.add(mac)
            new_entities.append(ZTEDeviceTracker(coordinator, mac, device))
        if new_entities:
            async_add_entities(new_entities)

    # Initial discovery on setup.
    _async_discover_devices()

    # Re-run discovery on every coordinator update to pick up new devices.
    entry.async_on_unload(coordinator.async_add_listener(_async_discover_devices))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_mac(mac: str) -> str:
    """Return a lower-case, colon-separated MAC address, or '' if invalid."""
    mac = mac.strip().lower().replace("-", ":").replace(".", ":")
    if len(mac.split(":")) == 6:
        return mac
    return ""


def _extract_first(dev: dict, keys: tuple[str, ...], default: str = "") -> str:
    """Return the first non-empty string value from candidate keys."""
    for key in keys:
        value = dev.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _device_mac(dev: dict) -> str:
    """Extract MAC from known variants in router payloads."""
    return _normalize_mac(
        _extract_first(dev, ("mac_addr", "mac", "mac_address", "macAddress"))
    )


def _device_hostname(dev: dict) -> str:
    """Extract hostname from known variants in router payloads."""
    return _extract_first(dev, ("hostname", "host_name", "name", "device_name"))


def _device_ip(dev: dict) -> str:
    """Extract IPv4 from known variants in router payloads."""
    return _extract_first(dev, ("ip_addr", "ip", "ip_address", "ipv4", "addr"))


def _device_connection_type(dev: dict) -> str:
    """Extract connection type from known variants in router payloads."""
    return _extract_first(dev, ("type", "access_type", "connect_type", "medium"))


def _all_devices(data: dict) -> list[dict]:
    """Merge known client lists and de-duplicate by MAC."""
    if not data:
        return []
    seen: set[str] = set()
    devices: list[dict] = []
    for key in ("all_devices", "station_list", "lan_station_list"):
        for dev in data.get(key) or []:
            mac = _device_mac(dev)
            if mac and mac not in seen:
                seen.add(mac)
                devices.append(dev)
    return devices


def _find_device(data: dict, mac: str) -> dict | None:
    """Return the raw device dict for *mac* from current coordinator data."""
    for dev in _all_devices(data):
        if _device_mac(dev) == mac:
            return dev
    return None


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

class ZTEDeviceTracker(CoordinatorEntity, ScannerEntity):
    """A single network device tracked via the ZTE Router."""

    def __init__(self, coordinator, mac: str, initial_data: dict) -> None:
        super().__init__(coordinator)
        self._mac = mac
        # Use hostname as display name; fall back to MAC if blank.
        self._initial_hostname = _device_hostname(initial_data) or mac
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.ip_entry}_tracker_{mac.replace(':', '')}"
        )

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        return _find_device(self.coordinator.data, self._mac) is not None

    @property
    def name(self) -> str:
        dev = _find_device(self.coordinator.data, self._mac)
        if dev:
            return _device_hostname(dev) or self._initial_hostname
        return self._initial_hostname

    @property
    def ip_address(self) -> str | None:
        dev = _find_device(self.coordinator.data, self._mac)
        return _device_ip(dev) if dev else None

    @property
    def mac_address(self) -> str:
        return self._mac

    @property
    def hostname(self) -> str | None:
        dev = _find_device(self.coordinator.data, self._mac)
        return _device_hostname(dev) if dev else self._initial_hostname

    @property
    def extra_state_attributes(self) -> dict:
        dev = _find_device(self.coordinator.data, self._mac)
        if not dev:
            return {}
        return {
            "connection_type": _device_connection_type(dev),
            "speed_mbps": dev.get("agreed_rate") or dev.get("speed"),
            "connect_time_seconds": dev.get("connect_time") or dev.get("online_time"),
            "addr_type": dev.get("addr_type") or dev.get("address_type"),
        }

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
