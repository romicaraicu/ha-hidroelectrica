# 📋 Referință entități

[← Înapoi la README](../README.md)

Fiecare loc de consum e un dispozitiv. Entitățile au ID-uri previzibile: `<platformă>.hidroelectrica_ro_<cont>_<cheie>`, de ex. `sensor.hidroelectrica_ro_8000123456_total_de_plata`.

## Senzori

| Cheie | Nume | Valoare | Atribute |
|---|---|---|---|
| `loc_consum` | Loc de consum | adresa | `cont`, `numar_cont`, `pod`, `instalatie`, `contor`, `distribuitor` |
| `consum_ultima_luna` | Consum ultima lună | kWh | `luna`, `data`, `kwh`, `lei`, `consum_anual`, `istoric` (până la 36 de luni, cea mai nouă prima) |
| `consum_an_curent` | Consum an curent | kWh | `consum_anual` (`{"2026": 2450.0, "2025": …}`) |
| `cost_an_curent` | Plătit în anul curent | lei (după data plății) | `facturat`, `de_plata`, `facturi`, `cost_anual` |
| `total_de_plata` | Total de plată | lei (soldul din iHidro) | `restant`, `urmatoarea_scadenta`, `facturi_neplatite` |
| `facturi_neplatite` | Facturi neplătite | număr | `total_rest_plata`, `restant`, `urmatoarea_scadenta`, `facturi` |
| `facturi_platite` | Facturi plătite | număr | `ultima_factura_platita`, `facturi` (ultimele 12) |
| `ultima_factura` | Ultima factură | lei | `numar`, `data_emitere`, `scadenta`, `valoare`, `rest_plata`, `status`, `restanta`, `perioada` |
| `urmatoarea_scadenta` | Următoarea scadență | dată | – |
| `ultima_plata` | Ultima plată | lei | `data`, `canal`, `plati` (ultimele 12) |
| `perioada_index` | Perioadă transmitere index | „20.11.2026 - 27.11.2026” | `inceput`, `sfarsit`, `activa`, `zile_pana_la_inceput`, `zile_ramase` |
| `perioada_index_inceput` | Început perioadă index | dată | – |
| `perioada_index_sfarsit` | Sfârșit perioadă index | dată | – |

`cost_anual` are, pentru fiecare an: `facturat` (după data emiterii), `platit` (după data plății), `de_plata`, `facturi`, `plati`, `kwh`, `lei_pe_kwh`.

Fiecare factură din liste are: `numar`, `data_emitere`, `scadenta`, `valoare`, `rest_plata`, `status` (*Plătită*, *Parțial plătită*, *Neplătită*, *Credit*), `restanta`, `perioada`.

## Senzori binari

| Cheie | Nume | Pornit când |
|---|---|---|
| `perioada_index_activa` | Transmitere index permisă | azi e în perioada de transmitere |
| `factura_restanta` | Factură restantă | există rest de plată cu scadența depășită |

## Buton

| Cheie | Nume | Ce face |
|---|---|---|
| `actualizare` | Actualizare date | citește imediat datele din iHidro |

## Exemplu de automatizare

```yaml
alias: Hidroelectrica - poți transmite indexul
triggers:
  - trigger: state
    entity_id: binary_sensor.hidroelectrica_ro_8000123456_perioada_index_activa
    to: "on"
actions:
  - action: notify.notify
    data:
      message: >-
        Poți transmite indexul la Hidroelectrica până pe
        {{ states('sensor.hidroelectrica_ro_8000123456_perioada_index_sfarsit') }}.
```
