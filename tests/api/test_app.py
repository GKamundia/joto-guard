import pytest
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from api.app import DEFAULT_ORIGINS, create_app
from conduit_sentinel.pipeline import run, write_outputs


@pytest.fixture(scope="module")
def processed(tmp_path_factory, fixtures_dir, config):
    """The pipeline's outputs for the two small fixture exports."""
    out = tmp_path_factory.mktemp("processed")
    write_outputs(
        run(
            [fixtures_dir / "conduit_part_a.csv", fixtures_dir / "conduit_part_b.csv"],
            config,
        ),
        out,
    )
    return out


@pytest.fixture
def client(processed):
    return TestClient(create_app(processed))


def test_index_lists_the_endpoints(client):
    body = client.get("/").json()

    assert body["service"] == "Conduit Sentinel"
    assert "/v1/station-health" in body["endpoints"]
    assert body["documentation"] == "/docs"


def test_stations(client):
    stations = client.get("/v1/stations").json()

    assert len(stations) == 1
    station = stations[0]
    assert station["station_id"] == 61
    assert (station["latitude"], station["longitude"]) == (-1.099736, 37.014528)
    assert station["attribution"] == "3d-fewsnet.icdp.ucar.edu"
    assert station["record_start_utc"] == "2026-08-28T00:00:25Z"
    assert station["latest_health"]["score"] == 80.0
    assert station["export_windows"] == [
        {"start_utc": "2026-08-28T00:00:25Z", "end_utc": "2026-08-28T00:09:50Z"}
    ]


def test_station_health_serves_the_whole_report(client):
    report = client.get("/v1/station-health").json()

    assert report["station"]["station_id"] == 61
    assert set(report) >= {"coverage", "health", "channel_status", "audits", "recommendations"}
    assert report["health"]["rule"].startswith("score = max(0, 100")


def test_qc_returns_the_most_recent_days(client):
    body = client.get("/v1/qc", params={"days": 1}).json()

    assert body["days"] == ["2026-08-28"]
    assert [row["date_utc"] for row in body["health"]] == ["2026-08-28"]
    assert {row["group"] for row in body["channel_status"]} >= {"battery", "wind_gust_dir"}
    assert body["empty_channels"] == ["battery_voltage"]
    assert body["rules"]["R12"].startswith("Channel empty")


def test_history_returns_a_series_with_its_unit(client):
    body = client.get("/v1/history", params={"var": "t_sht_c"}).json()

    assert body["variable"] == "t_sht_c"
    assert body["unit"] == "°C"
    assert body["n_hours"] == 1
    assert body["truncated"] is False
    point = body["series"][0]
    assert point["hour_utc"] == "2026-08-28T00:00:00Z"
    assert (point["n_obs"], point["coverage_pct"]) == (10, 16.7)
    # ten minutes is under half the hour, so Sentinel publishes no value for it
    assert point["t_sht_c"] is None


def test_history_can_be_limited_to_a_period(client):
    empty = client.get(
        "/v1/history", params={"var": "t_sht_c", "start": "2026-09-01T00:00:00Z"}
    ).json()

    assert empty["n_hours"] == 0
    assert empty["series"] == []


@pytest.mark.parametrize("variable", ["nope", "hour_utc", "health_code"])
def test_history_refuses_a_variable_it_does_not_hold(client, variable):
    response = client.get("/v1/history", params={"var": variable})

    assert response.status_code == 404
    assert "t_sht_c" in response.json()["detail"]["available"]


def test_dataset_download(client):
    response = client.get("/v1/dataset/health_daily.csv")

    assert response.status_code == 200
    assert response.text.splitlines()[0].startswith("station_id,date_utc,score")

    unknown = client.get("/v1/dataset/secrets.env")
    assert unknown.status_code == 404
    assert "obs_qc.csv" in unknown.json()["detail"]["available"]


def test_without_outputs_the_api_says_what_to_run(tmp_path):
    response = TestClient(create_app(tmp_path)).get("/v1/stations")

    assert response.status_code == 503
    assert "python -m conduit_sentinel" in response.json()["detail"]


def test_rerunning_the_pipeline_refreshes_the_api(processed, fixtures_dir, config):
    client = TestClient(create_app(processed))
    assert client.get("/v1/stations").json()[0]["n_obs"] == 10

    write_outputs(run([fixtures_dir / "conduit_part_a.csv"], config), processed)

    assert client.get("/v1/stations").json()[0]["n_obs"] == 6


def test_the_deployed_web_origin_can_be_set_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "JOTO_ALLOWED_ORIGINS", "https://joto-guard.vercel.app, http://localhost:5173"
    )
    app = create_app(data_dir=tmp_path)

    allowed = next(
        middleware.kwargs["allow_origins"]
        for middleware in app.user_middleware
        if middleware.cls is CORSMiddleware
    )
    assert allowed == ["https://joto-guard.vercel.app", "http://localhost:5173"]


def test_without_that_setting_only_the_local_vite_server_may_call(tmp_path):
    app = create_app(data_dir=tmp_path)

    allowed = next(
        middleware.kwargs["allow_origins"]
        for middleware in app.user_middleware
        if middleware.cls is CORSMiddleware
    )
    assert allowed == list(DEFAULT_ORIGINS)
