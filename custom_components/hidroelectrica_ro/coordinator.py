"""DataUpdateCoordinator pentru Hidroelectrica."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    HidroelectricaApi,
    HidroelectricaAuthError,
    HidroelectricaConnectionError,
    HidroelectricaError,
)
from .const import (
    CONF_ACCOUNTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    HISTORY_YEARS,
)
from .parser import AccountData, account_id, build_account_data

_LOGGER = logging.getLogger(__name__)


class HidroelectricaCoordinator(DataUpdateCoordinator[dict[str, AccountData]]):
    """Descarcă datele tuturor conturilor selectate."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: HidroelectricaApi) -> None:
        hours = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=timedelta(hours=hours),
        )
        self.api = api
        self.accounts: list[dict[str, Any]] = []
        self.raw: dict[str, dict[str, Any]] = {}

    @property
    def selected_accounts(self) -> list[str] | None:
        """Conturile alese de utilizator (None = toate)."""
        return self.config_entry.options.get(CONF_ACCOUNTS) or None

    async def _optional(self, label: str, uan: str, coro) -> Any:
        """Un endpoint care poate lipsi fără să oprească actualizarea."""
        try:
            return await coro
        except HidroelectricaConnectionError as err:
            _LOGGER.debug("%s indisponibil pentru %s: %s", label, uan, err)
            return None

    async def _fetch_account(self, account: dict[str, Any]) -> dict[str, Any]:
        uan = account_id(account)
        number = str(account.get("AccountNumber") or "").strip()
        today = date.today()
        start = date(today.year - HISTORY_YEARS + 1, 1, 1)
        bill, history, usage, window, pods = await asyncio.gather(
            self._optional("GetBill", uan, self.api.get_bill(uan, number)),
            self.api.get_billing_history(uan, number, start, today),
            self._optional("GetUsageGeneration", uan, self.api.get_usage(uan, number)),
            self._optional("GetWindowDates", uan, self.api.get_window_dates(uan, number)),
            self._optional("GetPods", uan, self.api.get_pods(uan, number)),
        )
        return {
            "account": account,
            "bill": bill,
            "history": history,
            "usage": usage,
            "window": window,
            "pods": pods,
        }

    async def _async_update_data(self) -> dict[str, AccountData]:
        try:
            accounts = await self.api.get_accounts()
            if self.selected_accounts:
                accounts = [a for a in accounts if account_id(a) in self.selected_accounts]
            raw: dict[str, dict[str, Any]] = {}
            for account in accounts:
                raw[account_id(account)] = await self._fetch_account(account)
        except HidroelectricaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except HidroelectricaError as err:
            raise UpdateFailed(str(err)) from err

        self.accounts = accounts
        self.raw = raw
        return {uan: build_account_data(uan, data) for uan, data in raw.items()}
