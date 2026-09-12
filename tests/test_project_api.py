import io
from flask import Flask
from kds.api import register_project_api
from kds.data.project_store import FileProjectStore


def test_project_api_end_to_end(tmp_path):
    app = Flask(__name__)
    register_project_api(app, FileProjectStore(tmp_path))
    with app.test_client() as client:
        response = client.post("/api/v2/projects", json={"id": "example", "name": "Example", "planning_year": 2024,
                                                       "annual_water_budget": 100, "water_budget_unit": "m3"})
        assert response.status_code == 201
        assert len(client.get("/api/v2/projects").json["projects"]) == 1
        root = "/api/v2/projects/example"
        batch = client.post(root + "/imports", data={"data_type": "analysis_units", "file":
            (io.BytesIO(b"external_id,settlement,area_da,current_crop\nA,Example,10,Wheat"), "units.csv")})
        assert batch.status_code == 201
        batch_url = root + "/imports/" + batch.json["id"]
        assert client.get(batch_url).json["row_count"] == 1
        assert client.get(root + "/analysis-units").json["count"] == 0
        assert client.post(batch_url + "/confirm", json={}).status_code == 400
        assert client.post(batch_url + "/confirm", json={"confirm": True}).status_code == 409
        assert client.post(batch_url + "/mapping", json={"mapping": batch.json["mapping"]}).status_code == 200
        assert client.post(batch_url + "/confirm", json={"confirm": True, "acknowledge_warnings": True}).status_code == 200
        assert client.get(root + "/analysis-units").json["count"] == 1
        assert client.get(root).json["data_revision"] == 1
        assert client.get(root + "/crops").status_code == 200
        assert client.get(root + "/economics").status_code == 200
        assert client.get(root + "/analysis-units?limit=0").status_code == 400
        assert client.get("/api/v2/projects/unknown").status_code == 404
        assert client.post(root + "/imports", data={"data_type": "crops", "options": "{bad", "file":
            (io.BytesIO(b"crop_name\nWheat"), "crops.csv")}).status_code == 400


def test_bad_project_payload_returns_400(tmp_path):
    app = Flask(__name__)
    register_project_api(app, FileProjectStore(tmp_path))
    with app.test_client() as client:
        assert client.post("/api/v2/projects", json=[]).status_code == 400
        assert client.post("/api/v2/projects", json={}).status_code == 400
