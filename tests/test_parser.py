"""Teste pentru parser (fără Home Assistant)."""

from datetime import date

from custom_components.hidroelectrica_ro.parser import (
    Invoice,
    allocate_balance,
    month_of,
    parse_date,
    parse_usage,
    parse_window,
    to_float,
)


def test_parse_date_formats() -> None:
    assert parse_date("11/05/2026") == date(2026, 11, 5)  # MM/DD/YYYY
    assert parse_date("11/05/2026 00:00:00") == date(2026, 11, 5)
    assert parse_date("25/11/2026") == date(2026, 11, 25)  # DD/MM când ziua > 12
    assert parse_date("2026-11-05T00:00:00") == date(2026, 11, 5)
    assert parse_date("05.11.2026") == date(2026, 11, 5)
    assert parse_date("20261105") == date(2026, 11, 5)
    assert parse_date("") is None and parse_date("nimic") is None


def test_to_float() -> None:
    assert to_float("1.234,56") == 1234.56
    assert to_float("1,234.56") == 1234.56
    assert to_float("12,5") == 12.5
    assert to_float("180.00 RON") == 180.0
    assert to_float(None) is None and to_float("x") is None


def test_month_of() -> None:
    assert month_of("Ian") == 1 and month_of("Jan") == 1 and month_of("noiembrie") == 11
    assert month_of("7") == 7 and month_of(13) is None


def test_allocate_balance_credit_and_partial() -> None:
    inv = [
        Invoice("3", date(2026, 3, 1), None, 50.0),
        Invoice("2", date(2026, 2, 1), None, -20.0),
        Invoice("1", date(2026, 1, 1), None, 100.0),
        Invoice("0", date(2025, 12, 1), None, 100.0),
    ]
    allocate_balance(inv, 80.0)
    assert [(i.status, i.rest_plata) for i in inv] == [
        ("neplatita", 50.0), ("credit", 0.0), ("partial_platita", 30.0), ("platita", 0.0),
    ]


def test_parse_usage_numeric_months_and_dates() -> None:
    body = {"result": {"Data": {"objUsageGenerationResultSetTwo": [
        {"Month": "2", "Year": "2026", "value": 10},
        {"UsageDate": "01/01/2026", "value": "5"},
        {"Month": "x", "Year": "2026", "value": 1},  # ignorat
    ]}}}
    entries = parse_usage(body)
    assert [(e.an, e.luna_nr, e.kwh) for e in entries] == [(2026, 1, 5.0), (2026, 2, 10.0)]


def test_parse_window_day_numbers_and_next() -> None:
    today = date(2026, 11, 25)
    body = {"result": {"Data": {"OpeningDate": "20", "ClosingDate": "27"}}}
    w = parse_window(body, today)
    assert (w.start, w.end) == (date(2026, 11, 20), date(2026, 11, 27))
    body = {"result": {"Data": {
        "Is_Window_Open": "0",
        "OpeningDate": "10/20/2026", "ClosingDate": "10/27/2026",
        "NextMonthOpeningDate": "12/20/2026", "NextMonthClosingDate": "12/27/2026",
    }}}
    w = parse_window(body, today)
    assert (w.start, w.end, w.is_open) == (date(2026, 12, 20), date(2026, 12, 27), False)
    assert w.label == "20.12.2026 - 27.12.2026"


def test_invoice_number_skips_encrypted_id() -> None:
    from custom_components.hidroelectrica_ro.parser import invoice_number

    enc = "Vrem+jy3ZmwyoeSwCMMGsNFf+bPL8nFpH1TzqilfYQ=="
    assert invoice_number({"invoiceId": enc, "exbel": "0012345678"}) == "12345678"
    assert invoice_number({"invoiceId": enc, "InvoiceNumber": "HE 1234"}) == "HE 1234"
    assert invoice_number({"invoiceId": enc}) == "—"
    assert invoice_number({"invoiceId": "998877"}) == "998877"
