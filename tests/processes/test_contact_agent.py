import json
from typing import Any

import pytest

from processes import contact_agent


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        return None


@pytest.mark.parametrize(
    ("company_status", "match_status", "outreach_eligible"),
    [
        ("active", "verified_corporate", True),
        ("dissolved", "inactive", False),
    ],
)
def test_contact_agent_prints_enriched_deduplicated_businesses(
    monkeypatch,
    capsys,
    company_status: str,
    match_status: str,
    outreach_eligible: bool,
) -> None:
    calls = []

    def fake_get(url, **kwargs):
        calls.append(("GET", url, kwargs))

        if url == contact_agent.NOMINATIM_URL:
            return FakeResponse(
                [
                    {
                        "display_name": "Preston, Lancashire, England",
                        "osm_type": "relation",
                        "osm_id": 1,
                        "lat": "53.759",
                        "lon": "-2.699",
                        "boundingbox": ["53.7", "53.8", "-2.8", "-2.6"],
                        "licence": "Data © OpenStreetMap contributors",
                    }
                ]
            )

        if url == contact_agent.COMPANIES_HOUSE_URL:
            return FakeResponse(
                {
                    "items": [
                        {
                            "title": "EXAMPLE CAFE LIMITED",
                            "company_number": "12345678",
                            "company_status": company_status,
                            "company_type": "ltd",
                            "address": {
                                "address_line_1": "1 Market Street",
                                "locality": "Preston",
                                "postal_code": "PR1 1AA",
                            },
                        }
                    ]
                }
            )

        raise AssertionError(f"Unexpected GET request: {url}")

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        assert url == contact_agent.OVERPASS_URL

        return FakeResponse(
            {
                "elements": [
                    {
                        "type": "node",
                        "id": 10,
                        "lat": 53.76,
                        "lon": -2.70,
                        "tags": {
                            "name": "Example Cafe",
                            "amenity": "cafe",
                            "addr:housenumber": "1",
                            "addr:street": "Market Street",
                            "addr:postcode": "PR1 1AA",
                            "phone": "+44 1772 123456",
                        },
                    },
                    {
                        "type": "way",
                        "id": 20,
                        "center": {"lat": 53.76, "lon": -2.70},
                        "tags": {
                            "name": "Example Cafe",
                            "amenity": "cafe",
                            "addr:housenumber": "1",
                            "addr:street": "Market Street",
                            "addr:postcode": "PR1 1AA",
                            "website": "https://example.test",
                            "email": "HELLO@EXAMPLE.TEST",
                        },
                    },
                    {
                        "type": "node",
                        "id": 30,
                        "lat": 53.77,
                        "lon": -2.71,
                        "tags": {
                            "name": "Another Cafe",
                            "amenity": "cafe",
                            "addr:housenumber": "2",
                            "addr:street": "Church Street",
                            "addr:postcode": "PR1 2AB",
                        },
                    },
                ]
            }
        )

    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "test-api-key")
    monkeypatch.setattr(contact_agent.requests, "get", fake_get)
    monkeypatch.setattr(contact_agent.requests, "post", fake_post)

    contact_agent.main(["--location", "Preston", "--limit", "1"])

    output = json.loads(capsys.readouterr().out)
    business = output["businesses"][0]

    assert output["campaign_location"]["name"] == "Preston, Lancashire, England"
    assert len(output["businesses"]) == 1
    assert business["business_name"] == "Example Cafe"
    assert business["website"] == "https://example.test"
    assert business["email"] == "hello@example.test"
    assert business["phone"] == "+44 1772 123456"
    assert business["osm_sources"] == [
        {"type": "node", "id": 10},
        {"type": "way", "id": 20},
    ]
    assert business["registry_match_status"] == match_status
    assert business["registration_number"] == "12345678"
    assert business["registered_name"] == "EXAMPLE CAFE LIMITED"
    assert business["outreach_eligible"] is outreach_eligible
    assert [method for method, _, _ in calls] == ["GET", "POST", "GET"]
