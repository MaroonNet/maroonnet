"""The radio list, radios.json, and the radios a new mission starts with."""

import json

from mission.tests.conftest import rows
from teams.radio_list import read_radio_list


def kinds(radios) -> list[str]:
    return [radio.kind.value for radio in radios]


def test_a_missing_file_is_written_with_eight_invented_radios(data_dir):
    radios = read_radio_list()

    assert kinds(radios) == ["searcher"] * 6 + ["command_post", "relay"]
    assert len({radio.node_num for radio in radios}) == 8
    saved = json.loads((data_dir / "radios.json").read_text(encoding="utf-8"))
    assert saved == [{"node_num": radio.node_num, "kind": radio.kind.value} for radio in radios]


def test_a_file_edited_by_hand_is_read_as_it_is(data_dir):
    data_dir.mkdir()
    (data_dir / "radios.json").write_text(
        '[{"node_num": 3663644600, "kind": "searcher"}, {"node_num": 7, "kind": "relay"}]', encoding="utf-8")

    radios = read_radio_list()

    assert [(radio.node_num, radio.kind.value) for radio in radios] == [(3663644600, "searcher"), (7, "relay")]


def test_a_node_number_listed_twice_counts_once(data_dir):
    data_dir.mkdir()
    (data_dir / "radios.json").write_text(
        '[{"node_num": 7, "kind": "searcher"}, {"node_num": 7, "kind": "relay"}]', encoding="utf-8")

    assert [(radio.node_num, radio.kind.value) for radio in read_radio_list()] == [(7, "searcher")]


def test_a_damaged_file_reads_as_the_invented_radios_and_is_left_alone(data_dir, capsys):
    data_dir.mkdir()
    (data_dir / "radios.json").write_text('[{"node_num": 7, "kind": "balloon"}]', encoding="utf-8")

    assert kinds(read_radio_list()) == ["searcher"] * 6 + ["command_post", "relay"]
    assert "RADIOS radios.json could not be read" in capsys.readouterr().out
    assert "balloon" in (data_dir / "radios.json").read_text(encoding="utf-8")


def test_a_new_mission_has_each_listed_radio_with_nobody_on_it(client, missions_dir):
    radios = read_radio_list()

    mission = client.post("/api/missions", json={"name": "Bear Creek", "time_zone": "America/Denver"}).json()

    file = missions_dir / f"bear-creek-{mission['id'][:8]}" / "session-01.sqlite3"
    assert rows(file, "SELECT team_id, node_num, kind FROM team ORDER BY team_id") == [
        (number, radio.node_num, radio.kind.value) for number, radio in enumerate(radios, start=1)
    ]
    assert rows(file, "SELECT count(*) FROM searcher_team_assignment") == [(0,)]
    assert rows(file, "SELECT count(*) FROM search_group") == [(0,)]
