"""Constante pentru integrarea Hidroelectrica."""

from __future__ import annotations

DOMAIN = "hidroelectrica_ro"
MANUFACTURER = "Hidroelectrica"

# --- API ---
# Portalul web ihidro.ro/portal cere Cloudflare Turnstile (captcha) la login,
# deci nu poate fi folosit automat. Aplicația de mobil iHidro folosește un API
# separat (platforma SEW "smartcmobile"), servit tot prin ihidro.ro, fără captcha.
API_BASE_URL = "https://ihidro.ro"
API_HOST_HEADER = "hidroelectrica-svc.smartcmobile.com"
API_USER_AGENT = "okhttp/4.9.0"
PORTAL_URL = "https://ihidro.ro/portal/"
LANGUAGE = "RO"

EP_GET_ID = "/API/UserLogin/GetId"
EP_VALIDATE_LOGIN = "/API/UserLogin/ValidateUserLogin"
EP_USER_SETTING = "/API/UserLogin/GetUserSetting"
EP_BILL = "/Service/Billing/GetBill"
EP_BILLING_HISTORY = "/Service/Billing/GetBillingHistoryList"
EP_USAGE = "/Service/Usage/GetUsageGeneration"
EP_WINDOW_DATES = "/Service/SelfMeterReading/GetWindowDates"
EP_PODS = "/Service/SelfMeterReading/GetPods"

# Câți ani de facturi/plăți cerem la fiecare actualizare (anul curent + N-1)
HISTORY_YEARS = 3

# --- Config entry ---
CONF_ACCOUNTS = "accounts"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL_HOURS = 6
MIN_SCAN_INTERVAL_HOURS = 1
MAX_SCAN_INTERVAL_HOURS = 24

# Toleranță pentru comparații de sume (lei)
AMOUNT_EPSILON = 0.005
