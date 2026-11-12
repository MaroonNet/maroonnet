from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_client_log_prints_the_message_and_the_browser(capsys):
    response = client.post("/api/client-log", json={"kind": "error", "detail": "style failed"},
                           headers={"User-Agent": "Safari"})

    assert response.status_code == 204
    assert "CLIENT error from Safari:\nstyle failed" in capsys.readouterr().out
