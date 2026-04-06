from __future__ import annotations

from dataclasses import dataclass

import requests
from django.conf import settings

GOOGLE_PLACES_AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"


class GooglePlacesError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlaceSuggestion:
    text: str
    place_id: str = ""


def autocomplete_cities(
    query: str,
    *,
    country_code: str = "",
    session_token: str = "",
    requests_session=None,
) -> list[PlaceSuggestion]:
    query = (query or "").strip()
    if len(query) < 2:
        return []
    api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        raise GooglePlacesError("Google Places API key is not configured.")

    payload: dict[str, object] = {
        "input": query,
        "includedPrimaryTypes": ["(cities)"],
    }
    normalized_country_code = (country_code or "").strip().lower()
    if normalized_country_code:
        payload["includedRegionCodes"] = [normalized_country_code]
    if session_token:
        payload["sessionToken"] = session_token

    session = requests_session or requests
    response = session.post(
        GOOGLE_PLACES_AUTOCOMPLETE_URL,
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "suggestions.placePrediction.placeId,suggestions.placePrediction.text.text",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )
    if response.status_code >= 400:
        raise GooglePlacesError(f"Google Places request failed with status {response.status_code}.")
    body = response.json()
    suggestions: list[PlaceSuggestion] = []
    for item in body.get("suggestions", []):
        prediction = item.get("placePrediction") or {}
        text = ((prediction.get("text") or {}).get("text") or "").strip()
        if not text:
            continue
        suggestions.append(
            PlaceSuggestion(
                text=text,
                place_id=(prediction.get("placeId") or "").strip(),
            )
        )
    return suggestions
