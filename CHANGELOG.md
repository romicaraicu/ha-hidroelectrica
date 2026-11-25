# Istoric versiuni

## 0.1.3

- Facturi de plată: factura curentă (din `GetBill`) e luată în calcul și când nu apare încă în istoricul de facturi. Înainte, soldul se atribuia unor facturi deja plătite, care apăreau greșit ca restante
- `tools/test_connection.py --facturi`: diagnostic cu sumele, datele și statusul calculat pentru fiecare factură (identificatorii sunt mascați)

## 0.1.2

- Numărul facturii: nu mai apare identificatorul criptat (ex. `Vrem+jy3…==`); se caută numărul lizibil (`invoiceNumber`, `exbel` etc.), iar dacă nu există se afișează „—”
- `tools/test_connection.py` arată un exemplu de factură și plată cu valorile mascate, pentru depanare (`--exemplu` afișează doar această secțiune); întrebările și mesajele de progres apar și când ieșirea e redirecționată

## 0.1.1

- Domeniul integrării devine `hidroelectrica_ro` (folderul `custom_components/hidroelectrica_ro`), ca să nu intre în conflict cu alte integrări Hidroelectrica care folosesc `hidroelectrica`
- Numele afișat devine „Hidroelectrica (iHidro)”
- Entitățile se numesc acum `sensor.hidroelectrica_ro_<cont>_…`; dashboard-ul și graficele trebuie regenerate cu `tools/genereaza_dashboard.py`

## 0.1.0

Prima versiune.

- Login cu utilizator + parolă iHidro, prin API-ul aplicației de mobil (portalul web cere captcha)
- Un dispozitiv per loc de consum, cu 13 senzori, 2 senzori binari și un buton de actualizare
- Consum lunar (istoric până la 36 de luni) și totaluri pe ani
- Facturi de plată, facturi plătite, ultima factură, următoarea scadență, factură restantă
- Plăți recente și cost pe ani (facturat, plătit, de plată, lei/kWh)
- Perioada de transmitere a indexului
- Dashboard cu carduri standard + grafice ApexCharts lunar și anual
- Diagnostic cu datele personale mascate
