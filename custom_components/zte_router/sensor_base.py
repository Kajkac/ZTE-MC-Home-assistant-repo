"""Shared base class and decorator used by all ZTE Router sensor entities."""

import asyncio
import logging
from datetime import datetime

from homeassistant.helpers.entity import Entity, EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)


def guard_stale_data(update_func):
    async def wrapper(self, *args, **kwargs):
        if not self.coordinator.last_update_success and not self.coordinator.allow_stale_data:
            _LOGGER.warning(f"{self._name}: Clearing state due to failed update and stale data disabled.")
            self._state = None
            if hasattr(self, '_attributes'):
                self._attributes.clear()
            self.async_write_ha_state()
            return
        await update_func(self, *args, **kwargs)
        self.async_write_ha_state()  # <-- ensure state always updates after success
    return wrapper


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

    def _get_value(self, key):
        """Strict fetch that respects allow_stale_data."""
        if not self.coordinator.last_update_success and not self.coordinator.allow_stale_data:
            _LOGGER.debug(f"[STRICT MODE] {self.name}: blocked access to stale key '{key}'")
            return None
        return self.coordinator.data.get(key)

    @property
    def is_diagnostics(self) -> bool:
        return getattr(self, "_attr_is_diagnostics", False)

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC if self.is_diagnostics else None

    @property
    def extra_state_attributes(self):
        # Only return attributes if self._attributes is defined
        return getattr(self, "_attributes", {})
