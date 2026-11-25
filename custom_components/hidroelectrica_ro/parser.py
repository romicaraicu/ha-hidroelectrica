"""Transformă răspunsurile brute ale API-ului iHidro în date per cont.

Un "cont" = un loc de consum (UtilityAccountNumber). Modulul nu depinde de
Home Assistant (testabil cu tools/test_connection.py).

API-ul nu spune pentru fiecare factură dacă e plătită; dă doar soldul total
de plată (`rembalance`). Ca în portal, soldul se atribuie facturilor începând
cu cea mai nouă: facturile acoperite de sold sunt neplătite, restul plătite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import re
from typing import Any

from .const import AMOUNT_EPSILON

STATUS_PAID = "platita"
STATUS_PARTIAL = "partial_platita"
STATUS_UNPAID = "neplatita"
STATUS_CREDIT = "credit"

STATUS_LABELS = {
    STATUS_PAID: "Plătită",
    STATUS_PARTIAL: "Parțial plătită",
    STATUS_UNPAID: "Neplătită",
    STATUS_CREDIT: "Credit",
}

LUNI = [
    "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
]
_MONTH_PREFIX = {
    "ian": 1, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mai": 5, "may": 5,
    "iun": 6, "jun": 6, "iul": 7, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
    "noi": 11, "nov": 11, "dec": 12,
}


# ----------------------------------------------------------------- utilitare
def to_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace("RON", "").replace("lei", "")
    if "," in text and "." in text:  # 1.234,56 sau 1,234.56
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(value: Any) -> date | None:
    """Acceptă MM/DD/YYYY [HH:MM:SS] (formatul API-ului SEW), ISO,
    dd.mm.yyyy, yyyymmdd și /Date(ms)/."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if text.startswith("/Date("):
        try:
            return datetime.fromtimestamp(int(text[6:].split(")")[0][:13]) / 1000).date()
        except ValueError:
            return None
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        a, b, year = (int(g) for g in match.groups())
        # API-ul SEW folosește MM/DD/YYYY; dacă prima parte > 12 e DD/MM/YYYY.
        month, day = (b, a) if a > 12 else (a, b)
        try:
            return date(year, month, day)
        except ValueError:
            return None
    for fmt, size in (("%Y-%m-%d", 10), ("%d.%m.%Y", 10), ("%Y%m%d", 8)):
        try:
            return datetime.strptime(text[:size], fmt).date()
        except ValueError:
            continue
    return None


def fmt_date(value: date | None) -> str | None:
    return value.strftime("%d.%m.%Y") if value else None


def iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _first(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if item.get(key) not in (None, ""):
            return item[key]
    return None


def _containers(body: Any) -> list[dict[str, Any]]:
    """Locurile unde pot apărea datele: result și result.Data."""
    out: list[dict[str, Any]] = []
    result = body.get("result") if isinstance(body, dict) else None
    if isinstance(result, dict):
        out.append(result)
        data = result.get("Data")
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            out.append(data[0])
    return out


def find_list(body: Any, *keys: str) -> list[dict[str, Any]]:
    for container in _containers(body):
        for key in keys:
            value = container.get(key)
            if isinstance(value, list):
                return [v for v in value if isinstance(v, dict)]
    return []


def find_record(body: Any, *required_any: str) -> dict[str, Any]:
    """Primul dict din result / result.Data care conține una din chei."""
    for container in _containers(body):
        if any(container.get(k) not in (None, "") for k in required_any):
            return container
    result = body.get("result") if isinstance(body, dict) else None
    data = result.get("Data") if isinstance(result, dict) else None
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and any(row.get(k) not in (None, "") for k in required_any):
                return row
    return {}


def data_list(body: Any) -> list[dict[str, Any]]:
    result = body.get("result") if isinstance(body, dict) else None
    data = result.get("Data") if isinstance(result, dict) else None
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        for key in ("Table", "Table1", "pods", "Pods"):
            if isinstance(data.get(key), list):
                return [d for d in data[key] if isinstance(d, dict)]
    return []


def month_of(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value) if 1 <= int(value) <= 12 else None
    text = str(value).strip().lower()
    if text.isdigit():
        number = int(text)
        return number if 1 <= number <= 12 else None
    return _MONTH_PREFIX.get(text[:3])


# ------------------------------------------------------------------ facturi
@dataclass
class Invoice:
    numar: str
    data_emitere: date | None
    scadenta: date | None
    valoare: float
    rest_plata: float = 0.0
    status: str = STATUS_PAID
    perioada: str | None = None
    tip: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def restanta(self) -> bool:
        return (
            self.status in (STATUS_UNPAID, STATUS_PARTIAL)
            and self.scadenta is not None
            and self.scadenta < date.today()
        )

    def as_attr(self) -> dict[str, Any]:
        return {
            "numar": self.numar,
            "data_emitere": iso(self.data_emitere),
            "scadenta": iso(self.scadenta),
            "valoare": round(self.valoare, 2),
            "rest_plata": round(self.rest_plata, 2),
            "status": STATUS_LABELS[self.status],
            "restanta": self.restanta,
            "perioada": self.perioada,
        }


# Câmpurile în care poate fi numărul facturii, în ordinea preferinței.
# `invoiceId` e de obicei un identificator criptat (base64), folosit intern de
# aplicație (ex. pentru PDF), deci e luat doar dacă arată ca un număr.
_INVOICE_NUMBER_KEYS = (
    "invoiceNumber", "InvoiceNumber", "invoicenumber", "invoiceNo", "InvoiceNo",
    "exbel", "Exbel", "EXBEL", "billNumber", "BillNumber", "documentNumber",
    "DocumentNumber", "opbel", "OPBEL", "invoiceId", "InvoiceId",
)
_READABLE_NUMBER = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._/-]{0,23}")


def invoice_number(item: dict[str, Any]) -> str:
    """Numărul facturii, ca pe factura tipărită; „—” dacă nu există unul lizibil."""
    for key in _INVOICE_NUMBER_KEYS:
        value = item.get(key)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if _READABLE_NUMBER.fullmatch(text) and any(ch.isdigit() for ch in text):
            return text.lstrip("0") or text
    return "—"


def _invoice(item: dict[str, Any]) -> Invoice:
    return Invoice(
        numar=invoice_number(item),
        data_emitere=parse_date(_first(item, "invoiceDate", "InvoiceDate", "BillDate", "billDate")),
        scadenta=parse_date(_first(item, "dueDate", "DueDate", "duedate")),
        valoare=to_float(_first(item, "amount", "Amount", "billamount", "BillAmount")) or 0.0,
        perioada=_first(item, "billPeriod", "BillPeriod"),
        tip=_first(item, "invoiceType", "InvoiceType"),
        raw=item,
    )


def allocate_balance(invoices: list[Invoice], balance: float | None) -> None:
    """Atribuie soldul de plată facturilor, de la cea mai nouă spre cea mai veche.

    `invoices` trebuie să fie sortate descrescător după data emiterii.
    """
    remaining = max(balance or 0.0, 0.0)
    for inv in invoices:
        if inv.valoare < -AMOUNT_EPSILON:
            inv.status, inv.rest_plata = STATUS_CREDIT, 0.0
            continue
        if remaining <= AMOUNT_EPSILON or inv.valoare <= AMOUNT_EPSILON:
            inv.status, inv.rest_plata = STATUS_PAID, 0.0
            continue
        owed = min(inv.valoare, remaining)
        remaining -= owed
        inv.rest_plata = round(owed, 2)
        inv.status = STATUS_UNPAID if inv.valoare - owed <= AMOUNT_EPSILON else STATUS_PARTIAL


# ------------------------------------------------------------------- consum
@dataclass
class ConsumptionEntry:
    an: int
    luna_nr: int
    kwh: float
    lei: float | None = None

    @property
    def luna(self) -> str:
        return f"{LUNI[self.luna_nr - 1]} {self.an}"

    @property
    def data(self) -> date:
        return date(self.an, self.luna_nr, 1)

    def as_attr(self) -> dict[str, Any]:
        return {
            "luna": self.luna,
            "data": iso(self.data),
            "kwh": round(self.kwh, 2),
            "lei": round(self.lei, 2) if self.lei is not None else None,
        }


def parse_usage(body: Any) -> list[ConsumptionEntry]:
    rows = find_list(body, "objUsageGenerationResultSetTwo")
    by_month: dict[tuple[int, int], ConsumptionEntry] = {}
    for row in rows:
        year = month = None
        when = parse_date(_first(row, "UsageDate", "Date", "date", "ReadDate"))
        if when:
            year, month = when.year, when.month
        month = month_of(_first(row, "Month", "month", "MonthName")) or month
        year_raw = _first(row, "Year", "year")
        if year_raw not in (None, "") and str(year_raw).strip().isdigit():
            year = int(str(year_raw).strip())
        kwh = to_float(_first(row, "value", "Value", "Usage", "kWh", "TotalUsage"))
        if not year or not month or kwh is None:
            continue
        by_month[(year, month)] = ConsumptionEntry(
            an=year, luna_nr=month, kwh=kwh, lei=to_float(_first(row, "UsageValue", "Cost"))
        )
    return [by_month[k] for k in sorted(by_month)]


# ------------------------------------------------------------- index window
def _window_date(value: Any, today: date) -> date | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.isdigit() and len(text) <= 2:  # doar ziua din lună
        try:
            return today.replace(day=int(text))
        except ValueError:
            return None
    return parse_date(text)


@dataclass
class ReadingWindow:
    start: date | None = None
    end: date | None = None
    open_flag: bool | None = None

    @property
    def is_open(self) -> bool:
        if self.open_flag is not None:
            return self.open_flag
        today = date.today()
        return bool(self.start and self.end and self.start <= today <= self.end)

    @property
    def label(self) -> str:
        start, end = fmt_date(self.start), fmt_date(self.end)
        if start and end:
            return f"{start} - {end}"
        return start or end or "Perioadă indisponibilă"


def parse_window(body: Any, today: date | None = None) -> ReadingWindow:
    today = today or date.today()
    row = find_record(
        body, "OpeningDate", "ClosingDate", "NextMonthOpeningDate", "Is_Window_Open",
        "WindowStartDate", "StartDate",
    )
    if not row:
        return ReadingWindow()
    current = (
        _window_date(_first(row, "OpeningDate", "WindowStartDate", "StartDate"), today),
        _window_date(_first(row, "ClosingDate", "WindowEndDate", "EndDate"), today),
    )
    upcoming = (
        _window_date(row.get("NextMonthOpeningDate"), today),
        _window_date(row.get("NextMonthClosingDate"), today),
    )
    flag_raw = row.get("Is_Window_Open")
    flag = None
    if flag_raw not in (None, ""):
        flag = str(flag_raw).strip().lower() in ("1", "true", "y", "da", "yes")

    def contains(w: tuple[date | None, date | None]) -> bool:
        return bool(w[0] and w[1] and w[0] <= today <= w[1])

    if contains(current) or (flag and current[0]):
        chosen = current
    elif contains(upcoming):
        chosen = upcoming
    elif upcoming[0] and upcoming[0] > today:
        chosen = upcoming
    elif current[0] and current[0] > today:
        chosen = current
    else:
        chosen = upcoming if upcoming[0] else current
    return ReadingWindow(start=chosen[0], end=chosen[1], open_flag=flag)


# --------------------------------------------------------------- rezultat
@dataclass
class AccountData:
    uan: str
    account: dict[str, Any]
    pod_info: dict[str, Any]
    invoices: list[Invoice]
    payments: list[dict[str, Any]]
    consumption: list[ConsumptionEntry]
    window: ReadingWindow
    bill: dict[str, Any]
    balance: float | None

    # -- loc de consum
    @property
    def account_number(self) -> str:
        return str(self.account.get("AccountNumber") or "").strip()

    @property
    def address(self) -> str:
        return str(_first(self.account, "Address", "address", "ServiceAddress") or self.uan).strip()

    @property
    def pod(self) -> str | None:
        value = _first(self.pod_info, "pod", "POD", "Pod", "podValue", "PODValue") or _first(
            self.account, "Pod", "POD", "pod"
        )
        return str(value).strip() if value else None

    @property
    def installation(self) -> str | None:
        value = _first(self.pod_info, "installation", "Installation", "InstallationNumber")
        return str(value).strip() if value else None

    @property
    def meter(self) -> str | None:
        value = _first(self.pod_info, "serialNumber", "SerialNumber", "MeterNumber", "equipmentNo") or _first(
            self.account, "EquipmentNo", "MeterNumber"
        )
        return str(value).strip() if value else None

    @property
    def distributor(self) -> str | None:
        value = _first(self.pod_info, "distributor", "Distributor")
        return str(value).strip() if value else None

    # -- facturi
    @property
    def unpaid_invoices(self) -> list[Invoice]:
        return [i for i in self.invoices if i.status in (STATUS_UNPAID, STATUS_PARTIAL)]

    @property
    def paid_invoices(self) -> list[Invoice]:
        return [i for i in self.invoices if i.status == STATUS_PAID]

    @property
    def latest_invoice(self) -> Invoice | None:
        return self.invoices[0] if self.invoices else None

    @property
    def total_balance(self) -> float | None:
        if self.balance is not None:
            return round(self.balance, 2)
        if self.invoices:
            return 0.0
        return None

    @property
    def overdue_amount(self) -> float:
        return round(sum(i.rest_plata for i in self.unpaid_invoices if i.restanta), 2)

    @property
    def next_due_date(self) -> date | None:
        today = date.today()
        dates = [i.scadenta for i in self.unpaid_invoices if i.scadenta and i.scadenta >= today]
        if dates:
            return min(dates)
        due = parse_date(_first(self.bill, "duedate", "DueDate", "dueDate"))
        if due and due >= today and (self.balance or 0) > AMOUNT_EPSILON:
            return due
        return None

    # -- plăți
    @property
    def last_payment(self) -> dict[str, Any] | None:
        return self.payments[0] if self.payments else None

    # -- consum
    @property
    def last_consumption(self) -> ConsumptionEntry | None:
        return self.consumption[-1] if self.consumption else None

    def yearly_consumption(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for entry in self.consumption:
            key = str(entry.an)
            totals[key] = round(totals.get(key, 0.0) + entry.kwh, 2)
        return dict(sorted(totals.items(), reverse=True))

    def yearly_costs(self) -> dict[str, dict[str, Any]]:
        """Cost pe ani: `facturat` după data emiterii, `platit` după data plății."""
        years: dict[str, dict[str, Any]] = {}

        def year(key: str) -> dict[str, Any]:
            return years.setdefault(
                key, {"facturat": 0.0, "platit": 0.0, "de_plata": 0.0, "facturi": 0, "plati": 0}
            )

        for inv in self.invoices:
            if inv.data_emitere is None:
                continue
            y = year(str(inv.data_emitere.year))
            y["facturat"] += inv.valoare
            y["de_plata"] += inv.rest_plata
            y["facturi"] += 1
        for pay in self.payments:
            if pay.get("data") and pay.get("suma") is not None:
                y = year(pay["data"][:4])
                y["platit"] += pay["suma"]
                y["plati"] += 1
        kwh_by_year = self.yearly_consumption()
        for name, y in years.items():
            for key in ("facturat", "platit", "de_plata"):
                y[key] = round(y[key], 2)
            kwh = kwh_by_year.get(name)
            y["kwh"] = kwh
            y["lei_pe_kwh"] = round(y["facturat"] / kwh, 2) if kwh and y["facturat"] > 0 else None
        return dict(sorted(years.items(), reverse=True))

    def summary(self) -> dict[str, Any]:
        """Rezumat (folosit de scriptul de test și la diagnostic)."""
        last = self.last_consumption
        latest = self.latest_invoice
        return {
            "cont": self.uan,
            "pod": self.pod,
            "adresa": self.address,
            "perioada_index": self.window.label,
            "perioada_index_activa": self.window.is_open,
            "consum_ultima_luna_kwh": round(last.kwh, 2) if last else None,
            "luna": last.luna if last else None,
            "consum_anual_kwh": self.yearly_consumption(),
            "cost_anual": self.yearly_costs(),
            "total_de_plata_lei": self.total_balance,
            "restant_lei": self.overdue_amount,
            "facturi_neplatite": len(self.unpaid_invoices),
            "facturi_platite": len(self.paid_invoices),
            "ultima_factura": latest.as_attr() if latest else None,
            "ultima_plata": self.last_payment,
        }


def _payment(item: dict[str, Any]) -> dict[str, Any]:
    amount = to_float(_first(item, "amount", "Amount", "PaymentAmount"))
    when = parse_date(_first(item, "paymentDate", "PaymentDate", "date", "Date"))
    return {
        "data": iso(when),
        "suma": round(amount, 2) if amount is not None else None,
        "canal": _first(item, "channel", "PaymentChannel", "PaymentMethod", "type"),
    }


def account_id(account: dict[str, Any]) -> str:
    return str(account.get("UtilityAccountNumber") or "").strip()


def build_account_data(uan: str, raw: dict[str, Any]) -> AccountData:
    """raw: {account, bill, history, usage, window, pods} pentru un cont."""
    history = raw.get("history")
    invoices = [_invoice(i) for i in find_list(history, "objBillingHistoryEntity", "BillingHistory")]
    invoices.sort(key=lambda i: (i.data_emitere or date.min, i.numar), reverse=True)

    bill = find_record(raw.get("bill"), "rembalance", "billamount", "duedate", "invoicenumber")
    balance = to_float(_first(bill, "rembalance", "RemBalance", "TotalDue", "AmountDue"))
    allocate_balance(invoices, balance)

    payments = [
        _payment(p)
        for p in find_list(history, "objBillingPaymentHistoryEntity", "PaymentHistory")
    ]
    payments.sort(key=lambda p: p.get("data") or "", reverse=True)

    pods = data_list(raw.get("pods"))
    return AccountData(
        uan=uan,
        account=raw.get("account") or {},
        pod_info=pods[0] if pods else {},
        invoices=invoices,
        payments=payments,
        consumption=parse_usage(raw.get("usage")),
        window=parse_window(raw.get("window")),
        bill=bill,
        balance=balance,
    )
