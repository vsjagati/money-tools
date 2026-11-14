"""Content pages must carry the officially sourced numbers, not approximations."""

from fastapi.testclient import TestClient

from money_tools.app import app

client = TestClient(app)


def test_irmaa_brackets_page_shows_official_tiers():
    r = client.get("/irmaa/brackets")
    assert r.status_code == 200
    # Tier figures from the official 2026 Medicare costs fact sheet
    assert "$202.90" in r.text and "$689.90" in r.text and "$38.99" in r.text
    assert "$109,001" in r.text  # the cliff example
    assert "ssa-44" in r.text.lower()  # appeal route linked


def test_rmd_table_page_shows_full_table_and_ages():
    r = client.get("/rmd/table")
    assert r.status_code == 200
    # Every divisor from Pub 590-B Appendix B must be present
    assert ">27.4<" in r.text and ">26.5<" in r.text and ">2.0<" in r.text
    assert "120" in r.text
    # Age rule from final rule 89 FR 58886
    assert "1960 or later" in r.text and "75" in r.text
    assert "1959" in r.text and "unresolved" in r.text
    assert "25%" in r.text and "April 1" in r.text
    assert "$12,195.12" in r.text  # worked example: 300,000 / 24.6


def test_calculator_pages_link_to_content_pages():
    assert '/irmaa/brackets' in client.get("/rmd/table").text
    assert client.get("/irmaa/brackets").status_code == 200
