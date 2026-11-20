from modules.radio_service import RADIO_STATIONS, public_station, split_stream_title


def test_exact_kazakhstan_catalog_and_subgroups():
    kz = [station for station in RADIO_STATIONS if station["country"] == "KZ"]
    assert len(kz) == 20
    assert len({station["id"] for station in kz}) == 20
    assert sum(station["subgroup"] == "pop" for station in kz) == 10
    assert sum(station["subgroup"] == "niche" for station in kz) == 6
    assert sum(station["subgroup"] == "talk" for station in kz) == 4


def test_public_station_hides_origin_url():
    public = public_station(RADIO_STATIONS[1])
    assert "url" not in public
    assert "source" not in public
    assert public["stream_url"].startswith("/api/music/radio/stream/")


def test_unconfirmed_stream_is_disabled():
    public = public_station(RADIO_STATIONS[0])
    assert public["available"] is False
    assert public["stream_url"] is None
    assert public["unavailableReason"]


def test_stream_title_parser():
    assert split_stream_title("Мираж - Музыка нас связала") == ("Мираж", "Музыка нас связала")
    assert split_stream_title("Новости") == (None, "Новости")
    assert split_stream_title("") == (None, None)
