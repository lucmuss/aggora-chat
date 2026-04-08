import pytest
from django.test import override_settings

from apps.accounts.google_places import GooglePlacesError, autocomplete_cities


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class DummySession:
    def __init__(self, response, detail_response=None):
        self.response = response
        self.detail_response = detail_response or DummyResponse(payload={})
        self.calls = []
        self.detail_calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return self.response

    def get(self, url, headers=None, timeout=None):
        self.detail_calls.append({"url": url, "headers": headers, "timeout": timeout})
        return self.detail_response


@pytest.mark.django_db
class TestGooglePlacesService:
    @override_settings(GOOGLE_PLACES_API_KEY="test-key")
    def test_autocomplete_cities_returns_text_suggestions(self):
        session = DummySession(
            DummyResponse(
                payload={
                    "suggestions": [
                        {
                            "placePrediction": {
                                "placeId": "abc123",
                                "text": {"text": "Berlin, Germany"},
                            }
                        }
                    ]
                }
            )
        )

        suggestions = autocomplete_cities(
            "Berlin",
            country_code="de",
            country_name="Germany",
            region="Berlin",
            requests_session=session,
        )

        assert [item.text for item in suggestions] == ["Berlin, Germany"]
        assert session.calls[0]["json"]["includedRegionCodes"] == ["de"]
        assert session.calls[0]["json"]["includedPrimaryTypes"] == ["(cities)"]
        assert session.calls[0]["json"]["input"] == "Berlin"

    @override_settings(GOOGLE_PLACES_API_KEY="")
    def test_autocomplete_cities_requires_api_key(self):
        with pytest.raises(GooglePlacesError):
            autocomplete_cities("Berlin")

    @override_settings(GOOGLE_PLACES_API_KEY="test-key")
    def test_autocomplete_cities_raises_for_google_error(self):
        session = DummySession(DummyResponse(status_code=403, payload={"error": {"message": "Forbidden"}}))

        with pytest.raises(GooglePlacesError):
            autocomplete_cities("Berlin", requests_session=session)

    @override_settings(GOOGLE_PLACES_API_KEY="test-key")
    def test_autocomplete_cities_prioritizes_matching_region(self):
        session = DummySession(
            DummyResponse(
                payload={
                    "suggestions": [
                        {
                            "placePrediction": {
                                "placeId": "munster",
                                "text": {"text": "Münster, Germany"},
                            }
                        },
                        {
                            "placePrediction": {
                                "placeId": "munich",
                                "text": {"text": "Munich, Germany"},
                            }
                        },
                    ]
                }
            )
        )

        def fake_get(url, headers=None, timeout=None):
            session.detail_calls.append({"url": url, "headers": headers, "timeout": timeout})
            if url.endswith("/munster"):
                return DummyResponse(payload={"addressComponents": [{"longText": "North Rhine-Westphalia", "types": ["administrative_area_level_1"]}]})
            return DummyResponse(payload={"addressComponents": [{"longText": "Bavaria", "types": ["administrative_area_level_1"]}]})

        session.get = fake_get

        suggestions = autocomplete_cities(
            "mun",
            country_code="de",
            country_name="Germany",
            region="Bavaria",
            requests_session=session,
        )

        assert [item.text for item in suggestions][:2] == ["Munich, Germany", "Münster, Germany"]
