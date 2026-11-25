"""Senzori Hidroelectrica."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HidroelectricaConfigEntry
from .entity import HidroelectricaEntity
from .parser import AccountData, iso

CURRENCY = "RON"
HISTORY_LIMIT = 36
PAID_LIMIT = 12


@dataclass(frozen=True, kw_only=True)
class HSensorDescription(SensorEntityDescription):
    value_fn: Callable[[AccountData], Any]
    attrs_fn: Callable[[AccountData], dict[str, Any]] | None = None


def _location_attrs(d: AccountData) -> dict[str, Any]:
    return {
        "cont": d.uan,
        "numar_cont": d.account_number or None,
        "pod": d.pod,
        "instalatie": d.installation,
        "contor": d.meter,
        "distribuitor": d.distributor,
    }


def _last_consumption_attrs(d: AccountData) -> dict[str, Any]:
    last = d.last_consumption
    history = [e.as_attr() for e in reversed(d.consumption)][:HISTORY_LIMIT]
    return {
        **(last.as_attr() if last else {}),
        "consum_anual": d.yearly_consumption(),
        "istoric": history,
    }


def _current_year_kwh(d: AccountData) -> float | None:
    totals = d.yearly_consumption()
    if not totals:
        return None
    return totals.get(str(date.today().year), 0.0)


def _current_year_paid(d: AccountData) -> float | None:
    costs = d.yearly_costs()
    if not costs:
        return None
    return costs.get(str(date.today().year), {}).get("platit", 0.0)


def _cost_attrs(d: AccountData) -> dict[str, Any]:
    costs = d.yearly_costs()
    current = costs.get(str(date.today().year), {})
    return {
        "facturat": current.get("facturat", 0.0),
        "de_plata": current.get("de_plata", 0.0),
        "facturi": current.get("facturi", 0),
        "cost_anual": costs,
    }


def _balance_attrs(d: AccountData) -> dict[str, Any]:
    return {
        "restant": d.overdue_amount,
        "urmatoarea_scadenta": iso(d.next_due_date),
        "facturi_neplatite": len(d.unpaid_invoices),
    }


def _unpaid_attrs(d: AccountData) -> dict[str, Any]:
    return {
        "total_rest_plata": round(sum(i.rest_plata for i in d.unpaid_invoices), 2),
        "restant": d.overdue_amount,
        "urmatoarea_scadenta": iso(d.next_due_date),
        "facturi": [i.as_attr() for i in d.unpaid_invoices],
    }


def _paid_attrs(d: AccountData) -> dict[str, Any]:
    paid = d.paid_invoices
    return {
        "ultima_factura_platita": paid[0].as_attr() if paid else None,
        "facturi": [i.as_attr() for i in paid[:PAID_LIMIT]],
    }


def _latest_invoice_attrs(d: AccountData) -> dict[str, Any]:
    latest = d.latest_invoice
    return latest.as_attr() if latest else {}


def _payment_attrs(d: AccountData) -> dict[str, Any]:
    last = d.last_payment or {}
    return {"data": last.get("data"), "canal": last.get("canal"), "plati": d.payments[:PAID_LIMIT]}


def _reading_attrs(d: AccountData) -> dict[str, Any]:
    today = date.today()
    start, end, is_open = d.window.start, d.window.end, d.window.is_open
    return {
        "inceput": iso(start),
        "sfarsit": iso(end),
        "activa": is_open,
        "zile_pana_la_inceput": (start - today).days if start and start > today else 0,
        "zile_ramase": (end - today).days if end and is_open and end >= today else 0,
    }


SENSORS: tuple[HSensorDescription, ...] = (
    HSensorDescription(
        key="loc_consum",
        icon="mdi:home-lightning-bolt-outline",
        value_fn=lambda d: d.address[:255],
        attrs_fn=_location_attrs,
    ),
    HSensorDescription(
        key="consum_ultima_luna",
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda d: round(d.last_consumption.kwh, 2) if d.last_consumption else None,
        attrs_fn=_last_consumption_attrs,
    ),
    HSensorDescription(
        key="consum_an_curent",
        icon="mdi:calendar-month-outline",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=0,
        value_fn=_current_year_kwh,
        attrs_fn=lambda d: {"consum_anual": d.yearly_consumption()},
    ),
    HSensorDescription(
        key="cost_an_curent",
        icon="mdi:cash-multiple",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=_current_year_paid,
        attrs_fn=_cost_attrs,
    ),
    HSensorDescription(
        key="total_de_plata",
        icon="mdi:cash-clock",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda d: d.total_balance,
        attrs_fn=_balance_attrs,
    ),
    HSensorDescription(
        key="facturi_neplatite",
        icon="mdi:file-alert-outline",
        native_unit_of_measurement="facturi",
        value_fn=lambda d: len(d.unpaid_invoices),
        attrs_fn=_unpaid_attrs,
    ),
    HSensorDescription(
        key="facturi_platite",
        icon="mdi:file-check-outline",
        native_unit_of_measurement="facturi",
        value_fn=lambda d: len(d.paid_invoices),
        attrs_fn=_paid_attrs,
    ),
    HSensorDescription(
        key="ultima_factura",
        icon="mdi:file-document-outline",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda d: round(d.latest_invoice.valoare, 2) if d.latest_invoice else None,
        attrs_fn=_latest_invoice_attrs,
    ),
    HSensorDescription(
        key="urmatoarea_scadenta",
        icon="mdi:calendar-alert",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: d.next_due_date,
    ),
    HSensorDescription(
        key="ultima_plata",
        icon="mdi:cash-check",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda d: (d.last_payment or {}).get("suma"),
        attrs_fn=_payment_attrs,
    ),
    HSensorDescription(
        key="perioada_index",
        icon="mdi:counter",
        value_fn=lambda d: d.window.label,
        attrs_fn=_reading_attrs,
    ),
    HSensorDescription(
        key="perioada_index_inceput",
        icon="mdi:calendar-start",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: d.window.start,
    ),
    HSensorDescription(
        key="perioada_index_sfarsit",
        icon="mdi:calendar-end",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: d.window.end,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HidroelectricaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        HidroelectricaSensor(coordinator, uan, description)
        for uan in coordinator.data
        for description in SENSORS
    )


class HidroelectricaSensor(HidroelectricaEntity, SensorEntity):
    entity_description: HSensorDescription

    def __init__(self, coordinator, uan: str, description: HSensorDescription) -> None:
        super().__init__(coordinator, uan, description.key, "sensor")
        self.entity_description = description
        self._update_values()

    def _update_values(self) -> None:
        data = self.account_data
        if data is None:
            return
        self._attr_native_value = self.entity_description.value_fn(data)
        attrs_fn = self.entity_description.attrs_fn
        self._attr_extra_state_attributes = attrs_fn(data) if attrs_fn else {}

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_values()
        super()._handle_coordinator_update()
