from __future__ import annotations

from dataclasses import dataclass
import os

from .http import PoliteHttpClient
from .normalizers import clean_text, safe_float


@dataclass(slots=True, frozen=True)
class GeocodeResult:
    provider: str
    query_address: str
    matched_address: str
    latitude: float
    longitude: float
    precision: str


class KakaoAddressGeocoder:
    """Geocode public venue addresses; never receives a user's live position."""

    ENDPOINT = "https://dapi.kakao.com/v2/local/search/address.json"
    provider = "kakao_local"

    def __init__(self, rest_api_key: str | None = None) -> None:
        self.rest_api_key = (rest_api_key or os.getenv("KAKAO_REST_API_KEY", "")).strip()

    def available(self) -> tuple[bool, str | None]:
        if not self.rest_api_key:
            return False, "KAKAO_REST_API_KEY is not set"
        return True, None

    def geocode(
        self,
        client: PoliteHttpClient,
        address: str,
    ) -> GeocodeResult | None:
        if not self.rest_api_key:
            raise RuntimeError("KAKAO_REST_API_KEY is required")
        payload = client.get_json(
            self.ENDPOINT,
            params={"query": address, "analyze_type": "similar", "size": 1},
            headers={"Authorization": f"KakaoAK {self.rest_api_key}"},
        )
        documents = payload.get("documents") or []
        if not documents:
            return None
        document = documents[0]
        latitude = safe_float(document.get("y"))
        longitude = safe_float(document.get("x"))
        if latitude is None or longitude is None:
            return None
        road = document.get("road_address") or {}
        parcel = document.get("address") or {}
        matched = (
            clean_text(road.get("address_name"))
            or clean_text(parcel.get("address_name"))
            or clean_text(document.get("address_name"))
            or address
        )
        precision = "building" if road.get("building_name") else "address"
        return GeocodeResult(
            provider=self.provider,
            query_address=address,
            matched_address=matched,
            latitude=latitude,
            longitude=longitude,
            precision=precision,
        )
