from __future__ import annotations

from kids_experience_radar.geocoding import KakaoAddressGeocoder
from kids_experience_radar.models import Event
from kids_experience_radar.store import EventStore


class KakaoClient:
    def __init__(self) -> None:
        self.headers: dict[str, str] | None = None

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        assert params == {
            "query": "서울특별시 종로구 세종대로 1",
            "analyze_type": "similar",
            "size": 1,
        }
        self.headers = headers
        return {
            "documents": [
                {
                    "x": "126.9780",
                    "y": "37.5665",
                    "road_address": {
                        "address_name": "서울 종로구 세종대로 1",
                        "building_name": "어린이체험관",
                    },
                    "address": {"address_name": "서울 종로구 세종로 1"},
                }
            ]
        }


def test_kakao_geocoder_maps_coordinates_without_user_location() -> None:
    geocoder = KakaoAddressGeocoder("secret-test-key")
    client = KakaoClient()

    result = geocoder.geocode(  # type: ignore[arg-type]
        client,
        "서울특별시 종로구 세종대로 1",
    )

    assert result is not None
    assert result.latitude == 37.5665
    assert result.longitude == 126.978
    assert result.precision == "building"
    assert client.headers == {"Authorization": "KakaoAK secret-test-key"}


def test_geocoding_cache_updates_all_events_for_same_public_venue(tmp_path) -> None:
    database = tmp_path / "radar.sqlite3"
    address = "서울특별시 종로구 세종대로 1"
    with EventStore(database) as store:
        store.upsert_events(
            [
                Event(
                    source_id="one",
                    source_name="one",
                    external_id="1",
                    title="어린이 체험",
                    detail_url="https://example.org/1",
                    address=address,
                ),
                Event(
                    source_id="two",
                    source_name="two",
                    external_id="2",
                    title="가족 교육",
                    detail_url="https://example.org/2",
                    address=address,
                ),
            ]
        )
        assert store.missing_addresses() == [address]

        updated = store.apply_geocode(
            provider="kakao_local",
            query_address=address,
            matched_address="서울 종로구 세종대로 1",
            latitude=37.5665,
            longitude=126.978,
            precision="building",
        )

        assert updated == 2
        assert store.missing_addresses() == []
        cached = store.cached_geocode("kakao_local", address)
        assert cached is not None
        assert cached["latitude"] == 37.5665

        store.upsert_events(
            [
                Event(
                    source_id="one",
                    source_name="one",
                    external_id="1",
                    title="어린이 체험",
                    detail_url="https://example.org/1",
                    address=address,
                )
            ]
        )
        row = store.connection.execute(
            "SELECT latitude, longitude FROM events WHERE source_id = 'one'"
        ).fetchone()
        assert row["latitude"] == 37.5665
        assert row["longitude"] == 126.978
