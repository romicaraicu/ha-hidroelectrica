#!/usr/bin/env python3
"""Testează conexiunea la iHidro (Hidroelectrica) fără Home Assistant.

Utilizare:
    python3 -m venv .venv && .venv/bin/pip install aiohttp
    .venv/bin/python tools/test_connection.py            # cere utilizator + parolă
    .venv/bin/python tools/test_connection.py --dump out  # salvează JSON-urile brute
    .venv/bin/python tools/test_connection.py --exemplu   # doar exemplul de factură (mascat)
    .venv/bin/python tools/test_connection.py --facturi   # diagnostic facturi plătite / neplătite

Datele salvate cu --dump conțin informații personale (adresă, POD, cont).
Nu le publica; pentru depanare trimite doar secțiunea "Structura răspunsurilor".
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
import getpass
import json
import os
import re
import sys
import types
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "hidroelectrica_ro"

# Încărcăm doar api.py + parser.py + const.py, fără __init__.py (care cere Home Assistant).
_pkg = types.ModuleType("hidroelectrica")
_pkg.__path__ = [str(PKG_DIR)]
sys.modules["hidroelectrica"] = _pkg

import aiohttp  # noqa: E402

from hidroelectrica.api import HidroelectricaApi, HidroelectricaError  # noqa: E402
from hidroelectrica.const import HISTORY_YEARS  # noqa: E402
from hidroelectrica.parser import (  # noqa: E402
    account_id,
    build_account_data,
    find_list,
    find_record,
)


def _shape(value, depth=0):
    """Structura unui JSON (chei + tipuri), fără valori personale."""
    if isinstance(value, dict):
        return {k: _shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1), f"x{len(value)}"] if value else []
    return type(value).__name__


def _log(message):
    """Mesaje de progres și erori pe stderr: se văd și când ieșirea e redirecționată."""
    print(message, file=sys.stderr, flush=True)


def _ask(prompt):
    print(prompt, end="", file=sys.stderr, flush=True)
    return input()


def _mask(value):
    """Forma unei valori fără conținut: cifre -> 9, litere -> a/A."""
    if value is None or isinstance(value, (bool, int, float)):
        return value if not isinstance(value, (int, float)) or isinstance(value, bool) else type(value).__name__
    return "".join("9" if c.isdigit() else ("A" if c.isupper() else "a") if c.isalpha() else c for c in str(value))


_AMOUNT_RE = re.compile(r"^-?\d{1,7}([.,]\d{1,4})?$")
_DATE_RE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})")
_WORD_RE = re.compile(r"^[A-Za-zĂÂÎȘȚăâîșț _-]{1,20}$")


def _visible(value):
    """Arată sume, date, valori logice și cuvinte scurte (statusuri);
    maschează restul (identificatori, numere de cont, texte lungi)."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value).strip()
    if _DATE_RE.match(text) or _WORD_RE.match(text):
        return text
    if _AMOUNT_RE.match(text) and not (text.isdigit() and len(text) >= 6):
        return text
    return _mask(text)


def _print_invoices(data, uan, label):
    """Diagnostic: ce trimite serverul pentru fiecare factură și ce deduce integrarea."""
    acc = build_account_data(uan, data)
    bill = find_record(data.get("bill"), "rembalance", "billamount", "duedate", "invoicenumber")
    bills = find_list(data.get("history"), "objBillingHistoryEntity", "BillingHistory")
    pays = find_list(data.get("history"), "objBillingPaymentHistoryEntity", "PaymentHistory")
    print(f"--- {label}")
    print("GetBill:", json.dumps({k: _visible(v) for k, v in bill.items()}, ensure_ascii=False))
    print(f"\nFacturi în istoric: {len(bills)}  (cea mai nouă prima)")
    by_raw = {id(i.raw): i for i in acc.invoices}
    for row in sorted(bills, key=lambda r: by_raw[id(r)].data_emitere or date.min, reverse=True):
        inv = by_raw[id(row)]
        extra = {k: _visible(v) for k, v in row.items() if k != "invoiceId"}
        print(
            f"  {inv.data_emitere} | scadență {inv.scadenta} | {inv.valoare:>9.2f} lei"
            f" | integrare: {inv.status} (rest {inv.rest_plata:.2f})"
            f" | server: {json.dumps(extra, ensure_ascii=False)}"
        )
    print(f"\nPlăți în istoric: {len(pays)}")
    for p in acc.payments:
        print(f"  {p['data']} | {p['suma']} lei | {p['canal']}")
    total_inv = sum(i.valoare for i in acc.invoices)
    total_pay = sum(p["suma"] or 0 for p in acc.payments)
    print(
        f"\nTotal facturat: {total_inv:.2f} | total plătit: {total_pay:.2f}"
        f" | diferență: {total_inv - total_pay:.2f} | sold server (rembalance): {acc.balance}"
    )


async def _safe(label, coro):
    try:
        return await coro
    except HidroelectricaError as err:
        _log(f"  ! {label}: {err}")
        return None


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", help="director în care se salvează JSON-urile brute")
    parser.add_argument(
        "--exemplu", action="store_true",
        help="afișează doar exemplul de factură și plată (valori mascate)",
    )
    parser.add_argument(
        "--facturi", action="store_true",
        help="diagnostic facturi: sume, date și statusul calculat (identificatorii sunt mascați)",
    )
    args = parser.parse_args()

    username = os.environ.get("IHIDRO_USER") or _ask("Utilizator iHidro: ")
    password = os.environ.get("IHIDRO_PASSWORD") or getpass.getpass("Parolă: ", stream=sys.stderr)

    raw: dict[str, dict] = {}
    async with aiohttp.ClientSession() as session:
        api = HidroelectricaApi(session, username, password)
        try:
            _log("→ Autentificare...")
            await api.authenticate()
            _log("✓ Autentificat")
            accounts = await api.get_accounts()
            _log(f"✓ {len(accounts)} loc(uri) de consum")
        except HidroelectricaError as err:
            _log(f"✗ {type(err).__name__}: {err}")
            return 1
        today = date.today()
        start = date(today.year - HISTORY_YEARS + 1, 1, 1)
        for acc in accounts:
            uan = account_id(acc)
            number = str(acc.get("AccountNumber") or "")
            _log(f"→ Date pentru contul …{uan[-4:]}")
            raw[uan] = {
                "account": acc,
                "bill": await _safe("GetBill", api.get_bill(uan, number)),
                "history": await _safe("GetBillingHistoryList", api.get_billing_history(uan, number, start, today)),
                "usage": await _safe("GetUsageGeneration", api.get_usage(uan, number)),
                "window": await _safe("GetWindowDates", api.get_window_dates(uan, number)),
                "pods": await _safe("GetPods", api.get_pods(uan, number)),
            }

    if args.facturi:
        print("\n=== Diagnostic facturi (sume și date reale; identificatorii mascați) ===")
        for i, (uan, data) in enumerate(raw.items()):
            _print_invoices(data, uan, f"cont {i + 1}")
        return 0

    if not args.exemplu:
        print("\n=== Structura răspunsurilor (fără valori) ===")
        for i, data in enumerate(raw.values()):
            print(f"--- cont {i + 1}")
            print(json.dumps({k: _shape(v) for k, v in data.items()}, indent=2, ensure_ascii=False))

    print("\n=== Exemplu factură și plată (valori mascate: 9 = cifră, a/A = literă) ===")
    for i, data in enumerate(raw.values()):
        bills = find_list(data.get("history"), "objBillingHistoryEntity", "BillingHistory")
        pays = find_list(data.get("history"), "objBillingPaymentHistoryEntity", "PaymentHistory")
        print(f"--- cont {i + 1}")
        print(json.dumps({
            "factura": {k: _mask(v) for k, v in (bills[0] if bills else {}).items()},
            "plata": {k: _mask(v) for k, v in (pays[0] if pays else {}).items()},
        }, indent=2, ensure_ascii=False))

    if args.exemplu:
        return 0

    print("\n=== Ce va vedea Home Assistant ===")
    for uan, data in raw.items():
        print(json.dumps(build_account_data(uan, data).summary(), indent=2, ensure_ascii=False, default=str))

    if args.dump:
        out = Path(args.dump)
        out.mkdir(parents=True, exist_ok=True)
        for i, data in enumerate(raw.values()):
            (out / f"cont_{i + 1}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\nJSON-uri brute salvate în {out.resolve()} (conțin date personale!)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
