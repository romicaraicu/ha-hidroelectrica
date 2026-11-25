<div align="center">

# 💧 Hidroelectrica pentru Home Assistant

**Consumul, facturile și perioada de transmitere a indexului de la Hidroelectrica (iHidro), direct în Home Assistant.**

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-41BDF5?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![Marketplace](https://img.shields.io/badge/Marketplace-Add%20from%20link-41BDF5?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/integrations/marketplace)
[![Licență MIT](https://img.shields.io/badge/licen%C8%9B%C4%83-MIT-1F446E)](LICENSE.md)

</div>

Dacă ai contract de energie electrică cu Hidroelectrica și folosești Home Assistant, integrarea asta îți scutește drumul prin [iHidro](https://ihidro.ro/portal/). Te autentifici o singură dată, cu utilizatorul și parola de acolo. De atunci, consumul lunar, facturile, plățile și perioada de transmitere a indexului apar ca entități obișnuite. Le poți pune pe dashboard, le poți folosi în automatizări sau te poți lăsa notificat de ele.

> [!NOTE]
> Proiect personal, neoficial, fără legătură cu Hidroelectrica. Citește aceleași date pe care le vezi și tu în aplicația iHidro.
>
> Domeniul integrării este `hidroelectrica_ro`, deci poate fi instalată alături de alte integrări Hidroelectrica (de ex. cnecrea/hidroelectrica, care folosește `hidroelectrica`).

---

## Ce afli din Home Assistant

| Întrebarea ta | Unde găsești răspunsul |
|---|---|
| **Cât am consumat luna trecută?** | `Consum ultima lună` (kWh), cu istoric pe până la 36 de luni |
| **Cât am consumat pe fiecare an?** | `Consum an curent` + totaluri pe fiecare an |
| **Am ceva de plată?** | `Total de plată` (lei) și `Facturi neplătite`, cu lista completă |
| **Am vreo factură întârziată?** | senzorul binar `Factură restantă` și `Următoarea scadență` |
| **Ce am plătit deja?** | `Facturi plătite`, `Ultima plată` și lista plăților recente |
| **Cât m-a costat curentul pe fiecare an?** | `Plătit în anul curent` + tabel pe ani: plătit, facturat, kWh, lei/kWh |
| **Când pot transmite indexul?** | `Perioadă transmitere index` + senzorul `Transmitere index permisă` |
| **Ce date are locul de consum?** | `Loc de consum`: adresă, cont, POD, distribuitor |

Pe lângă senzori ai:
- un buton **Actualizare date**
- un **dashboard** gata făcut, cu tabele de consum pe luni și pe ani
- **grafice** de consum lunar și anual (card ApexCharts, opțional)

---

## Pornire rapidă

**1. Instalează din Marketplace** (Home Assistant 2026.11 sau mai nou)

**Setări** → **Marketplace** → **Add from link** → `romicaraicu/ha-hidroelectrica` → **Install**

**2. Adaugă contul**

**Setări** → **Dispozitive și servicii** → **Adaugă integrare** → *Hidroelectrica (iHidro)* → utilizator + parolă iHidro

**3. (Opțional) Pune dashboard-ul**

```bash
python3 tools/genereaza_dashboard.py <numărul contului>
```

Apoi lipește fișierul generat în *Editorul de configurație brută* al unui panou nou.

Instalarea pe versiuni mai vechi (HACS sau manual) și dashboard-ul sunt explicate în **[docs/instalare.md](docs/instalare.md)**.

---

## Documentație

| Ghid | Ce conține |
|---|---|
| 📦 [Instalare și configurare](docs/instalare.md) | Marketplace, HACS, manual, primul cont, dashboard, grafice |
| 📋 [Referință entități](docs/entitati.md) | Fiecare senzor, cu atributele lui |
| 🛠️ [Depanare](docs/depanare.md) | Testul de conexiune, log-uri, diagnostic, întrebări |
| 📜 [Istoric versiuni](CHANGELOG.md) | Ce s-a schimbat în fiecare versiune |

---

## Cum funcționează

```
 Home Assistant                         Hidroelectrica (ihidro.ro)
┌──────────────────────┐   login    ┌──────────────────────────────┐
│ config flow          │ ─────────▶ │ /API/UserLogin/GetId         │
│ (utilizator + parolă)│ ◀───────── │ /API/UserLogin/ValidateUser… │ → UserID + SessionToken
└──────────┬───────────┘            └──────────────────────────────┘
           │ la fiecare 6 h (configurabil)
           ▼
┌──────────────────────┐   Basic    ┌──────────────────────────────┐
│ coordinator          │ ─────────▶ │ /Service/Billing/…           │
│ → parser → senzori   │ ◀───────── │ /Service/Usage/…             │
└──────────────────────┘    JSON    │ /Service/SelfMeterReading/…  │
                                    └──────────────────────────────┘
```

- **De ce nu portalul web?** Login-ul de pe ihidro.ro/portal cere un captcha Cloudflare, verificat pe server, deci nu poate fi automatizat. Integrarea folosește același API ca **aplicația de mobil iHidro**, care nu are captcha.
- **Sesiunea** se reînnoiește singură: dacă serverul o respinge, integrarea se autentifică din nou cu datele salvate.
- **Facturi plătite / neplătite.** API-ul dă soldul total de plată, nu statusul fiecărei facturi. Soldul se atribuie facturilor începând cu cea mai nouă: facturile acoperite de sold sunt neplătite (sau parțial plătite), cele mai vechi sunt plătite.

<details>
<summary><b>Endpoint-uri folosite</b></summary>

| Endpoint | Pentru ce |
|---|---|
| `POST /API/UserLogin/GetId` | cheie temporară pentru login |
| `POST /API/UserLogin/ValidateUserLogin` | login cu utilizator + parolă |
| `POST /API/UserLogin/GetUserSetting` | locurile de consum (conturile) |
| `POST /Service/Billing/GetBill` | factura curentă și soldul de plată |
| `POST /Service/Billing/GetBillingHistoryList` | istoric facturi și plăți |
| `POST /Service/Usage/GetUsageGeneration` | consum lunar |
| `POST /Service/SelfMeterReading/GetWindowDates` | perioada de transmitere a indexului |
| `POST /Service/SelfMeterReading/GetPods` | POD, instalație, distribuitor |

</details>

<details>
<summary><b>Organizarea codului</b></summary>

```
custom_components/hidroelectrica_ro/
  api.py            client HTTP: login + apeluri API (fără Home Assistant)
  parser.py         transformă JSON-ul în date per loc de consum
  coordinator.py    citește periodic toate datele contului
  config_flow.py    adăugare cont, reautentificare, opțiuni
  entity.py         bază comună (un dispozitiv per loc de consum)
  sensor.py · binary_sensor.py · button.py
  diagnostics.py    export cu datele personale mascate
dashboard/          dashboard Lovelace + grafice ApexCharts opționale
tools/              test de conexiune și generator de dashboard
tests/              teste rulate cu Home Assistant real
```

</details>

---

## Bune de știut

- Datele de consum sunt **lunare**, așa cum le facturează Hidroelectrica. Nu sunt citiri în timp real.
- Integrarea doar **citește** date. Indexul se transmite deocamdată din aplicația iHidro sau de pe portal.
- API-ul aplicației de mobil nu e documentat public. Dacă Hidroelectrica îl schimbă, integrarea poate avea nevoie de o actualizare.

## Ai găsit o problemă?

Deschide un [issue](https://github.com/romicaraicu/ha-hidroelectrica/issues). Înainte, șterge din log-uri și din capturi adresa, codul POD și numărul contului.

## Licență

[MIT](LICENSE.md)
