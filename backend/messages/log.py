"""The log of the open mission: its messages and its sector events, in time order.

A message is saved as one row for each radio. A send to several radios is several rows that
share a batch_id, and the log shows them as one line that lists each radio and when it
acknowledged.

A sector line is not saved anywhere. It is read from the rows of which group held which
sector: one line when the group was given the sector, and one when that ended.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlmodel import Session, select

from missiondb.models import (
    Message, MessageAddressing, MessageDirection, SearchSector, SectorAssignment, SectorStatus,
)


class Receipt(BaseModel):
    """One radio of a message, and when it acknowledged."""

    radio_id: int
    ack_time: datetime | None  # none: not acknowledged. A message from a radio has none.


class MessageLine(BaseModel):
    kind: Literal["message"] = "message"
    id: int  # the id of the send's first row
    time: datetime
    type: str  # "evidence", "found", "instruction", "out_of_sector" or "assignment"
    direction: MessageDirection
    addressing: MessageAddressing
    text: str
    radios: list[Receipt]  # by radio. The one radio it came from, or each radio it went to.


class SectorLine(BaseModel):
    kind: Literal["sector"] = "sector"
    id: int  # the id of the row of the group holding the sector
    time: datetime
    event: Literal["assigned", "completed", "released"]
    sector_id: int
    sector_name: str
    group_id: int
    partial: bool  # a released line only: the sector is searched in part


Line = MessageLine | SectorLine

# Where a line goes among lines of the same second: a group leaves one sector before it
# takes the next, and a message comes after both.
ORDER = {"completed": 0, "released": 0, "assigned": 1, "message": 2}


def read_log(db: Session) -> list[Line]:
    """Every line of the open session, oldest first."""
    lines = [*message_lines(db), *sector_lines(db)]
    return sorted(lines, key=lambda line: (line.time, ORDER[line.event if line.kind == "sector" else "message"], line.id))


def message_lines(db: Session) -> list[MessageLine]:
    """One line for each send. Rows are joined by their batch_id and never by their words,
    so the same words sent twice are two lines."""
    lines: dict[int, MessageLine] = {}
    for row in db.exec(select(Message).order_by(Message.message_id)):
        send = row.batch_id if row.batch_id is not None else row.message_id
        line = lines.get(send)
        if line is None:
            line = lines[send] = MessageLine(
                id=row.message_id, time=row.time, type=row.type_code, direction=row.direction,
                addressing=row.addressing, text=row.text, radios=[],
            )
        line.radios.append(Receipt(radio_id=row.team_id, ack_time=row.ack_time))
    for line in lines.values():
        line.radios.sort(key=lambda receipt: receipt.radio_id)
    return list(lines.values())


def sector_lines(db: Session) -> list[SectorLine]:
    """An assigned line for each time a group was given a sector, and a line for when that
    ended. It ended as completed when it ended at the sector's completed time; any other
    ending is a release."""
    lines: list[SectorLine] = []
    held = select(SectorAssignment, SearchSector).join(SearchSector)
    for row, sector in db.exec(held):
        facts = {"id": row.assignment_id, "sector_id": sector.search_sector_id, "sector_name": sector.name,
                 "group_id": row.search_group_id}
        lines.append(SectorLine(time=row.from_time, event="assigned", partial=False, **facts))
        if row.to_time is None:
            continue
        if row.to_time == sector.completed_time:
            lines.append(SectorLine(time=row.to_time, event="completed", partial=False, **facts))
        else:
            lines.append(SectorLine(time=row.to_time, event="released", partial=sector.status == SectorStatus.PARTIAL, **facts))
    return lines
