"""Senzori binari Hidroelectrica."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HidroelectricaConfigEntry
from .entity import HidroelectricaEntity
from .parser import AccountData, iso


@dataclass(frozen=True, kw_only=True)
class HBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[AccountData], bool]


BINARY_SENSORS: tuple[HBinaryDescription, ...] = (
    HBinaryDescription(
        key="perioada_index_activa",
        icon="mdi:counter",
        value_fn=lambda d: d.window.is_open,
    ),
    HBinaryDescription(
        key="factura_restanta",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.overdue_amount > 0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HidroelectricaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        HidroelectricaBinarySensor(coordinator, uan, description)
        for uan in coordinator.data
        for description in BINARY_SENSORS
    )


class HidroelectricaBinarySensor(HidroelectricaEntity, BinarySensorEntity):
    entity_description: HBinaryDescription

    def __init__(self, coordinator, uan: str, description: HBinaryDescription) -> None:
        super().__init__(coordinator, uan, description.key, "binary_sensor")
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        data = self.account_data
        return self.entity_description.value_fn(data) if data else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.account_data
        if data is None:
            return {}
        if self.entity_description.key == "perioada_index_activa":
            return {"inceput": iso(data.window.start), "sfarsit": iso(data.window.end)}
        return {"restant": data.overdue_amount}
