"""Fixtures pentru testele integrării Hidroelectrica.

Răspunsurile imită structura API-ului SEW folosit de aplicația iHidro
({"result": {"Status": 1, "Data": ...}}), cu date fictive.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

UAN = "8000123456"
ACCOUNT_NO = "1000987654"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def us(d: date) -> str:
    """Format MM/DD/YYYY, ca în API."""
    return d.strftime("%m/%d/%Y")


def sample_raw():
    t = date.today()
    y = t.year
    return {
        "accounts": [{
            "UtilityAccountNumber": UAN, "AccountNumber": ACCOUNT_NO,
            "Address": "Str. Test 1, Iasi", "Pod": "RO003E000000001",
            "IsDefaultAccount": True,
        }],
        "bill": {"result": {
            "billamount": "150.00", "rembalance": "180.00",
            "duedate": us(t + timedelta(days=10)), "invoicenumber": "H0003",
        }},
        "history": {"result": {
            "objBillingHistoryEntity": [
                {"invoiceId": "H0001", "invoiceDate": f"09/05/{y - 1}", "dueDate": f"09/25/{y - 1}",
                 "amount": "120.00", "billPeriod": "08/2025"},
                {"invoiceId": "H0002", "invoiceDate": us(t - timedelta(days=40)),
                 "dueDate": us(t - timedelta(days=2)), "amount": "100.00"},
                {"invoiceId": "H0003", "invoiceDate": us(t - timedelta(days=5)),
                 "dueDate": us(t + timedelta(days=10)), "amount": "150.00"},
            ],
            "objBillingPaymentHistoryEntity": [
                {"amount": "120.00", "paymentDate": f"09/20/{y - 1}", "channel": "Card"},
                {"amount": "70.00", "paymentDate": us(t - timedelta(days=3)), "channel": "Banca"},
            ],
        }},
        "usage": {"result": {"Status": 1, "Data": {
            "objUsageGenerationResultSetTwo": [
                {"Month": "Sep", "Year": str(y - 1), "value": "200", "UsageValue": "130.5"},
                {"Month": "Oct", "Year": str(y), "value": "210.4", "UsageValue": "140"},
                {"Month": "Nov", "Year": str(y), "value": "245", "UsageValue": "160"},
            ],
        }}},
        "window": {"result": {"Status": 1, "Data": {
            "Is_Window_Open": "1",
            "OpeningDate": us(t - timedelta(days=2)),
            "ClosingDate": us(t + timedelta(days=3)),
        }}},
        "pods": {"result": {"Status": 1, "Data": [
            {"pod": "RO003E000000001", "installation": "4000111", "distributor": "DEER"},
        ]}},
    }


@pytest.fixture
def mock_api():
    raw = sample_raw()
    with patch(
        "custom_components.hidroelectrica_ro.HidroelectricaApi", autospec=True
    ) as api_cls, patch(
        "custom_components.hidroelectrica_ro.config_flow.HidroelectricaApi", new=api_cls
    ):
        api = api_cls.return_value
        api.authenticate = AsyncMock()
        api.get_accounts = AsyncMock(return_value=raw["accounts"])
        api.get_bill = AsyncMock(return_value=raw["bill"])
        api.get_billing_history = AsyncMock(return_value=raw["history"])
        api.get_usage = AsyncMock(return_value=raw["usage"])
        api.get_window_dates = AsyncMock(return_value=raw["window"])
        api.get_pods = AsyncMock(return_value=raw["pods"])
        yield api
