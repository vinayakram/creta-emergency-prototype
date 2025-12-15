from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_query_requires_ingest_or_returns_404():
    r = client.post("/query", json={"query": "dead battery jump start"})
    assert r.status_code in (200, 404)

    if r.status_code == 200:
        data = r.json()
        assert isinstance(data.get("steps"), list)
        assert isinstance(data.get("warnings"), list)
        assert isinstance(data.get("tools"), list)
        assert isinstance(data.get("sources"), list)
