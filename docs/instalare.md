# 📦 Instalare și configurare

[← Înapoi la README](../README.md)

**Cuprins**
1. [Înainte să începi](#1-înainte-să-începi)
2. [Alege cum instalezi](#2-alege-cum-instalezi)
3. [Leagă contul](#3-leagă-contul)
4. [Pune dashboard-ul și graficele](#4-pune-dashboard-ul-și-graficele)
5. [Mai târziu: opțiuni, parolă nouă, ștergere](#5-mai-târziu)

---

## 1. Înainte să începi

- [ ] Home Assistant **2024.12** sau mai nou
- [ ] Contul iHidro funcționează în aplicația de mobil sau pe [ihidro.ro](https://ihidro.ro/portal/) și vezi în el cel puțin un loc de consum
- [ ] Știi **numele de utilizator** (nu neapărat emailul) și parola

<details>
<summary><b>Verifică contul înainte să instalezi ceva în Home Assistant (recomandat)</b></summary>

Pe orice calculator cu Python 3.11+, din folderul proiectului:

```bash
python3 -m venv .venv
```
```bash
.venv/bin/pip install aiohttp
```
```bash
.venv/bin/python tools/test_connection.py
```

Scriptul cere utilizatorul și parola, apoi afișează:
- **Structura răspunsurilor**: doar numele câmpurilor, fără valori personale
- **Ce va vedea Home Assistant**: consum, facturi, plăți, perioada de index

Dacă vezi `✓ Autentificat` și cifrele seamănă cu cele din aplicație, poți trece mai departe. Dacă ceva lipsește sau arată greșit, trimite secțiunea *Structura răspunsurilor* (vezi [depanare.md](depanare.md)).

</details>

---

## 2. Alege cum instalezi

| Versiunea Home Assistant | Metoda |
|---|---|
| 2026.11 sau mai nouă | **A. Marketplace** (recomandat) |
| mai veche de 2026.11 | **B. HACS** |
| orice versiune, fără magazin | **C. Copiere manuală** |

### A. Marketplace

1. **Setări** → **Marketplace** → **Add from link**
2. Scrie `romicaraicu/ha-hidroelectrica` → **Add** (prima dată, Marketplace cere legătura cu GitHub)
3. Dacă te întreabă de **Type**, alege **Integration**
4. Deschide **Hidroelectrica (iHidro)** → **Install**
5. Dacă în **Reparații** apare o cerere de restart, accept-o

### B. HACS

1. **HACS** → ⋮ → **Custom repositories**
2. Adaugă `https://github.com/romicaraicu/ha-hidroelectrica`, tip **Integration**
3. Caută *Hidroelectrica (iHidro)* → **Download**
4. Repornește Home Assistant

### C. Copiere manuală

Copiază folderul `custom_components/hidroelectrica_ro` în `/config/custom_components/` (prin Samba, SSH sau *File editor*), ca să obții `/config/custom_components/hidroelectrica_ro/manifest.json`. Repornește Home Assistant.

---

## 3. Leagă contul

1. **Setări** → **Dispozitive și servicii** → **+ Adaugă integrare** → *Hidroelectrica*
2. Introdu **utilizatorul** și **parola** iHidro
3. Dacă ai **mai multe locuri de consum**, bifează-le pe cele dorite și alege intervalul de citire (implicit 6 ore)

Fiecare loc de consum devine un dispozitiv „Hidroelectrica *adresa*”, cu 14 senzori, 2 senzori binari și un buton. Detalii în [entitati.md](entitati.md).

| Mesaj | Ce faci |
|---|---|
| *Nume de utilizator sau parolă incorecte.* | Încearcă aceleași date în aplicația iHidro; atenție la spațiile copiate la final |
| *Nu mă pot conecta la iHidro.* | Serverul sau rețeaua au o problemă; reîncearcă. Dacă persistă, vezi [depanare.md](depanare.md) |
| *Contul nu are niciun loc de consum asociat.* | Asociază locul de consum din aplicația iHidro |

---

## 4. Pune dashboard-ul și graficele

Dashboard-ul `dashboard/hidroelectrica_dashboard.yaml` folosește doar carduri incluse în Home Assistant:
- **Sumar**: total de plată, scadență, consum, ultima plată
- **Transmitere index**
- **Facturi de plată**, **Facturi plătite** și **Plăți recente**
- **Consum pe luni** și **Consum pe ani**, cu bare
- **Cost pe ani**: plătit, facturat, de plată, kWh, lei/kWh
- un al doilea tab, **Preț kWh**: prețul ultimei luni, media anului, tabel pe luni (24) și pe ani

**Pas 1: află numărul contului.** E atributul `cont` al senzorului *Loc de consum* (sau numărul de serie al dispozitivului, dacă nu e POD-ul). Entitățile se numesc `sensor.hidroelectrica_ro_<cont>_…`.

**Pas 2: generează fișierele:**

```bash
python3 tools/genereaza_dashboard.py 8000123456
```

Se creează `dashboard/hidroelectrica_<cont>.yaml` și `dashboard/card_grafic_consum_<cont>.yaml`. Sunt excluse din git, pentru că conțin numărul contului.

**Pas 3: creează panoul.**
1. **Setări** → **Panouri de bord** → **+ Adaugă panou** → **Pornește de la zero**
2. Deschide panoul → ✏️ → ⋮ → **Editor de configurație brută**
3. Lipește conținutul fișierului `hidroelectrica_<cont>.yaml` și salvează

### Grafice de consum pe luni și pe ani

1. Instalează cardul `apexcharts-card`: Marketplace → **Add from link** → `RomRider/apexcharts-card` (sau HACS → *Frontend*)
2. În panou: ✏️ → **Adaugă card** → **Manual**
3. Lipește conținutul fișierului `card_grafic_consum_<cont>.yaml`

Primești patru grafice: consumul lunar pe ultimii 2 ani, consumul total pe fiecare an, prețul mediu lunar (lei/kWh, linie) și prețul mediu anual.

---

## 5. Mai târziu

**Alte locuri de consum sau alt interval:** **Setări** → **Dispozitive și servicii** → **Hidroelectrica** → ⚙️ **Configurare**.

**Citire imediată:** butonul **Actualizare date**.

**Ți-ai schimbat parola:** Home Assistant afișează *Reautentificare necesară*; apasă și introdu parola nouă.

**Renunți:** **Setări** → **Dispozitive și servicii** → **Hidroelectrica** → ⋮ → **Șterge**, apoi dezinstalează din Marketplace/HACS (sau șterge `/config/custom_components/hidroelectrica_ro`) și repornește.
