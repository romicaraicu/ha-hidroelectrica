# 🛠️ Depanare

[← Înapoi la README](../README.md)

## 1. Testul de conexiune (fără Home Assistant)

```bash
.venv/bin/python tools/test_connection.py
```

Arată dacă login-ul merge și ce date ar vedea Home Assistant. Secțiunea **Structura răspunsurilor** conține doar numele câmpurilor și tipurile lor, fără valori. Pe ea o poți trimite când ceva lipsește sau arată greșit (de exemplu consumul gol sau date inversate).

Opțiuni utile:

| Opțiune | Ce afișează |
|---|---|
| `--facturi` | fiecare factură cu sumă, emitere, scadență și statusul calculat (plătită / neplătită), plus plățile și soldul; identificatorii sunt mascați. Pentru o factură care apare greșit ca restantă |
| `--exemplu` | o factură și o plată cu toate valorile mascate (9 = cifră, a/A = literă), ca să se vadă numele câmpurilor |
| `--dump out` | JSON-urile complete. **Acestea conțin date personale**; nu le publica |

## 2. Log-uri detaliate

```yaml
logger:
  logs:
    custom_components.hidroelectrica_ro: debug
```

## 3. Diagnostic

**Setări** → **Dispozitive și servicii** → **Hidroelectrica** → ⋮ → **Descarcă diagnosticul**. Adresa, contul, POD-ul și datele de login sunt mascate; structura răspunsurilor e inclusă.

## Întrebări

**De ce nu folosește portalul web?** Login-ul de pe ihidro.ro/portal cere un captcha Cloudflare Turnstile verificat pe server. Aplicația de mobil iHidro folosește alt API, fără captcha, și pe acela îl folosește și integrarea.

**Cum se decide dacă o factură e plătită?** API-ul dă soldul total de plată, nu statusul fiecărei facturi. Soldul se atribuie facturilor de la cea mai nouă spre cea mai veche. Factura curentă (cea din `GetBill`) e inclusă chiar dacă nu apare încă în istoric. Dacă ai plătit o factură mai veche și ai lăsat una mai nouă neplătită, lista poate diferi puțin de portal, dar totalul de plată e corect.

**Pot transmite indexul din Home Assistant?** Nu încă. Va fi adăugat după ce formatul cererii e verificat pe un cont real, ca să nu trimită date greșite.

**Datele sunt în timp real?** Nu. Consumul e lunar, ca în factură.

| Problemă | Cauză probabilă |
|---|---|
| *Reautentificare necesară* | parola s-a schimbat sau contul e blocat temporar |
| Entitățile sunt *indisponibile* | serverul iHidro nu a răspuns; se reîncearcă la următorul interval |
| Consum gol, facturi prezente | endpoint-ul de consum a răspuns altfel decât ne așteptăm: rulează testul de conexiune |
| Perioada de index e „Perioadă indisponibilă” | endpoint-ul de perioadă nu a răspuns sau are alt format: rulează testul de conexiune |
