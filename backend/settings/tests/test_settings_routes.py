"""The settings routes, tested through the web addresses the web app calls."""

import json

from fastapi.testclient import TestClient

from maps.folders import app_data_folder
from server.main import app

client = TestClient(app)


def test_each_test_gets_its_own_app_data_folder(data_dir):
    # The guard that keeps tests away from the real settings file.
    assert app_data_folder() == data_dir


def test_with_no_settings_file_the_starting_values_are_read():
    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {"units": "imperial"}


def test_a_changed_setting_is_answered_saved_in_the_app_data_folder_and_read_back(data_dir):
    response = client.patch("/api/settings", json={"units": "metric"})

    assert response.status_code == 200
    assert response.json() == {"units": "metric"}
    # The app data folder did not exist before the change, so the change made it.
    assert json.loads((data_dir / "settings.json").read_text(encoding="utf-8")) == {"units": "metric"}
    # Each read comes from the file, so this is also what a restarted backend answers.
    assert client.get("/api/settings").json() == {"units": "metric"}


def test_a_value_the_setting_does_not_offer_is_refused_and_nothing_is_saved(data_dir):
    response = client.patch("/api/settings", json={"units": "furlongs"})

    assert response.status_code == 422  # the request was understood but its contents are wrong
    assert not (data_dir / "settings.json").exists()
    assert client.get("/api/settings").json() == {"units": "imperial"}


def test_a_name_that_is_not_a_setting_is_refused_and_nothing_is_saved(data_dir):
    response = client.patch("/api/settings", json={"unitz": "metric"})

    assert response.status_code == 422
    assert not (data_dir / "settings.json").exists()


def test_a_change_that_names_no_setting_leaves_them_as_they_were():
    client.patch("/api/settings", json={"units": "metric"})

    response = client.patch("/api/settings", json={})

    assert response.json() == {"units": "metric"}
    assert client.get("/api/settings").json() == {"units": "metric"}


def test_a_damaged_settings_file_reads_as_the_starting_values_and_says_so(data_dir, capsys):
    data_dir.mkdir()
    (data_dir / "settings.json").write_text('{"units": "met', encoding="utf-8")  # cut off part way

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {"units": "imperial"}
    assert "settings.json could not be read" in capsys.readouterr().out


def test_a_value_the_file_should_not_hold_counts_as_damage(data_dir, capsys):
    data_dir.mkdir()
    (data_dir / "settings.json").write_text('{"units": "furlongs"}', encoding="utf-8")

    assert client.get("/api/settings").json() == {"units": "imperial"}
    assert "settings.json could not be read" in capsys.readouterr().out


def test_the_next_change_replaces_a_damaged_settings_file(data_dir):
    data_dir.mkdir()
    (data_dir / "settings.json").write_text("not settings at all", encoding="utf-8")

    client.patch("/api/settings", json={"units": "metric"})

    assert json.loads((data_dir / "settings.json").read_text(encoding="utf-8")) == {"units": "metric"}
