"""Teste pentru clientul API (sesiune HTTP simulată)."""

import json

import pytest

from custom_components.hidroelectrica.api import (
    HidroelectricaApi,
    HidroelectricaAuthError,
    HidroelectricaConnectionError,
)


class FakeResp:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def text(self):
        return json.dumps(self._body) if not isinstance(self._body, str) else self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Răspunde pe baza endpoint-ului; reține cererile."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def post(self, url, json=None, headers=None, **kwargs):
        endpoint = url.split("ihidro.ro", 1)[1]
        self.calls.append((endpoint, json, headers))
        handler = self.routes[endpoint]
        status, body = handler(json, headers) if callable(handler) else handler
        return FakeResp(status, body)


GET_ID = (200, {"result": {"Status": 1, "Data": {"key": "k", "tokenId": "t"}}})


def login_ok(token="S1"):
    return (200, {"result": {"Status": 1, "Data": {"Table": [
        {"UserID": "42", "SessionToken": token}]}}})


async def test_login_and_accounts() -> None:
    session = FakeSession({
        "/API/UserLogin/GetId": GET_ID,
        "/API/UserLogin/ValidateUserLogin": login_ok(),
        "/API/UserLogin/GetUserSetting": (200, {"result": {"Data": {
            "Table1": [{"UtilityAccountNumber": "8001", "AccountNumber": "1"}],
            "Table2": [{"UtilityAccountNumber": "8001"}, {"UtilityAccountNumber": "8002"}],
        }}}),
    })
    api = HidroelectricaApi(session, "user", "pass")
    accounts = await api.get_accounts()
    assert [a["UtilityAccountNumber"] for a in accounts] == ["8001", "8002"]
    endpoint, payload, headers = session.calls[1]
    assert payload["UserId"] == "user" and payload["password"] == "pass"
    assert headers["SourceType"] == "0" and headers["Authorization"].startswith("Basic ")
    _, payload, headers = session.calls[2]
    assert payload == {"UserID": "42"} and headers["SourceType"] == "1"


async def test_invalid_credentials() -> None:
    session = FakeSession({
        "/API/UserLogin/GetId": GET_ID,
        "/API/UserLogin/ValidateUserLogin": (200, {"result": {
            "Status": 0, "Message": "Nume de utilizator sau parola incorecte", "Data": {"Table": []}}}),
    })
    with pytest.raises(HidroelectricaAuthError, match="incorecte"):
        await HidroelectricaApi(session, "u", "p").authenticate()


async def test_relogin_on_401() -> None:
    tokens = iter(["S1", "S2"])
    state = {"bill_calls": 0}

    def bill(payload, headers):
        state["bill_calls"] += 1
        return (401, None) if state["bill_calls"] == 1 else (200, {"result": {"rembalance": "1"}})

    session = FakeSession({
        "/API/UserLogin/GetId": GET_ID,
        "/API/UserLogin/ValidateUserLogin": lambda p, h: login_ok(next(tokens)),
        "/Service/Billing/GetBill": bill,
    })
    body = await HidroelectricaApi(session, "u", "p").get_bill("8001", "1")
    assert body == {"result": {"rembalance": "1"}}
    logins = [c for c in session.calls if c[0].endswith("ValidateUserLogin")]
    assert len(logins) == 2


async def test_redirect_is_connection_error() -> None:
    session = FakeSession({"/API/UserLogin/GetId": (302, "")})
    with pytest.raises(HidroelectricaConnectionError):
        await HidroelectricaApi(session, "u", "p").authenticate()
