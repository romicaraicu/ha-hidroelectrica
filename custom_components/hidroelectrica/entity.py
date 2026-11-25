"""Entitate de bază Hidroelectrica (un device per loc de consum)."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, MANUFACTURER, PORTAL_URL
from .coordinator import HidroelectricaCoordinator
from .parser import AccountData


class HidroelectricaEntity(CoordinatorEntity[HidroelectricaCoordinator]):
    """Entitate legată de un cont (loc de consum)."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HidroelectricaCoordinator, uan: str, key: str, platform: str
    ) -> None:
        super().__init__(coordinator)
        self._uan = uan
        self._attr_translation_key = key
        self._attr_unique_id = f"{uan}_{key}"
        # Entity ID previzibil, folosit și de dashboard-ul inclus:
        # sensor.hidroelectrica_<cont>_<cheie>
        self.entity_id = f"{platform}.{DOMAIN}_{slugify(uan)}_{key}"
        data = coordinator.data.get(uan)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uan)},
            name=f"Hidroelectrica {data.address if data else uan}",
            manufacturer=MANUFACTURER,
            model="Loc de consum",
            serial_number=(data.pod if data else None) or uan,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=PORTAL_URL,
        )

    @property
    def account_data(self) -> AccountData | None:
        return (self.coordinator.data or {}).get(self._uan)

    @property
    def available(self) -> bool:
        return super().available and self.account_data is not None
