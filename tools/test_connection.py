#!/usr/bin/env python3
"""Testează conexiunea la iHidro (Hidroelectrica) fără Home Assistant.

Utilizare:
    python3 -m venv .venv && .venv/bin/pip install aiohttp
    .venv/bin/python tools/test_connection.py            # cere utilizator + parolă
    .venv/bin/python tools/test_connection.py --dump out  # salvează JSON-urile brute

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
from hidroelectrica.parser import account_id, build_account_data, find_list  # noqa: E402


def _shape(value, depth=0):
    """Structura unui JSON (chei + tipuri), fără valori personale."""
    if isinstance(value, dict):
        return {k: _shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1), f"x{len(value)}"] if value else []
    return type(value).__name__


def _mask(value):
    """Forma unei valori fără conținut: cifre -> 9, litere -> a/A."""
    if value is None or isinstance(value, (bool, int, float)):
        return value if not isinstance(value, (int, float)) or isinstance(value, bool) else type(value).__name__
    return "".join("9" if c.isdigit() else ("A" if c.isupper() else "a") if c.isalpha() else c for c in str(value))


async def _safe(label, coro):
    try:
        return await coro
    except HidroelectricaError as err:
        print(f"  ! {label}: {err}")
        return None


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", help="director în care se salvează JSON-urile brute")
    args = parser.parse_args()

    username = os.environ.get("IHIDRO_USER") or input("Utilizator iHidro: ")
    password = os.environ.get("IHIDRO_PASSWORD") or getpass.getpass("Parolă: ")

    raw: dict[str, dict] = {}
    async with aiohttp.ClientSession() as session:
        api = HidroelectricaApi(session, username, password)
        try:
            print("→ Autentificare...")
            await api.authenticate()
            print("✓ Autentificat")
            accounts = await api.get_accounts()
            print(f"✓ {len(accounts)} loc(uri) de consum")
        except HidroelectricaError as err:
            print(f"✗ {type(err).__name__}: {err}")
            return 1
        today = date.today()
        start = date(today.year - HISTORY_YEARS + 1, 1, 1)
        for acc in accounts:
            uan = account_id(acc)
            number = str(acc.get("AccountNumber") or "")
            print(f"→ Date pentru contul …{uan[-4:]}")
            raw[uan] = {
                "account": acc,
                "bill": await _safe("GetBill", api.get_bill(uan, number)),
                "history": await _safe("GetBillingHistoryList", api.get_billing_history(uan, number, start, today)),
                "usage": await _safe("GetUsageGeneration", api.get_usage(uan, number)),
                "window": await _safe("GetWindowDates", api.get_window_dates(uan, number)),
                "pods": await _safe("GetPods", api.get_pods(uan, number)),
            }

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
