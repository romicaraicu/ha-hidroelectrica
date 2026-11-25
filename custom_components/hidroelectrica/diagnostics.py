"""Diagnostic Hidroelectrica (date personale mascate)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import HidroelectricaConfigEntry

TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "adresa",
    "cont",
    "numar_cont",
    "pod",
    "instalatie",
    "contor",
}


def _shape(value: Any, depth: int = 0) -> Any:
    """Structura unui JSON (chei + tipuri), fără valori."""
    if depth > 6:
        return "…"
    if isinstance(value, dict):
        return {k: _shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1), f"x{len(value)}"] if value else []
    return type(value).__name__


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HidroelectricaConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    accounts = {
        f"cont_{i + 1}": data.summary()
        for i, data in enumerate((coordinator.data or {}).values())
    }
    raw = coordinator.raw or {}
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": {**entry.options, "accounts": len(entry.options.get("accounts") or [])},
        "last_update_success": coordinator.last_update_success,
        "rezumat": async_redact_data(accounts, TO_REDACT),
        "structura_raspunsuri": {
            f"cont_{i + 1}": {k: _shape(v) for k, v in data.items() if k != "account"}
            for i, data in enumerate(raw.values())
        },
    }
