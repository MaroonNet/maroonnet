"""Tracks: where each searcher radio has been, cut where the radio changed group."""

from people.tests.conftest import write


def report(radio_id: int, time: str, lat: float, lon: float) -> str:
    """One position report, as a row to write. time is the hour and minute, on the made-up
    mission's day."""
    stamp = f"2026-11-20T{time}:00Z"
    return f"INSERT INTO location (team_id, time, rx_time, lat, lon) VALUES ({radio_id}, '{stamp}', '{stamp}', {lat}, {lon});"


def tracks(client) -> dict[int, list[dict]]:
    """The pieces of each track of the open mission, by its radio's id."""
    response = client.get("/api/mission/tracks")
    assert response.status_code == 200, response.text
    return {track["radio_id"]: track["pieces"] for track in response.json()}


def test_a_mission_with_no_positions_has_no_tracks(client, bear_creek):
    assert client.get("/api/mission/tracks").json() == []


def test_a_track_is_its_radios_positions_in_time_order(client, bear_creek):
    write(bear_creek, report(1, "15:02", 39.52, -105.32) + report(1, "15:01", 39.51, -105.31)
          + report(1, "15:03", 39.53, -105.33))

    # Each point is longitude, then latitude: the order the map takes.
    assert tracks(client) == {1: [{"group_id": None, "points": [[-105.31, 39.51], [-105.32, 39.52], [-105.33, 39.53]]}]}


def test_each_radio_has_its_own_track(client, bear_creek):
    write(bear_creek, report(2, "15:01", 39.6, -105.4) + report(1, "15:01", 39.5, -105.3))

    assert tracks(client) == {
        1: [{"group_id": None, "points": [[-105.3, 39.5]]}],
        2: [{"group_id": None, "points": [[-105.4, 39.6]]}],
    }


def test_a_track_is_cut_where_its_radio_changed_group(client, bear_creek):
    """Radio 1 is in group 1 from 3:00 to 3:10, in group 2 from 3:10 to 3:20, and in none
    after. Each piece starts on the last point of the one before, so the line has no gap."""
    write(bear_creek, """
        INSERT INTO search_group (search_group_id) VALUES (1), (2);
        INSERT INTO team_group_assignment (team_id, search_group_id, from_time, to_time) VALUES
            (1, 1, '2026-11-20T15:00:00Z', '2026-11-20T15:10:00Z'),
            (1, 2, '2026-11-20T15:10:00Z', '2026-11-20T15:20:00Z');
    """ + report(1, "15:05", 39.1, -105.1) + report(1, "15:09", 39.2, -105.2) + report(1, "15:15", 39.3, -105.3)
          + report(1, "15:25", 39.4, -105.4) + report(1, "15:30", 39.5, -105.5))

    assert tracks(client)[1] == [
        {"group_id": 1, "points": [[-105.1, 39.1], [-105.2, 39.2]]},
        {"group_id": 2, "points": [[-105.2, 39.2], [-105.3, 39.3]]},
        {"group_id": None, "points": [[-105.3, 39.3], [-105.4, 39.4], [-105.5, 39.5]]},
    ]


def test_a_position_before_the_radio_joined_a_group_has_none(client, bear_creek):
    write(bear_creek, """
        INSERT INTO search_group (search_group_id) VALUES (1);
        INSERT INTO team_group_assignment (team_id, search_group_id, from_time) VALUES (1, 1, '2026-11-20T15:10:00Z');
    """ + report(1, "15:05", 39.1, -105.1) + report(1, "15:15", 39.2, -105.2))

    assert [piece["group_id"] for piece in tracks(client)[1]] == [None, 1]


def test_a_position_at_the_second_a_group_row_ends_is_still_in_that_group(client, bear_creek):
    """Ending a session closes every group row at the session's end time, and a radio can
    report in that same second."""
    write(bear_creek, """
        INSERT INTO search_group (search_group_id) VALUES (1);
        INSERT INTO team_group_assignment (team_id, search_group_id, from_time, to_time) VALUES
            (1, 1, '2026-11-20T15:00:00Z', '2026-11-20T15:10:00Z');
    """ + report(1, "15:05", 39.1, -105.1) + report(1, "15:10", 39.2, -105.2))

    assert tracks(client)[1] == [{"group_id": 1, "points": [[-105.1, 39.1], [-105.2, 39.2]]}]


def test_at_the_second_a_radio_changes_group_it_is_in_the_new_one(client, bear_creek):
    write(bear_creek, """
        INSERT INTO search_group (search_group_id) VALUES (1), (2);
        INSERT INTO team_group_assignment (team_id, search_group_id, from_time, to_time) VALUES
            (1, 1, '2026-11-20T15:00:00Z', '2026-11-20T15:10:00Z'),
            (1, 2, '2026-11-20T15:10:00Z', NULL);
    """ + report(1, "15:05", 39.1, -105.1) + report(1, "15:10", 39.2, -105.2))

    assert [piece["group_id"] for piece in tracks(client)[1]] == [1, 2]


def test_only_a_searcher_radio_has_a_track(client, bear_creek):
    """Radio 4 is the command post's."""
    write(bear_creek, report(4, "15:01", 39.5, -105.3))

    assert tracks(client) == {}


def test_arizona07_has_six_tracks(client, arizona07):
    client.post("/api/missions/952592f8-f48b-4310-aa51-3abcefc02005/open")

    found = tracks(client)

    def groups(radio_id: int) -> list[int | None]:
        return [piece["group_id"] for piece in found[radio_id]]

    assert sorted(found) == [1, 2, 3, 4, 5, 7]
    assert groups(1) == [1] and groups(2) == [1] and groups(5) == [3] and groups(7) == [2]
    assert groups(3) == [1, 3]     # moved to Group 3 at 1:24 am
    assert groups(4) == [2, None]  # left Group 2 at 11:25 pm
    # Every report of the six radios is on a track; a piece after the first repeats one point.
    points = sum(len(piece["points"]) for pieces in found.values() for piece in pieces)
    assert points == 1872 + 1902 + 1984 + 1069 + 1859 + 1656 + 2
