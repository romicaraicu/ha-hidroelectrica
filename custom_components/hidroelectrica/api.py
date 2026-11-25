"""Client pentru API-ul aplicației de mobil iHidro (Hidroelectrica).

Portalul web (ihidro.ro/portal) cere captcha Cloudflare Turnstile la login, așa
că folosim API-ul aplicației de mobil (platforma SEW "smartcmobile"):

1. GetId              -> key + tokenId          (Basic key:tokenId la pasul 2)
2. ValidateUserLogin  -> UserID + SessionToken  (Basic UserID:SessionToken după)
3. Apeluri autentificate (SourceType=1)

Modulul nu depinde de Home Assistant (testabil cu tools/test_connection.py).
"""

from __future__ import annotations

import asyncio
import base64
from datetime import date, datetime
import json
import logging
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_HOST_HEADER,
    API_USER_AGENT,
    EP_BILL,
    EP_BILLING_HISTORY,
    EP_GET_ID,
    EP_PODS,
    EP_USAGE,
    EP_USER_SETTING,
    EP_VALIDATE_LOGIN,
    EP_WINDOW_DATES,
    LANGUAGE,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=45)
_SESSION_HINTS = ("session", "sesiun", "token", "expir", "unauthor", "neautoriz")


class HidroelectricaError(Exception):
    """Eroare generică Hidroelectrica."""


class HidroelectricaAuthError(HidroelectricaError):
    """Utilizator sau parolă incorecte / cont blocat."""


class HidroelectricaConnectionError(HidroelectricaError):
    """Eroare de rețea sau răspuns neașteptat de la server."""


def _basic(user: str, secret: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()


def result_of(body: Any) -> dict[str, Any]:
    """`result` din răspunsul standard SEW ({version, status_code, result})."""
    if isinstance(body, dict) and isinstance(body.get("result"), dict):
        return body["result"]
    return {}


def data_of(body: Any) -> Any:
    """`result.Data` din răspunsul standard SEW."""
    return result_of(body).get("Data")


def _message(body: Any) -> str:
    result = result_of(body)
    return str(result.get("Message") or result.get("message") or "").strip()


def _status_failed(body: Any) -> bool:
    status = result_of(body).get("Status")
    return status is not None and str(status).strip().lower() in ("0", "false", "failure", "failed")


class HidroelectricaApi:
    """Client asincron pentru un cont iHidro."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._user_id: str | None = None
        self._session_token: str | None = None
        self._lock = asyncio.Lock()

    @property
    def user_id(self) -> str | None:
        return self._user_id

    # ------------------------------------------------------------ HTTP brut
    def _headers(self, authorization: str | None, authenticated: bool) -> dict[str, str]:
        headers = {
            "SourceType": "1" if authenticated else "0",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Host": API_HOST_HEADER,
            "User-Agent": API_USER_AGENT,
        }
        if authorization:
            headers["Authorization"] = authorization
        return headers

    async def _post(
        self, endpoint: str, payload: dict[str, Any], headers: dict[str, str]
    ) -> tuple[int, Any]:
        url = f"{API_BASE_URL}{endpoint}"
        try:
            async with self._session.post(
                url, json=payload, headers=headers, timeout=_TIMEOUT, allow_redirects=False
            ) as resp:
                status = resp.status
                if status in (301, 302, 303, 307, 308):
                    raise HidroelectricaConnectionError(
                        f"{endpoint}: serverul a redirecționat cererea (HTTP {status})"
                    )
                if status == 401:
                    return status, None
                text = await resp.text()
                if status >= 400:
                    raise HidroelectricaConnectionError(f"{endpoint}: HTTP {status}")
                try:
                    return status, json.loads(text) if text else None
                except ValueError as err:
                    raise HidroelectricaConnectionError(
                        f"{endpoint}: răspuns care nu e JSON"
                    ) from err
        except asyncio.TimeoutError as err:
            raise HidroelectricaConnectionError(f"{endpoint}: timeout") from err
        except aiohttp.ClientError as err:
            raise HidroelectricaConnectionError(f"{endpoint}: {err}") from err

    # ------------------------------------------------------- autentificare
    async def authenticate(self) -> None:
        """Login complet (GetId + ValidateUserLogin)."""
        async with self._lock:
            await self._login()

    async def _login(self) -> None:
        self._user_id = self._session_token = None
        _, body = await self._post(EP_GET_ID, {}, self._headers(None, False))
        data = data_of(body) or {}
        key, token_id = data.get("key"), data.get("tokenId")
        if not key or not token_id:
            raise HidroelectricaConnectionError("GetId nu a întors key/tokenId")

        now = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        payload = {
            "deviceType": "MobileApp",
            "OperatingSystem": "Android",
            "UpdatedDate": now,
            "Deviceid": "",
            "SessionCode": "",
            "LanguageCode": LANGUAGE,
            "password": self._password,
            "UserId": self._username,
            "TFADeviceid": "",
            "OSVersion": 14,
            "TimeOffSet": "120",
            "LUpdHideShow": now,
            "Browser": "NA",
        }
        status, body = await self._post(
            EP_VALIDATE_LOGIN, payload, self._headers(_basic(key, token_id), False)
        )
        if status == 401:
            raise HidroelectricaConnectionError("ValidateUserLogin: HTTP 401 la pre-autentificare")
        data = data_of(body)
        table = data.get("Table") if isinstance(data, dict) else None
        row = table[0] if isinstance(table, list) and table else {}
        user_id = str(row.get("UserID") or "").strip()
        token = str(row.get("SessionToken") or "").strip()
        if not user_id or not token:
            msg = _message(body) or "Utilizator sau parolă incorecte."
            raise HidroelectricaAuthError(msg)
        self._user_id, self._session_token = user_id, token
        _LOGGER.debug("Autentificat în iHidro (UserID=%s)", user_id)

    async def _ensure_login(self) -> None:
        if self._session_token:
            return
        async with self._lock:
            if not self._session_token:
                await self._login()

    async def _call(self, endpoint: str, payload_fn) -> Any:
        """Apel autentificat; la sesiune expirată se reautentifică o dată."""
        for attempt in (1, 2):
            await self._ensure_login()
            token_used = self._session_token
            status, body = await self._post(
                endpoint,
                payload_fn(),
                self._headers(_basic(self._user_id or "", token_used or ""), True),
            )
            expired = status == 401 or (
                _status_failed(body)
                and any(h in _message(body).lower() for h in _SESSION_HINTS)
            )
            if not expired:
                return body
            if attempt == 1:
                _LOGGER.debug("%s: sesiune expirată, reautentificare", endpoint)
                async with self._lock:
                    if self._session_token == token_used:
                        self._session_token = None
        raise HidroelectricaAuthError(f"{endpoint}: sesiunea nu a putut fi reînnoită")

    # ---------------------------------------------------------------- date
    async def get_accounts(self) -> list[dict[str, Any]]:
        """Conturile (locurile de consum) asociate utilizatorului."""
        body = await self._call(EP_USER_SETTING, lambda: {"UserID": self._user_id})
        data = data_of(body) or {}
        accounts: list[dict[str, Any]] = []
        seen: set[str] = set()
        if isinstance(data, dict):
            for table in ("Table1", "Table2"):
                for row in data.get(table) or []:
                    uan = str(row.get("UtilityAccountNumber") or "").strip()
                    if uan and uan not in seen:
                        seen.add(uan)
                        accounts.append(row)
        return accounts

    def _account_payload(self, uan: str, account_number: str, **extra: Any) -> dict[str, Any]:
        return {
            "UserID": self._user_id,
            "UtilityAccountNumber": uan,
            "AccountNumber": account_number,
            **extra,
        }

    async def get_bill(self, uan: str, account_number: str) -> Any:
        """Factura curentă + soldul de plată."""
        return await self._call(
            EP_BILL,
            lambda: self._account_payload(
                uan, account_number, LanguageCode=LANGUAGE, IsBillPDF="0"
            ),
        )

    async def get_billing_history(
        self, uan: str, account_number: str, start: date, end: date
    ) -> Any:
        """Istoric facturi + plăți (objBillingHistoryEntity / objBillingPaymentHistoryEntity)."""
        return await self._call(
            EP_BILLING_HISTORY,
            lambda: self._account_payload(
                uan,
                account_number,
                LanguageCode=LANGUAGE,
                FromDate=start.strftime("%m/%d/%Y"),
                ToDate=end.strftime("%m/%d/%Y"),
            ),
        )

    async def get_usage(self, uan: str, account_number: str) -> Any:
        """Consum lunar (objUsageGenerationResultSetTwo)."""
        return await self._call(
            EP_USAGE,
            lambda: self._account_payload(
                uan,
                account_number,
                date="",
                IsCSR=False,
                IsUSD=False,
                Mode="M",
                HourlyType="H",
                UsageType="e",
                UsageOrGeneration=False,
                GroupId=0,
                LanguageCode=LANGUAGE,
                Type="D",
                MeterNumber="",
                IsEnterpriseUser=False,
                SeasonType=0,
                DateFromDaily="",
                IsNetUsage=False,
                TimeOffset="120",
                UserType="Residential",
                DateToDaily="",
                UtilityId=0,
                IsLastTendays=False,
            ),
        )

    async def get_window_dates(self, uan: str, account_number: str) -> Any:
        """Perioada de transmitere a indexului."""
        return await self._call(
            EP_WINDOW_DATES,
            lambda: self._account_payload(uan, account_number, MeterType="E"),
        )

    async def get_pods(self, uan: str, account_number: str) -> Any:
        """Punctele de consum (POD, instalație, contor)."""
        return await self._call(
            EP_PODS,
            lambda: self._account_payload(uan, account_number, MeterType="E"),
        )
