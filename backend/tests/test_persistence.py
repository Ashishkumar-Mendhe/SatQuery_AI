from __future__ import annotations

from collections.abc import Generator

import pytest
from starlette.testclient import TestClient

from satquery.main import create_app


@pytest.fixture
def client() -> Generator[TestClient]:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_workspaces_crud_lifecycle(client: TestClient) -> None:
    # 1. List workspaces
    resp = client.get("/api/v1/workspaces")
    assert resp.status_code == 200
    initial_list = resp.json()
    assert isinstance(initial_list, list)

    # 2. Create workspace
    create_resp = client.post(
        "/api/v1/workspaces",
        json={"name": "Test Bangalore Workspace", "state": "active"},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "Test Bangalore Workspace"
    ws_id = created["id"]

    # 3. Save AOI for workspace
    aoi_payload = {
        "name": "Bellandur Lake",
        "source": "polygon",
        "area_sqkm": 9.64,
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.65, 12.92],
                    [77.68, 12.92],
                    [77.68, 12.95],
                    [77.65, 12.95],
                    [77.65, 12.92],
                ]
            ],
        },
        "bounds": [77.65, 12.92, 77.68, 12.95],
        "workspace_id": ws_id,
    }
    aoi_resp = client.post("/api/v1/aois", json=aoi_payload)
    assert aoi_resp.status_code == 201
    saved_aoi = aoi_resp.json()
    assert saved_aoi["name"] == "Bellandur Lake"
    assert saved_aoi["workspace_id"] == ws_id
    aoi_id = saved_aoi["id"]

    # 4. List saved AOIs
    list_aois_resp = client.get("/api/v1/aois")
    assert list_aois_resp.status_code == 200
    aois = list_aois_resp.json()
    assert any(a["id"] == aoi_id for a in aois)

    # 5. Record analysis history
    history_payload = {
        "analysis_type": "change_detection",
        "title": "Bi-temporal NDVI Vegetation Differencing",
        "query_text": "What vegetation changes occurred?",
        "result": {"loss_pixels": 450, "gain_pixels": 120, "shared_valid": 10000},
        "workspace_id": ws_id,
    }
    hist_resp = client.post("/api/v1/history", json=history_payload)
    assert hist_resp.status_code == 201
    saved_hist = hist_resp.json()
    assert saved_hist["title"] == "Bi-temporal NDVI Vegetation Differencing"
    hist_id = saved_hist["id"]

    # 6. List history
    list_hist_resp = client.get("/api/v1/history")
    assert list_hist_resp.status_code == 200
    history_items = list_hist_resp.json()
    assert any(h["id"] == hist_id for h in history_items)

    # 7. Clean up
    del_aoi_resp = client.delete(f"/api/v1/aois/{aoi_id}")
    assert del_aoi_resp.status_code == 204

    del_hist_resp = client.delete(f"/api/v1/history/{hist_id}")
    assert del_hist_resp.status_code == 204

    del_ws_resp = client.delete(f"/api/v1/workspaces/{ws_id}")
    assert del_ws_resp.status_code == 204
