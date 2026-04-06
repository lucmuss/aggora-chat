from __future__ import annotations

from dataclasses import dataclass

import requests
from django.conf import settings

GOOGLE_PLACES_AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
GOOGLE_PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"


class GooglePlacesError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlaceSuggestion:
    text: str
    place_id: str = ""


def _normalize_place_text(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _extract_region_from_place(body: dict) -> str:
    for component in body.get("addressComponents", []):
        types = set(component.get("types") or [])
        if "administrative_area_level_1" in types:
            return (component.get("longText") or component.get("shortText") or "").strip()
    return ""


def _load_place_region(place_id: str, *, api_key: str, session) -> str:
    if not place_id:
        return ""
    response = session.get(
        GOOGLE_PLACE_DETAILS_URL.format(place_id=place_id),
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "addressComponents",
        },
        timeout=10,
    )
    if response.status_code >= 400:
        return ""
    return _extract_region_from_place(response.json())


def autocomplete_cities(
    query: str,
    *,
    country_code: str = "",
    country_name: str = "",
    region: str = "",
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
    normalized_region = _normalize_place_text(region)
    if normalized_region and suggestions and hasattr(session, "get"):
        indexed_suggestions = list(enumerate(suggestions))
        scored = []
        for index, suggestion in indexed_suggestions[:8]:
            region_name = _normalize_place_text(_load_place_region(suggestion.place_id, api_key=api_key, session=session))
            score = 0 if region_name and region_name == normalized_region else 1
            scored.append((score, index, suggestion))
        if scored and any(score == 0 for score, _, _ in scored):
            ranked = [suggestion for _, _, suggestion in sorted(scored, key=lambda item: (item[0], item[1]))]
            ranked_ids = {suggestion.place_id for suggestion in ranked}
            suggestions = ranked + [suggestion for suggestion in suggestions if suggestion.place_id not in ranked_ids]
    return suggestions
