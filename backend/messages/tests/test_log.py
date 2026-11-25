"""The log: the open session's messages, one line for each send, and its sector events."""

from people.tests.conftest import write


def message(radio_id: int, time: str, direction: str, text: str, type_code: str = "instruction",
            addressing: str = "direct", batch_id: int | None = None, ack: str | None = None) -> str:
    """One message row to write. time and ack are the hour, minute and second, on the
    made-up mission's day."""
    stamp = f"'2026-11-20T{time}Z'"
    acked = f"'2026-11-20T{ack}Z'" if ack else "NULL"
    return (
        "INSERT INTO message (team_id, time, rx_time, direction, type_code, text, addressing, batch_id, ack_time) "
        f"VALUES ({radio_id}, {stamp}, {stamp}, '{direction}', '{type_code}', '{text}', '{addressing}', "
        f"{batch_id if batch_id is not None else 'NULL'}, {acked});"
    )


SECTORS = """
    INSERT INTO search_group (search_group_id) VALUES (1), (2);
    INSERT INTO search_sector (search_sector_id, name, status, created_time, completed_time) VALUES
        (1, 'S1', 'completed', '2026-11-20T15:00:00Z', '2026-11-20T16:30:00Z'),
        (2, 'S2', 'partial', '2026-11-20T15:00:00Z', NULL),
        (3, 'S3', 'drawn', '2026-11-20T15:00:00Z', NULL);
"""


def held(sector_id: int, group_id: int, from_time: str, to_time: str | None = None) -> str:
    """One row of a group holding a sector, to write."""
    until = f"'2026-11-20T{to_time}Z'" if to_time else "NULL"
    return (
        "INSERT INTO sector_assignment (search_sector_id, search_group_id, from_time, to_time) "
        f"VALUES ({sector_id}, {group_id}, '2026-11-20T{from_time}Z', {until});"
    )


def log(client) -> list[dict]:
    response = client.get("/api/mission/log")
    assert response.status_code == 200, response.text
    return response.json()


def test_a_mission_with_no_messages_and_no_sectors_has_an_empty_log(client, bear_creek):
    assert log(client) == []


def test_a_message_to_one_radio_is_a_line_with_when_it_was_acknowledged(client, bear_creek):
    write(bear_creek, message(2, "15:10:00", "out", "Hold at the creek.", ack="15:10:09"))

    assert log(client) == [{
        "kind": "message", "id": 1, "time": "2026-11-20T15:10:00Z", "type": "instruction",
        "direction": "out", "addressing": "direct", "text": "Hold at the creek.",
        "radios": [{"radio_id": 2, "ack_time": "2026-11-20T15:10:09Z"}],
    }]


def test_a_message_not_yet_acknowledged_has_no_acknowledgement_time(client, bear_creek):
    write(bear_creek, message(2, "15:10:00", "out", "Hold at the creek."))

    assert log(client)[0]["radios"] == [{"radio_id": 2, "ack_time": None}]


def test_a_message_from_a_radio_names_that_radio(client, bear_creek):
    write(bear_creek, message(3, "15:12:00", "in", "Boot print by the bridge.", type_code="evidence"))

    line = log(client)[0]

    assert (line["direction"], line["type"], line["radios"]) == ("in", "evidence", [{"radio_id": 3, "ack_time": None}])


def test_the_rows_of_one_send_are_one_line_listing_each_radio(client, bear_creek):
    """One send to radios 1 and 3 is saved as two rows that share a batch_id, the id of the
    first of them."""
    write(bear_creek, message(3, "15:10:00", "out", "Return to base.", "instruction", "multicast", 1, ack="15:10:12")
          + message(1, "15:10:00", "out", "Return to base.", "instruction", "multicast", 1))

    assert log(client) == [{
        "kind": "message", "id": 1, "time": "2026-11-20T15:10:00Z", "type": "instruction",
        "direction": "out", "addressing": "multicast", "text": "Return to base.",
        "radios": [{"radio_id": 1, "ack_time": None}, {"radio_id": 3, "ack_time": "2026-11-20T15:10:12Z"}],
    }]


def test_two_sends_of_the_same_words_are_two_lines(client, bear_creek):
    """Rows are joined by their batch_id, never by matching words."""
    write(bear_creek, message(1, "15:10:00", "out", "Check in.", addressing="broadcast", batch_id=1)
          + message(2, "15:10:00", "out", "Check in.", addressing="broadcast", batch_id=1)
          + message(1, "15:40:00", "out", "Check in.", addressing="broadcast", batch_id=3)
          + message(2, "15:40:00", "out", "Check in.", addressing="broadcast", batch_id=3))

    assert [(line["id"], len(line["radios"])) for line in log(client)] == [(1, 2), (3, 2)]


def test_a_sector_given_to_a_group_is_an_assigned_line(client, bear_creek):
    write(bear_creek, SECTORS + held(3, 2, "15:50:00"))

    assert log(client) == [{
        "kind": "sector", "id": 1, "time": "2026-11-20T15:50:00Z", "event": "assigned",
        "sector_id": 3, "sector_name": "S3", "group_id": 2, "partial": False,
    }]


def test_an_assignment_that_ended_when_the_sector_was_completed_is_a_completed_line(client, bear_creek):
    write(bear_creek, SECTORS + held(1, 1, "15:50:00", "16:30:00"))

    assert [(line["event"], line["time"], line["partial"]) for line in log(client)] == [
        ("assigned", "2026-11-20T15:50:00Z", False),
        ("completed", "2026-11-20T16:30:00Z", False),
    ]


def test_an_assignment_that_ended_otherwise_is_a_released_line(client, bear_creek):
    """S3 was taken back before anyone entered it, so it is still Drawn."""
    write(bear_creek, SECTORS + held(3, 2, "15:50:00", "16:10:00"))

    assert [(line["event"], line["partial"]) for line in log(client)] == [("assigned", False), ("released", False)]


def test_a_released_line_says_when_the_sector_is_partial(client, bear_creek):
    write(bear_creek, SECTORS + held(2, 2, "15:50:00", "16:10:00"))

    assert [(line["event"], line["partial"]) for line in log(client)] == [("assigned", False), ("released", True)]


def test_a_sector_released_and_later_completed_has_a_line_for_each(client, bear_creek):
    """Group 2 left S1 at 4:00 pm; group 1 took it and completed it at 4:30 pm."""
    write(bear_creek, SECTORS + held(1, 2, "15:50:00", "16:00:00") + held(1, 1, "16:05:00", "16:30:00"))

    assert [(line["event"], line["group_id"]) for line in log(client)] == [
        ("assigned", 2), ("released", 2), ("assigned", 1), ("completed", 1),
    ]


def test_messages_and_sector_lines_are_in_time_order_together(client, bear_creek):
    write(bear_creek, SECTORS + held(3, 2, "15:50:00", "16:10:00")
          + message(1, "16:20:00", "in", "Done here.") + message(1, "15:55:00", "out", "Go north."))

    assert [(line["kind"], line["time"][11:16]) for line in log(client)] == [
        ("sector", "15:50"), ("message", "15:55"), ("sector", "16:10"), ("message", "16:20"),
    ]


def test_at_the_same_second_a_group_leaves_one_sector_before_it_takes_the_next(client, bear_creek):
    write(bear_creek, SECTORS + held(3, 2, "16:10:00") + held(2, 2, "15:50:00", "16:10:00"))

    assert [(line["event"], line["sector_name"]) for line in log(client)] == [
        ("assigned", "S2"), ("released", "S2"), ("assigned", "S3"),
    ]


def test_reading_the_log_writes_nothing(client, bear_creek):
    write(bear_creek, SECTORS + held(1, 1, "15:50:00", "16:30:00"))
    before = bear_creek.read_bytes()

    log(client)

    assert bear_creek.read_bytes() == before


def test_with_no_mission_open_there_is_no_log(client):
    assert client.get("/api/mission/log").status_code == 409


def test_arizona07_has_seven_message_lines_and_twelve_sector_lines(client, arizona07):
    client.post("/api/missions/952592f8-f48b-4310-aa51-3abcefc02005/open")

    lines = log(client)
    messages = [line for line in lines if line["kind"] == "message"]
    sectors = [line for line in lines if line["kind"] == "sector"]

    assert [line["time"] for line in lines] == sorted(line["time"] for line in lines)
    assert [line["addressing"] for line in messages] == ["direct"] * 4 + ["multicast", "direct", "broadcast"]
    assert [radio["radio_id"] for radio in messages[4]["radios"]] == [1, 2]
    broadcast = messages[6]
    assert [radio["radio_id"] for radio in broadcast["radios"]] == [1, 2, 3, 4, 5, 7]
    assert all(radio["ack_time"] for radio in broadcast["radios"])
    assert [(line["event"], line["sector_name"], line["group_id"], line["partial"]) for line in sectors] == [
        ("assigned", "S1", 1, False), ("assigned", "S2", 3, False), ("assigned", "S3", 2, False),
        ("completed", "S3", 2, False),   # 12:24 am
        ("assigned", "S5", 2, False),
        ("completed", "S1", 1, False), ("completed", "S2", 3, False),
        ("assigned", "S4", 3, False), ("assigned", "S6", 1, False),
        ("completed", "S5", 2, False),
        ("released", "S4", 3, True), ("released", "S6", 1, True),   # 2:37 am
    ]
