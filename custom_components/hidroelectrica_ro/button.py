"""Buton de actualizare manuală Hidroelectrica."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HidroelectricaConfigEntry
from .entity import HidroelectricaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HidroelectricaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        HidroelectricaRefreshButton(coordinator, uan) for uan in coordinator.data
    )


class HidroelectricaRefreshButton(HidroelectricaEntity, ButtonEntity):
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator, uan: str) -> None:
        super().__init__(coordinator, uan, "actualizare", "button")

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
