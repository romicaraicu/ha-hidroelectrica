"""Config flow pentru Hidroelectrica."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import HidroelectricaApi, HidroelectricaAuthError, HidroelectricaError
from .const import (
    CONF_ACCOUNTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    MAX_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
)
from .parser import account_id

_LOGGER = logging.getLogger(__name__)

CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


def _interval_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL_HOURS,
            max=MAX_SCAN_INTERVAL_HOURS,
            step=1,
            unit_of_measurement="h",
            mode=NumberSelectorMode.SLIDER,
        )
    )


def _accounts_selector(accounts: list[dict[str, Any]]) -> SelectSelector:
    options = []
    for acc in accounts:
        uan = account_id(acc)
        if not uan:
            continue
        label = str(acc.get("Address") or uan).strip()
        options.append(SelectOptionDict(value=uan, label=f"{label} ({uan})"))
    return SelectSelector(
        SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.LIST)
    )


async def _validate(hass, username: str, password: str) -> list[dict[str, Any]]:
    """Autentifică și întoarce conturile (locurile de consum)."""
    api = HidroelectricaApi(async_get_clientsession(hass), username, password)
    await api.authenticate()
    return await api.get_accounts()


class HidroelectricaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fluxul de adăugare a unui cont iHidro."""

    VERSION = 1

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._accounts: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME].strip()
            self._password = user_input[CONF_PASSWORD]
            await self.async_set_unique_id(self._username.lower())
            self._abort_if_unique_id_configured()
            try:
                self._accounts = await _validate(self.hass, self._username, self._password)
            except HidroelectricaAuthError as err:
                _LOGGER.debug("Autentificare eșuată: %s", err)
                errors["base"] = "invalid_auth"
            except HidroelectricaError as err:
                _LOGGER.warning("Nu mă pot conecta la iHidro: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Eroare neașteptată")
                errors["base"] = "unknown"
            else:
                if not any(account_id(a) for a in self._accounts):
                    errors["base"] = "no_accounts"
                else:
                    return await self.async_step_accounts()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA, {CONF_USERNAME: self._username}
            ),
            errors=errors,
        )

    async def async_step_accounts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        all_ids = [account_id(a) for a in self._accounts if account_id(a)]
        if user_input is not None or len(all_ids) == 1:
            chosen = (user_input or {}).get(CONF_ACCOUNTS) or all_ids
            return self.async_create_entry(
                title=self._username,
                data={CONF_USERNAME: self._username, CONF_PASSWORD: self._password},
                options={
                    CONF_ACCOUNTS: chosen,
                    CONF_SCAN_INTERVAL: (user_input or {}).get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
                    ),
                },
            )
        return self.async_show_form(
            step_id="accounts",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNTS, default=all_ids): _accounts_selector(
                        self._accounts
                    ),
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_HOURS
                    ): _interval_selector(),
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        self._username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _validate(self.hass, self._username, user_input[CONF_PASSWORD])
            except HidroelectricaAuthError:
                errors["base"] = "invalid_auth"
            except HidroelectricaError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"username": self._username},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HidroelectricaOptionsFlow()


class HidroelectricaOptionsFlow(OptionsFlow):
    """Reconfigurare: locuri de consum și interval de actualizare."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={**self.config_entry.options, **user_input})

        coordinator = getattr(self.config_entry, "runtime_data", None)
        accounts = (coordinator.accounts if coordinator else None) or []
        if coordinator and not accounts:
            try:
                accounts = await coordinator.api.get_accounts()
            except HidroelectricaError:
                accounts = []
        current = self.config_entry.options.get(CONF_ACCOUNTS) or [
            account_id(a) for a in accounts if account_id(a)
        ]
        schema: dict[Any, Any] = {}
        if accounts:
            schema[vol.Required(CONF_ACCOUNTS, default=current)] = _accounts_selector(accounts)
        schema[
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
                ),
            )
        ] = _interval_selector()
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
