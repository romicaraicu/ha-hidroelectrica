"""Teste pentru parser (fără Home Assistant)."""

from datetime import date

from custom_components.hidroelectrica_ro.parser import (
    Invoice,
    allocate_balance,
    build_account_data,
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


def _history(*rows):
    return {"result": {"objBillingHistoryEntity": [
        {"invoiceId": "Xx+Yy==", "invoiceDate": d, "dueDate": due, "amount": a}
        for d, due, a in rows
    ]}}


def test_current_bill_missing_from_history_takes_the_balance() -> None:
    """Caz real: sold 307.21 = o singură factură nouă, care nu e încă în istoric.
    Fără factura curentă, soldul ajungea pe facturi deja plătite."""
    raw = {
        "bill": {"result": {"billamount": "307.21", "rembalance": "307.21",
                            "duedate": "12/15/2026"}},
        "history": _history(
            ("10/20/2026", "11/10/2026", "134.36"),
            ("09/20/2026", "10/10/2026", "250.00"),
        ),
    }
    acc = build_account_data("8001", raw)
    assert [(i.valoare, i.status, i.rest_plata) for i in acc.invoices] == [
        (307.21, "neplatita", 307.21), (134.36, "platita", 0.0), (250.0, "platita", 0.0),
    ]
    assert acc.invoices[0].scadenta == date(2026, 12, 15)
    assert len(acc.unpaid_invoices) == 1 and acc.total_balance == 307.21


def test_current_bill_already_in_history_is_not_duplicated() -> None:
    raw = {
        "bill": {"result": {"billamount": "307.21", "rembalance": "307.21",
                            "duedate": "12/15/2026"}},
        "history": _history(
            ("11/25/2026", "12/15/2026", "307.21"),
            ("10/20/2026", "11/10/2026", "134.36"),
        ),
    }
    acc = build_account_data("8001", raw)
    assert [(i.valoare, i.status) for i in acc.invoices] == [
        (307.21, "neplatita"), (134.36, "platita"),
    ]


def test_zero_current_bill_is_ignored() -> None:
    raw = {
        "bill": {"result": {"billamount": "0", "rembalance": "0"}},
        "history": _history(("10/20/2026", "11/10/2026", "134.36")),
    }
    acc = build_account_data("8001", raw)
    assert len(acc.invoices) == 1 and acc.invoices[0].status == "platita"


def test_prices_skip_months_without_cost_and_fall_back_to_invoices() -> None:
    raw = {
        "usage": {"result": {"Data": {"objUsageGenerationResultSetTwo": [
            {"Month": "Jan", "Year": "2026", "value": "100", "UsageValue": "80"},
            {"Month": "Feb", "Year": "2026", "value": "300"},  # fără cost: ignorată
            {"Month": "Mar", "Year": "2026", "value": "100", "UsageValue": "100"},
            {"Month": "Dec", "Year": "2025", "value": "200"},  # 2025 fără costuri lunare
        ]}}},
        "history": _history(("12/10/2025", "12/30/2025", "250.00")),
    }
    acc = build_account_data("8001", raw)
    assert acc.last_price.luna == "martie 2026" and acc.last_price.lei_pe_kwh == 1.0
    prices = acc.yearly_prices()
    assert prices["2026"] == {"kwh": 200.0, "lei": 180.0, "luni": 2, "lei_pe_kwh": 0.9, "sursa": "consum"}
    assert prices["2025"] == {"kwh": 200.0, "lei": 250.0, "luni": None, "lei_pe_kwh": 1.25, "sursa": "facturi"}
    assert list(prices) == ["2026", "2025"]


def test_no_usage_cost_means_no_price() -> None:
    raw = {"usage": {"result": {"Data": {"objUsageGenerationResultSetTwo": [
        {"Month": "Jan", "Year": "2026", "value": "100"},
    ]}}}}
    acc = build_account_data("8001", raw)
    assert acc.last_price is None and acc.yearly_prices() == {}
    assert acc.consumption[0].as_attr()["lei_pe_kwh"] is None
