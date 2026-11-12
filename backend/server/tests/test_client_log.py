from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_client_log_prints_the_message(capsys):
    response = client.post("/api/client-log", json={"kind": "error", "detail": "style failed"})

    assert response.status_code == 204
    assert "CLIENT error: style failed" in capsys.readouterr().out
