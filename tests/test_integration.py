"""Test end-to-end: config flow, entități, reauth, diagnostic, dashboard."""

from datetime import date, timedelta

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hidroelectrica_ro.api import HidroelectricaAuthError
from custom_components.hidroelectrica_ro.const import CONF_ACCOUNTS, DOMAIN

from .conftest import UAN

Y = date.today().year


async def test_config_flow_creates_entry(hass: HomeAssistant, mock_api) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "utilizator", CONF_PASSWORD: "x"}
    )
    # un singur cont -> pasul de selecție e sărit
    assert result["type"] is FlowResultType.CREATE_ENTRY, result
    assert result["options"][CONF_ACCOUNTS] == [UAN]
    await hass.async_block_till_done()
    assert hass.states.get(f"sensor.hidroelectrica_ro_{UAN}_total_de_plata") is not None


async def test_config_flow_invalid_auth(hass: HomeAssistant, mock_api) -> None:
    mock_api.authenticate.side_effect = HidroelectricaAuthError("Parolă greșită")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "utilizator", CONF_PASSWORD: "x"}
    )
    assert result["errors"] == {"base": "invalid_auth"}


async def _setup(hass, mock_api):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="utilizator",
        data={CONF_USERNAME: "utilizator", CONF_PASSWORD: "x"},
        options={CONF_ACCOUNTS: [UAN]},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities(hass: HomeAssistant, mock_api) -> None:
    await _setup(hass, mock_api)
    s = lambda k: hass.states.get(f"sensor.hidroelectrica_ro_{UAN}_{k}")  # noqa: E731

    assert s("loc_consum").state == "Str. Test 1, Iasi"
    assert s("loc_consum").attributes["pod"] == "RO003E000000001"
    assert s("loc_consum").attributes["distribuitor"] == "DEER"
    assert float(s("consum_ultima_luna").state) == 245.0
    assert s("consum_ultima_luna").attributes["luna"] == f"noiembrie {Y}"
    assert len(s("consum_ultima_luna").attributes["istoric"]) == 3
    assert float(s("consum_an_curent").state) == 455.4
    assert float(s("total_de_plata").state) == 180.0
    assert s("total_de_plata").attributes["unit_of_measurement"] == "RON"
    # soldul 180 acoperă H0003 (150) + 30 din H0002 -> 2 neplătite, 1 plătită
    assert s("facturi_neplatite").state == "2"
    unpaid = s("facturi_neplatite").attributes["facturi"]
    assert [(i["numar"], i["rest_plata"], i["status"]) for i in unpaid] == [
        ("H0003", 150.0, "Neplătită"), ("H0002", 30.0, "Parțial plătită"),
    ]
    assert s("facturi_platite").state == "1"
    assert s("ultima_factura").attributes["numar"] == "H0003"
    assert float(s("ultima_plata").state) == 70.0
    assert s("ultima_plata").attributes["canal"] == "Banca"
    assert s("urmatoarea_scadenta").state == (date.today() + timedelta(days=10)).isoformat()
    assert float(s("cost_an_curent").state) == 70.0
    costs = s("cost_an_curent").attributes["cost_anual"]
    assert list(costs) == [str(Y), str(Y - 1)]
    assert costs[str(Y)]["facturat"] == 250.0 and costs[str(Y)]["de_plata"] == 180.0
    assert costs[str(Y)]["lei_pe_kwh"] == round(250 / 455.4, 2)
    assert costs[str(Y - 1)]["platit"] == 120.0 and costs[str(Y - 1)]["kwh"] == 200.0
    assert " - " in s("perioada_index").state
    assert s("perioada_index").attributes["zile_ramase"] == 3
    assert hass.states.get(f"binary_sensor.hidroelectrica_ro_{UAN}_perioada_index_activa").state == "on"
    assert hass.states.get(f"binary_sensor.hidroelectrica_ro_{UAN}_factura_restanta").state == "on"
    assert hass.states.get(f"button.hidroelectrica_ro_{UAN}_actualizare") is not None
    # testele rulează în engleză; în română numele vine din ro.json
    assert s("total_de_plata").attributes["friendly_name"].endswith("Amount due")


async def test_optional_endpoint_failure_keeps_working(hass: HomeAssistant, mock_api) -> None:
    from custom_components.hidroelectrica_ro.api import HidroelectricaConnectionError

    mock_api.get_usage.side_effect = HidroelectricaConnectionError("HTTP 500")
    mock_api.get_window_dates.side_effect = HidroelectricaConnectionError("HTTP 500")
    await _setup(hass, mock_api)
    assert hass.states.get(f"sensor.hidroelectrica_ro_{UAN}_total_de_plata").state == "180.0"
    assert hass.states.get(f"sensor.hidroelectrica_ro_{UAN}_consum_ultima_luna").state == "unknown"
    assert hass.states.get(f"sensor.hidroelectrica_ro_{UAN}_perioada_index").state == "Perioadă indisponibilă"


async def test_auth_failure_starts_reauth(hass: HomeAssistant, mock_api) -> None:
    mock_api.get_accounts.side_effect = HidroelectricaAuthError("x")
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="u",
        data={CONF_USERNAME: "u", CONF_PASSWORD: "x"}, options={},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_diagnostics_redacts(hass: HomeAssistant, mock_api) -> None:
    from custom_components.hidroelectrica_ro.diagnostics import (
        async_get_config_entry_diagnostics,
    )
    entry = await _setup(hass, mock_api)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "Str. Test 1" not in text
    assert UAN not in text
    assert "RO003E000000001" not in text
    assert "objBillingHistoryEntity" in text  # structura e păstrată


async def test_dashboard_templates_render(hass: HomeAssistant, mock_api) -> None:
    """Toate template-urile markdown din dashboard se randează fără erori."""
    from pathlib import Path

    import yaml
    from homeassistant.helpers.template import Template

    await _setup(hass, mock_api)
    src = Path(__file__).parent.parent / "dashboard" / "hidroelectrica_dashboard.yaml"
    dash = yaml.safe_load(src.read_text().replace("0000000000", UAN))

    contents: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "markdown":
                contents.append(node["content"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str) and node.split(".")[0] in ("sensor", "binary_sensor", "button") \
                and node.split(".")[-1].startswith("hidroelectrica_ro_"):
            assert hass.states.get(node) is not None, node

    walk(dash)
    assert len(contents) >= 6
    rendered = [Template(c, hass).async_render(parse_result=False) for c in contents]
    joined = "\n".join(rendered)
    print(joined)
    assert "H0003" in joined and f"noiembrie {Y}" in joined and "Poți transmite" in joined
    assert "|:--|:--|:--|--:|:--|\n| H0003" in joined
    assert f"| **{Y}** | **70.00** | 250.00 | 180.00 | 455 | 0.55 |" in joined
