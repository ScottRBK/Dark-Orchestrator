"""Discover and verify businesses for a campaign location.

Run a small local sample with:
uv run --env-file .env processes/contact_agent.py --location Preston --limit 5
"""
import argparse
import json
import os
import re
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = (
   "DarkContactAgent/0.1 "
   "(https://github.com/ScottRBK/Dark-Orchestrator)"
)
COMPANIES_HOUSE_URL = "https://api.company-information.service.gov.uk/search/companies"
OSM_ATTRIBUTION = "Data © OpenStreetMap contributors, ODbL 1.0"
ALLOWED_COMPANY_TYPES = {"ltd", "llp", "plc"}
COMPANIES_HOUSE_REQUEST_INTERVAL_SECONDS = 0.55

TARGET_AMENITIES = {
   "animal_boarding",
   "bar",
   "cafe",
   "car_rental",
   "car_wash",
   "clinic",
   "conference_centre",
   "dentist",
   "doctors",
   "driving_school",
   "events_venue",
   "fast_food",
   "gambling",
   "ice_cream",
   "money_transfer",
   "nightclub",
   "pharmacy",
   "post_office",
   "pub",
   "restaurant",
   "studio",
   "vehicle_inspection",
   "veterinary",
}

EXCLUDED_AMENITIES = {
   "bank",
   "building_society",
   "casino",
   "cinema",
   "childcare",
   "college",
   "community_centre",
   "fire_station",
   "fuel",
   "kindergarten",
   "library",
   "parking",
   "place_of_worship",
   "police",
   "school",
   "social_facility",
   "townhall",
   "university",
}

EXCLUDED_SHOPS = {
   "no",
   "vacant",
}

EXCLUDED_OFFICES = {
   "association",
   "educational_institution",
   "government",
   "ngo",
}

class ContactAgent:
    def __init__(self) -> None:
        self._companies_house_cache: dict[str, dict[str, Any]] = {}
        self._last_companies_house_request_at: float | None = None

    def resolve_location(self, location: str, country_iso: str = "gb") -> dict[str, object]:
        location = location.strip() 
        country_iso = country_iso.strip().lower() 

        if not location:
            raise ValueError("Campaing location is required")

        try:
            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": location,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": country_iso,
                    "featureType": "settlement",
                },
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "en",
                    "User-Agent": USER_AGENT,
                },
                timeout=(5, 10),
            )
            response.raise_for_status() 
            results = response.json() 

        except requests.RequestException as error:
            raise RuntimeError("Unable to validate campaign location") from error 

        if not isinstance(results, list) or not results: 
            raise ValueError(f"Unknown Location: {location} in country: {country_iso}")

        result = results[0]
        south, north, west, east = map(float, result["boundingbox"])

        return {
            "name": result["display_name"], 
            "osm_type": result["osm_type"],
            "osm_id": result["osm_id"],
            "latitude": float(result["lat"]),
            "longitude": float(result["lon"]),
            "bounding_box": {
                "south": south,
                "north": north,
                "west": west, 
                "east": east,
            },
            "licence": result["licence"],
        }

    def fetch_osm_data(self, bounding_box: dict[str, float]) -> list[dict[str, object]]:
    
        south = bounding_box["south"]
        west = bounding_box["west"]
        north = bounding_box["north"]
        east = bounding_box["east"]

        query = f"""
        [out:json][timeout:60];
        (
            nwr["shop"]["name"]({south},{west},{north},{east});
            nwr["amenity"]["name"]({south},{west},{north},{east});
            nwr["office"]["name"]({south},{west},{north},{east});
            nwr["craft"]["name"]({south},{west},{north},{east});
        );
        out center tags;
        """

        try: 
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers={
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
                timeout=(10, 90),
            )
            response.raise_for_status()
            result = response.json() 
        except requests.RequestException as error:
            raise RuntimeError("Unable to retrieve businesses") from error 

        businesses = []

        for element in result.get("elements", []):
            tags = element.get("tags", {})
            center = element.get("center", {})

            businesses.append(
                {
                    "osm_type": element["type"],
                    "osm_id": element["id"],
                    "name": tags["name"],
                    "latitude": element.get("lat", center.get("lat")),
                    "longitude": element.get("lon", center.get("lon")),
                    "tags": tags,
                }
            )

        return businesses

    def _classify_business(self, tags: dict[str, str]) -> str | None:

        amenity = tags.get("amenity") 
        shop = tags.get("shop")
        office = tags.get("office")
        craft = tags.get("craft")

        if amenity in EXCLUDED_AMENITIES:
            return None 
        if shop and shop not in EXCLUDED_SHOPS:
            return "shop"
        if office and office not in EXCLUDED_OFFICES:
            return "office"
        if craft:
            return "craft"
        if amenity in TARGET_AMENITIES:
            return "amenity"

        return None 

    def _deduplication_key(self, business: dict[str, Any]) -> tuple[object, ...]:
        tags = business["tags"]
        name = business["business_name"].casefold()
        house_number = tags.get("addr:housenumber")
        street = tags.get("addr:street")
        postcode = tags.get("addr:postcode")

        if street and postcode:
            return (
                "address",
                name,
                house_number.casefold() if house_number else None,
                street.casefold(),
                postcode.replace(" ", "").upper(),
            )

        return ("osm", business["osm_type"], business["osm_id"])

    def _deduplicate(
        self,
        businesses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        unique = {}

        for business in businesses:
            key = self._deduplication_key(business)
            existing = unique.get(key)

            if existing is None:
                unique[key] = business
                continue

            existing["tags"] = {
                **business["tags"],
                **existing["tags"],
            }

            for field in ("website", "email", "phone", "postcode"):
                existing[field] = existing.get(field) or business.get(field)

            existing["osm_sources"].extend(business["osm_sources"])

        return list(unique.values())

    def extract_businesses(
        self,
        osm_data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        businesses = []
        for business in osm_data:
            tags = business.get("tags", {})


            website = tags.get("website") or tags.get("contact:website")
            email = tags.get("email") or tags.get("contact:email")
            phone = tags.get("phone") or tags.get("contact:phone")
            business_name = " ".join(tags["name"].split())
            postcode = tags.get("addr:postcode")

            category = self._classify_business(tags=tags)
            if category is None: 
                continue
            
            businesses.append(
                {
                    **business,
                    "business_name": business_name,
                    "category": category,
                    "osm_sources": [
                        {
                            "type": business["osm_type"],
                            "id": business["osm_id"],
                        }
                    ],
                    "website": website.strip() if website else None,
                    "email": email.strip().lower() if email else None,
                    "phone": phone.strip() if phone else None,
                    "postcode": postcode.strip().upper() if postcode else None,
                }
            )
        return self._deduplicate(businesses)

    def enrich_legal_entities(
        self,
        businesses: list[dict[str, Any]],
        country_iso: str,
    ) -> list[dict[str, Any]]:
        country_iso = country_iso.strip().lower()

        if country_iso != "gb":
            raise ValueError(f"Unsupported country: {country_iso}")

        return self._enrich_from_companies_house(businesses)

    @staticmethod
    def _normalise_company_name(name: str) -> str:
        normalised = unicodedata.normalize("NFKD", name)
        normalised = normalised.encode("ascii", "ignore").decode()
        normalised = normalised.casefold().replace("&", " and ")
        normalised = re.sub(r"[^a-z0-9]+", " ", normalised)
        normalised = re.sub(
            r"\b(?:limited|ltd|llp|plc)\b$",
            "",
            normalised,
        )
        return " ".join(normalised.split())

    @staticmethod
    def _normalise_postcode(postcode: str | None) -> str | None:
        if not postcode:
            return None

        return postcode.replace(" ", "").upper()

    @staticmethod
    def _company_match_fields(
        company: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "registration_number": company.get("company_number"),
            "registered_name": company.get("title"),
            "registered_address": company.get("address"),
            "legal_form": company.get("company_type"),
            "entity_status": company.get("company_status"),
        }

    def _matched_company_result(
        self,
        company: dict[str, Any],
        match_status: str,
        score: float,
        evidence: list[str],
    ) -> dict[str, Any]:
        company_status = company.get("company_status")
        company_type = company.get("company_type")

        if match_status == "verified_corporate" and company_status != "active":
            match_status = "inactive"

        if (
            match_status == "verified_corporate"
            and company_type not in ALLOWED_COMPANY_TYPES
        ):
            match_status = "unsupported_legal_form"

        eligible = match_status == "verified_corporate"

        return {
            "registry_match_status": match_status,
            "registry": "gb_companies_house",
            "jurisdiction": "gb",
            **self._company_match_fields(company),
            "match_score": round(score, 3),
            "match_evidence": evidence,
            "subscriber_class": "corporate" if eligible else None,
            "active_confirmed_by": "gb_companies_house" if eligible else None,
            "outreach_eligible": eligible,
        }

    def _match_companies_house(
        self,
        business: dict[str, Any],
        search_results: dict[str, Any],
    ) -> dict[str, Any]:
        business_name = self._normalise_company_name(business["business_name"])
        business_postcode = self._normalise_postcode(business.get("postcode"))
        companies = search_results.get("items", [])

        exact_name = [
            company
            for company in companies
            if self._normalise_company_name(company.get("title", ""))
            == business_name
        ]
        exact_name_and_postcode = [
            company
            for company in exact_name
            if self._normalise_postcode(
                company.get("address", {}).get("postal_code")
            )
            == business_postcode
            and business_postcode is not None
        ]

        if len(exact_name_and_postcode) == 1:
            return self._matched_company_result(
                exact_name_and_postcode[0],
                "verified_corporate",
                1.0,
                ["exact_normalised_name", "exact_postcode"],
            )

        if len(exact_name_and_postcode) > 1 or len(exact_name) > 1:
            return self._unverified_company_result("ambiguous")

        if len(exact_name) == 1:
            return self._matched_company_result(
                exact_name[0],
                "review",
                1.0,
                ["exact_normalised_name"],
            )

        postcode_candidates = [
            company
            for company in companies
            if business_postcode is not None
            and self._normalise_postcode(
                company.get("address", {}).get("postal_code")
            )
            == business_postcode
        ]
        ranked_candidates = sorted(
            (
                (
                    SequenceMatcher(
                        None,
                        business_name,
                        self._normalise_company_name(company.get("title", "")),
                    ).ratio(),
                    company,
                )
                for company in postcode_candidates
            ),
            key=lambda candidate: candidate[0],
            reverse=True,
        )

        if ranked_candidates:
            score, company = ranked_candidates[0]
            next_score = (
                ranked_candidates[1][0]
                if len(ranked_candidates) > 1
                else 0.0
            )

            if score >= 0.9 and score - next_score >= 0.05:
                return self._matched_company_result(
                    company,
                    "review",
                    score,
                    ["similar_name", "exact_postcode"],
                )

        return self._unverified_company_result("unverified")

    @staticmethod
    def _unverified_company_result(status: str) -> dict[str, Any]:
        return {
            "registry_match_status": status,
            "registry": "gb_companies_house",
            "jurisdiction": "gb",
            "registration_number": None,
            "registered_name": None,
            "registered_address": None,
            "legal_form": None,
            "entity_status": None,
            "match_score": None,
            "match_evidence": [],
            "subscriber_class": None,
            "active_confirmed_by": None,
            "outreach_eligible": False,
        }

    def _enrich_from_companies_house(
        self,
        businesses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enriched = []

        for business in businesses:
            search_results = self._fetch_companies_house(
                business["business_name"]
            )
            registry_result = self._match_companies_house(
                business,
                search_results,
            )
            enriched.append(
                {
                    **business,
                    **registry_result,
                    "no_website": business.get("website") is None,
                }
            )

        return enriched

    def _fetch_companies_house(self, business_name: str) -> dict[str, Any]:
        api_key = os.getenv("COMPANIES_HOUSE_API_KEY")

        if not api_key:
            raise RuntimeError(
                "Environment variable COMPANIES_HOUSE_API_KEY is required"
            )

        cache_key = self._normalise_company_name(business_name)
        cached = self._companies_house_cache.get(cache_key)

        if cached is not None:
            return cached

        if self._last_companies_house_request_at is not None:
            elapsed = time.monotonic() - self._last_companies_house_request_at
            delay = COMPANIES_HOUSE_REQUEST_INTERVAL_SECONDS - elapsed

            if delay > 0:
                time.sleep(delay)

        try:
            response = requests.get(
                COMPANIES_HOUSE_URL,
                params={
                    "q": business_name,
                    "items_per_page": 10,
                },
                headers={"Accept": "application/json"},
                auth=(api_key, ""),
                timeout=(5, 15),
            )
            self._last_companies_house_request_at = time.monotonic()
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as error:
            raise RuntimeError(
                f"Unable to search Companies House for {business_name}"
            ) from error

        self._companies_house_cache[cache_key] = result
        return result


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", required=True)
    parser.add_argument("--country-iso", default="gb")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(arguments)

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")

    agent = ContactAgent()
    location = agent.resolve_location(args.location, args.country_iso)
    osm_data = agent.fetch_osm_data(location["bounding_box"])
    businesses = agent.extract_businesses(osm_data)

    if args.limit is not None:
        businesses = businesses[: args.limit]

    enriched = agent.enrich_legal_entities(businesses, args.country_iso)
    print(
        json.dumps(
            {
                "campaign_location": location,
                "businesses": enriched,
                "attribution": OSM_ATTRIBUTION,
            },
            indent=2,
        )
    )

if __name__ == "__main__":
    main()
