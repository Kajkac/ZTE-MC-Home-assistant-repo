import json
import time
import logging
import subprocess
import asyncio
from datetime import datetime, timedelta
from homeassistant.helpers.entity import Entity, EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from .const import (
    DOMAIN, SENSOR_NAMES, MANUFACTURER, MODEL, UNITS,
    DISABLED_SENSORS_MC889, DISABLED_SENSORS_MC888, DISABLED_SENSORS_MC801A,
    DIAGNOSTICS_SENSORS
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ip_entry = entry.data["router_ip"]
    password_entry = entry.data["router_password"]
    ping_interval = entry.data.get("ping_interval", 60)
    sms_check_interval = entry.data.get("sms_check_interval", 100)
    router_type = entry.data.get("router_type", "MC801A")

    _LOGGER.info(f"Router type selected: {router_type}")
    _LOGGER.info(f"Ping interval: {ping_interval} seconds")
    _LOGGER.info(f"SMS check interval: {sms_check_interval} seconds")

    if router_type == "MC889":
        disabled_sensors = DISABLED_SENSORS_MC889
    elif router_type == "MC888":
        disabled_sensors = DISABLED_SENSORS_MC888
    else:
        disabled_sensors = DISABLED_SENSORS_MC801A

    coordinator = ZTERouterDataUpdateCoordinator(hass, ip_entry, password_entry, ping_interval)
    sms_coordinator = ZTERouterSMSUpdateCoordinator(hass, ip_entry, password_entry, sms_check_interval)

    await coordinator.async_refresh()
    await sms_coordinator.async_refresh()

    if not coordinator.last_update_success or not sms_coordinator.last_update_success:
        _LOGGER.error("Coordinator(s) failed to refresh successfully.")
        raise PlatformNotReady

    sensors = []
    for key in coordinator.data.keys():
        name = SENSOR_NAMES.get(key, key)  # Get the friendly name or default to key
        sensors.append(ZTERouterSensor(coordinator, name, key, disabled_sensors.get(key, False)))

    # Add new dynamic set of sensors
    dynamic_data = await hass.async_add_executor_job(
        coordinator.run_mc_script, ip_entry, password_entry, 3
    )
    _LOGGER.debug(f"Data for command 3: {dynamic_data}")
    dynamic_data = json.loads(dynamic_data)
    coordinator._data.update(dynamic_data)  # Update coordinator's data with dynamic data
    for key in dynamic_data.keys():
        name = SENSOR_NAMES.get(key, key)
        sensors.append(ZTERouterSensor(coordinator, name, key, disabled_sensors.get(key, False)))

    # Add the new sensor for command 6
    additional_data = await hass.async_add_executor_job(
        coordinator.run_mc_script, ip_entry, password_entry, 6
    )
    _LOGGER.debug(f"Data for command 6: {additional_data}")
    additional_data = json.loads(additional_data)
    coordinator._data.update(additional_data)  # Update coordinator's data with additional data
    for key in additional_data.keys():
        name = SENSOR_NAMES.get(key, key)
        sensors.append(ZTERouterSensor(coordinator, name, key, disabled_sensors.get(key, False)))

    # Add the new sensor for Last SMS
    if "content" in additional_data:
        sensors.append(LastSMSSensor(sms_coordinator, additional_data, disabled_sensors.get("last_sms", False)))  # Use the SMS coordinator

    # Add the Connected Bands sensor
    sensors.append(ConnectedBandsSensor(coordinator, disabled_sensors.get("connected_bands", False)))

    # Add the custom formatted sensors
    sensors.append(MonthlyUsageSensor(coordinator))
    sensors.append(monthly_tx_gb(coordinator))
    sensors.append(monthly_rx_gb(coordinator))
    sensors.append(DataLeftSensor(coordinator))
    sensors.append(ConnectionUptimeSensor(coordinator))

    _LOGGER.info(f"Sensors added: {[sensor.name for sensor in sensors]}")
    _LOGGER.info(f"Diagnostics sensors: {[sensor.name for sensor in sensors if sensor.is_diagnostics]}")

    async_add_entities(sensors, True)

class ZTERouterDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, ip_entry, password_entry, ping_interval):
        self.ip_entry = ip_entry
        self.password_entry = password_entry
        self._data = {}
        _LOGGER.info(f"Initializing DataUpdateCoordinator with ping interval: {ping_interval} seconds")
        super().__init__(
            hass,
            _LOGGER,
            name="zte_router",
            update_interval=timedelta(seconds=ping_interval),  # Use ping_interval
        )

    async def _async_update_data(self):
        _LOGGER.info("Starting _async_update_data in DataUpdateCoordinator at %s", datetime.now())
        try:
            # Add an 8-second delay before executing the script
            await asyncio.sleep(8)
            # Offload the blocking function to a thread
            data = await self.hass.async_add_executor_job(
                self.run_mc_script, self.ip_entry, self.password_entry, 7
            )
            _LOGGER.debug(f"Data received from mc.py script: {data}")
            self._data.update(json.loads(data))
            return self._data
        except Exception as err:
            _LOGGER.error(f"Error during _async_update_data: {err}")
            return self._data

    def run_mc_script(self, ip, password, command, retries=3, delay=2):
        attempt = 0
        while attempt < retries:
            _LOGGER.info(f"Running mc.py script for command {command}, attempt {attempt + 1}")
            try:
                result = subprocess.run(
                    ["python3", "/config/custom_components/zte_router/mc.py", ip, password, str(command)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                _LOGGER.debug(f"Output for command {command}: {result.stdout}")
                return result.stdout
            except subprocess.CalledProcessError as e:
                _LOGGER.warning(f"Attempt {attempt + 1} failed with error: {e}. Retrying in {delay} seconds...")
                attempt += 1
                if attempt < retries:
                    time.sleep(delay)
                    delay *= 2  # Double the delay time for the next retry
                else:
                    _LOGGER.error(f"All {retries} attempts failed for command {command}. Raising error.")
                    raise

class ZTERouterSMSUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, ip_entry, password_entry, sms_check_interval):
        self.ip_entry = ip_entry
        self.password_entry = password_entry
        self._data = {}
        _LOGGER.info(f"Initializing SMSUpdateCoordinator with SMS check interval: {sms_check_interval} seconds")
        super().__init__(
            hass,
            _LOGGER,
            name="zte_router_sms",
            update_interval=timedelta(seconds=sms_check_interval),  # Use sms_check_interval
        )

    async def _async_update_data(self):
        _LOGGER.info("Starting _async_update_data in SMSUpdateCoordinator at %s", datetime.now())
        try:
            # Add a 5-second delay before executing the script
            await asyncio.sleep(5)
            # Offload the blocking function to a thread
            data = await self.hass.async_add_executor_job(
                self.run_mc_script, self.ip_entry, self.password_entry, 6
            )
            _LOGGER.debug(f"SMS data received from mc.py script: {data}")
            self._data.update(json.loads(data))
            return self._data
        except Exception as err:
            _LOGGER.error(f"Error during _async_update_data (SMS): {err}")
            return self._data

    def run_mc_script(self, ip, password, command):
        _LOGGER.info(f"Running mc.py script for SMS command {command}")
        try:
            result = subprocess.run(
                ["python3", "/config/custom_components/zte_router/mc.py", ip, password, str(command)],
                capture_output=True,
                text=True,
                check=True
            )
            _LOGGER.debug(f"Output for SMS command {command}: {result.stdout}")
            return result.stdout
        except subprocess.CalledProcessError as e:
            _LOGGER.error(f"Error running SMS command {command}: {e}")
            raise

class ZTERouterEntity(RestoreEntity, Entity):
    """Base class for ZTE Router sensors to ensure consistent MRO."""

    async def async_added_to_hass(self):
        _LOGGER.info(f"Entity {self.name} added to hass at {datetime.now()}")
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            if hasattr(self, "_attributes"):
                self._attributes.update(last_state.attributes)
            _LOGGER.debug(f"Restored state for {self.name}: {self._state}")
        self.async_on_remove(self.coordinator.async_add_listener(
            lambda: asyncio.ensure_future(self.async_handle_coordinator_update())
        ))
        await self.async_handle_coordinator_update()

class ZTERouterSensor(ZTERouterEntity):
    def __init__(self, coordinator, name, key, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = name
        self._key = key
        self._state = None
        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_is_diagnostics = key in DIAGNOSTICS_SENSORS
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing sensor {self._name} with key {self._key}")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_{self._key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        """Return True if the entity is available."""
        return True

    @property
    def unit_of_measurement(self):
        return UNITS.get(self._key)

    @property
    def is_diagnostics(self):
        return self._attr_is_diagnostics

    @property
    def entity_category(self):
        if self.is_diagnostics:
            return EntityCategory.DIAGNOSTIC
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for sensor {self._name} at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            new_state = self.coordinator.data.get(self._key, None)
            if new_state is not None:
                self._state = new_state
                _LOGGER.info(f"Sensor {self._name} updated. Old state: {old_state}, New state: {self._state}")
            else:
                _LOGGER.warning(f"No new data for sensor {self._name}. Retaining last state: {self._state}")
        else:
            _LOGGER.warning(f"No data available from coordinator for sensor {self._name}. Retaining last state: {self._state}")
        self.async_write_ha_state()

class LastSMSSensor(ZTERouterEntity):
    def __init__(self, coordinator, sms_data, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = "Last SMS"
        self._state = sms_data.get("content", "NO DATA")  # Default to "NO DATA" if content is not available
        self._attributes = {k: v for k, v in sms_data.items() if k != "content"}
        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Last SMS sensor with state: {self._state}")

        # Parse and format the date attribute
        if "date" in self._attributes:
            self._attributes["formatted_date"] = self.format_date(self._attributes["date"])

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_last_sms"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        """Return True if the entity is available."""
        return True

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def is_diagnostics(self):
        return True  # LastSMS is a diagnostic sensor

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Last SMS sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    async def async_handle_coordinator_update(self):
        old_state = self._state
        _LOGGER.debug(f"Updating LastSMS sensor with new data: {self.coordinator.data}")
        data = self.coordinator.data
        if data and "content" in data:
            self._state = data.get("content", "NO DATA")  # Default to "NO DATA" if content is not available
            self._attributes = {k: v for k, v in data.items() if k != "content"}
            if "date" in self._attributes:
                self._attributes["formatted_date"] = self.format_date(self._attributes["date"])
            _LOGGER.info(f"Last SMS sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"No new SMS data available. Retaining last state: {self._state}")
        self.async_write_ha_state()

    def format_date(self, date_str):
        try:
            # Extract the date parts from the string
            parts = date_str.split(',')
            if len(parts) == 7 and all(parts):
                year = int(parts[0]) + 2000  # Assuming the year is in the format 'YY'
                month = int(parts[1])
                day = int(parts[2])
                hour = int(parts[3])
                minute = int(parts[4])
                second = int(parts[5])
                timezone_offset = parts[6]

                # Create a datetime object
                dt = datetime(year, month, day, hour, minute, second)

                # Format the date to a more readable format
                formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")

                # Append timezone offset
                formatted_date += f" UTC{timezone_offset}"

                return formatted_date
            else:
                return date_str  # Return the original string if it doesn't match the expected format
        except ValueError as e:
            _LOGGER.error(f"Error parsing date string {date_str}: {e}")
            return date_str

def format_ca_bands(ca_bands, nr5g_action_band):
    if not ca_bands:
        return "No CA"
    ca_bands_list = ca_bands.split(";")
    ca_bands_formatted = []
    for band in ca_bands_list:
        band_info = band.split(",")
        if len(band_info) >= 6:
            band_id = band_info[3]  # Use the appropriate index for the band identifier
            bandwidth = band_info[5]
            ca_bands_formatted.append(f"B{band_id}(@{bandwidth}Mhz)")
    if nr5g_action_band:
        ca_bands_formatted.append(f"{nr5g_action_band}")
    return "+".join(ca_bands_formatted)

class ConnectedBandsSensor(ZTERouterEntity):
    def __init__(self, coordinator, disabled_by_default=False):
        self.coordinator = coordinator
        self._name = "Connected Bands"
        self._state = None
        self._attributes = {}
        self.entity_registry_enabled_default = not disabled_by_default
        self._attr_is_diagnostics = True  # Ensure ConnectedBands is marked as diagnostics
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Connected Bands sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_connected_bands"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        """Return True if the entity is available."""
        return True

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def is_diagnostics(self):
        return self._attr_is_diagnostics

    @property
    def entity_category(self):
        if self.is_diagnostics:
            return EntityCategory.DIAGNOSTIC
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Connected Bands sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            rmcc = data.get("rmcc", "")
            rmnc = data.get("rmnc", "")
            cell_id = data.get("cell_id", "")
            wan_ip = data.get("wan_ipaddr", "")
            main_band = data.get("lte_ca_pcell_band", "")
            main_bandwidth = data.get("lte_ca_pcell_bandwidth", "")
            ca_bands = data.get("lte_multi_ca_scell_info", "")
            ca_bands_formatted = format_ca_bands(ca_bands, data.get("nr5g_action_band", ""))

            # Calculate enbid
            try:
                enb_id = int(cell_id, 16) // 256 if cell_id else ""
            except ValueError:
                _LOGGER.error(f"Invalid cell_id for conversion to int: {cell_id}")
                enb_id = ""

            self._state = f"MAIN:B{main_band}(@{main_bandwidth}Mhz) CA:{ca_bands_formatted}"
            self._attributes = {
                "rmcc": rmcc,
                "rmnc": rmnc,
                "cell_id": cell_id,
                "wan_ip": wan_ip,
                "main_band": main_band,
                "main_bandwidth": main_bandwidth,
                "ca_bands": ca_bands,
                "enb_id": enb_id,
            }
            _LOGGER.info(f"Connected Bands sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"No data available for Connected Bands sensor. Retaining last state: {self._state}")
        self.async_write_ha_state()

class MonthlyUsageSensor(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Monthly Usage"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Monthly Usage sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_monthly_usage"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        """Return True if the entity is available."""
        return True

    @property
    def unit_of_measurement(self):
        return "GB"

    @property
    def is_diagnostics(self):
        return False  # MonthlyUsage is not a diagnostic sensor

    @property
    def entity_category(self):
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Monthly Usage sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            monthly_tx_bytes = float(data.get("monthly_tx_bytes", 0) or 0)
            monthly_rx_bytes = float(data.get("monthly_rx_bytes", 0) or 0)
            monthly_usage_gb = (monthly_tx_bytes + monthly_rx_bytes) / 1024 / 1024 / 1024
            self._state = round(monthly_usage_gb, 2)
            _LOGGER.info(f"Monthly Usage sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"No data available for Monthly Usage sensor. Retaining last state: {self._state}")
        self.async_write_ha_state()

#define GB TX sensor
class monthly_tx_gb(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Monthly TX GB"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Monthly TX GB sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_monthly_tx_gb"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        """Return True if the entity is available."""
        return True

    @property
    def unit_of_measurement(self):
        return "GB"

    @property
    def is_diagnostics(self):
        return False  #Monthly GB Sensor is not a diagnostic sensor

    @property
    def entity_category(self):
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Monthly TX GB sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            monthly_tx_bytes = float(data.get("monthly_tx_bytes", 0) or 0)
            monthly_tx_gb = monthly_tx_bytes / 1024 / 1024 / 1024
            self._state = round(monthly_tx_gb, 2)
            _LOGGER.info(f"Monthly TX GB sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"No data available for Monthly TX GB sensor. Retaining last state: {self._state}")
        self.async_write_ha_state()

#define GB RX sensor
class monthly_rx_gb(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Monthly RX GB"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Monthly RX GB sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_monthly_rx_gb"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        """Return True if the entity is available."""
        return True

    @property
    def unit_of_measurement(self):
        return "GB"

    @property
    def is_diagnostics(self):
        return False  #Monthly GB Sensor is not a diagnostic sensor

    @property
    def entity_category(self):
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Monthly RX GB sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            data = self.coordinator.data
            monthly_rx_bytes = float(data.get("monthly_rx_bytes", 0) or 0)
            monthly_rx_gb = monthly_rx_bytes / 1024 / 1024 / 1024
            self._state = round(monthly_rx_gb, 2)
            _LOGGER.info(f"Monthly RX GB sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"No data available for Monthly RX GB sensor. Retaining last state: {self._state}")
        self.async_write_ha_state()

#define DataLeftSensor
class DataLeftSensor(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Data Left"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Data Left sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_data_left"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        """Return True if the entity is available."""
        return True

    @property
    def unit_of_measurement(self):
        return "GB"

    @property
    def is_diagnostics(self):
        return False  # DataLeft is not a diagnostic sensor

    @property
    def entity_category(self):
        return None

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Data Left sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            monthly_usage = float(self.hass.states.get("sensor.monthly_usage").state or 0)
            # Use the configurable threshold from the options
            threshold = self.coordinator.config_entry.options.get("monthly_usage_threshold", 200)
            data_left = threshold - monthly_usage if monthly_usage < threshold else 50 - (monthly_usage % 50)
            self._state = round(data_left, 2)
            _LOGGER.info(f"Data Left sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"No data available for Data Left sensor. Retaining last state: {self._state}")
        self.async_write_ha_state()

class ConnectionUptimeSensor(ZTERouterEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._name = "Connection Uptime"
        self._state = None
        self.entity_registry_enabled_default = True  # Set to True, enabled by default
        self._attr_should_poll = False  # Disable default polling
        _LOGGER.info(f"Initializing Connection Uptime sensor")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.coordinator.ip_entry}_connection_uptime"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}_{self.coordinator.ip_entry}")},
            "name": self.coordinator.ip_entry,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data.get("wa_inner_version", "Unknown")
        }

    @property
    def available(self):
        """Return True if the entity is available."""
        return True

    @property
    def unit_of_measurement(self):
        return UNITS.get("connection_uptime")

    @property
    def is_diagnostics(self):
        return True  # ConnectionUptime is a diagnostic sensor

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    async def async_update(self):
        _LOGGER.info(f"Manual update requested for Connection Uptime sensor at {datetime.now()}")
        await self.coordinator.async_request_refresh()

    async def async_handle_coordinator_update(self):
        old_state = self._state
        if self.coordinator.data:
            realtime_time = float(self.coordinator.data.get("realtime_time", 0) or 0)
            uptime_hours = realtime_time / 3600
            self._state = round(uptime_hours, 2)
            _LOGGER.info(f"Connection Uptime sensor updated. Old state: {old_state}, New state: {self._state}")
        else:
            _LOGGER.warning(f"No data available for Connection Uptime sensor. Retaining last state: {self._state}")
        self.async_write_ha_state()
