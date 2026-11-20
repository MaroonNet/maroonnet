# Sample missions

Mission data for local testing. Each folder holds one seed file (plain SQL) that
fills an empty mission database. Build your own copy, point the backend at it,
break it, rebuild it.

Real missions live on a commander's laptop and never in this repository. The
missions here are samples made for development.

| Mission | Folder | What it is |
| --- | --- | --- |
| Arizona07 | `arizona07/` | One-night search, 8 radios, 7 sectors, 6 waypoints, about 10,400 positions |

Built Arizona07 before November 20, 2026? That was version 1, with different
sectors and an older schema. Delete your copy (see "Reset it") and build this one.

## Build a mission file

From `backend/`:

```sh
export MISSIONDB_URL=sqlite:///missions/arizona07/day-01.sqlite3
uv run alembic upgrade 0002
sqlite3 missions/arizona07/day-01.sqlite3 < missiondb/sample-missions/arizona07/arizona07-seed.sql
uv run alembic upgrade head
```

1. `alembic upgrade 0002` creates the file at the schema version the seed was written for.
2. `sqlite3 ... < seed.sql` loads the data. It prints nothing when it works.
3. `alembic upgrade head` brings the file up to the current schema.

No `sqlite3` command on your machine? Replace the third line with:

```sh
uv run python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.executescript(open(sys.argv[2]).read()); c.close()" missions/arizona07/day-01.sqlite3 missiondb/sample-missions/arizona07/arizona07-seed.sql
```

The file lands in `backend/missions/`, which git ignores.

## Use it

Start the backend with the same `MISSIONDB_URL` set. `missiondb/db.py` reads it.

## Look inside it

Open `backend/missiondb/tools/missiondb-explorer.html` in a browser, choose
**Open .sqlite3**, and pick the mission file. It draws the tables, their keys and
their rows. The file is read in your browser and goes nowhere. It works offline;
`sql-asm.js` must stay in the same folder as the page.

## Reset it

Delete `missions/arizona07/day-01.sqlite3` (and any `-wal` / `-shm` files beside
it), then run the build again.

## Arizona07

### Real

From the public MapScore case set (case `Arizona07`), by way of
`backend/mapdb/regions/arizona07.json`:

- The search area: the 25 km window SPM runs on.
- The start point, 31.50572, -110.67622, and the find point, 31.51000, -110.65333.
  Both are stored as waypoints: `Start point`, and the two `find` waypoints.
- The outline of the story: a lone hiker lost his trail after dark, a Border
  Patrol helicopter found him with FLIR, and a ground team walked him out.

The sectors were drawn over the SPM Model A probability map for this case (hiker,
run November 20, 2026). Together they cover about 30% of the probability. The map
itself is not stored in the mission file.

### Reconstructed

Everything else was made up for demonstration: the date and times, groups,
radios, searchers, sectors, tracks, messages and waypoints. The tracks were
generated over the real terrain. Searchers 10 to 13 are the MaroonNet team; every
other name is invented. Radio `!7f3b21a2` is a team test radio; the other node
numbers are invented.

### Who is on which radio

| Radio | Group | Searchers |
| --- | --- | --- |
| 1, 2, 3 | Group 1 | 1 to 3, 4 to 6, 7 to 9 |
| 4 | Group 2 until 11:25 pm, then none | 10 to 13 |
| 5 | Group 3 | 14, 15, 17 |
| 6 | none | none (spare, never deployed) |
| 7 | Group 2 | 18 to 21 |
| 8 | none | 16 (the commander, at the command post) |

Radio 3 moves from Group 1 to Group 3 at 1:24 am.

### The night (local time, MST; the database stores UTC)

| Time | Event |
| --- | --- |
| 8:30 pm | Command post opens inside S1. S1, S2, S3 drawn by 8:45 pm. |
| 8:50 pm | Briefing. Group 1 takes S1, Group 2 takes S3, Group 3 takes S2. |
| 9:14 to 9:19 pm | Groups 2 and 3 reach their sectors. |
| 10:15, 10:40 pm | S4 and S5 drawn. |
| 11:24 pm | Radio 4 is detached from Group 2 to find a helicopter landing zone. |
| 11:34 to 11:55 pm | Radio 5 is out of range. Its positions arrive up to 21 minutes late. |
| 12:24 am | S3 completed. Group 2 (now radio 7 alone) is assigned S5 at 12:26 am. |
| 12:33 am | Radio 4 marks the landing zone (`LZ 1`). |
| 12:55, 1:02 am | S6 and S7 drawn. S7 is never assigned. |
| 1:21 am | S1 completed. |
| 1:23 am | S2 completed. At 1:24 am Group 3 is assigned S4 and radio 3 joins it. |
| 1:24 am | Radio 1 walks into S6 before it is assigned. |
| 1:37 am | Radio 1 reports boot prints in S6. |
| 1:46 am | Radio 2 arrives and S6 is assigned to Group 1. |
| 1:51 am | Helicopter sighting. The commander pins it and sends radios 1 and 2. |
| 2:07 am | S5 completed. |
| 2:34 am | Radio 1 confirms the subject. |
| 2:37 am | S4 and S6 completed. All teams recalled at 2:38 am. |
| 4:20 am | Mission closed. |

### Things to test against

- Radio 6 was registered and never deployed: no positions, no searchers, no group.
- Radio 8 is the command post. It never moves, reports every 5 minutes (90
  positions), and belongs to no group.
- Radio 4 has no group after 11:25 pm and still reports positions.
- Radio 3 has two group assignments.
- Group 2 holds two sectors, one after the other (S3, then S5). `sector_assignment`
  keeps both with their times. S7 has no assignment row at all.
- `sector_dispatch` has one row per radio per assignment (11 rows), each acknowledged.
- The command post sits inside S1, so every deployed radio has a `sector_entry`
  row for S1, whether or not S1 was its sector.
- Radio 1 enters S6 about 22 minutes before S6 is assigned to its group. Radio 3
  clips S7 on its way to S4. Both produce `sector_entry` rows for sectors that
  were not theirs at the time.
- `sector_entry` records the first entry only. A radio that leaves and returns
  gets no second row.
- Positions come every 10 s inside a radio's own assigned sector and every 60 s
  elsewhere. About 3% are missing, as lost reports.
- There are two `find` waypoints on the same point. The first (helicopter
  sighting) has no radio and no message. The second (confirmed on the ground)
  links to radio 1 and its `found` message.
- S4 and S6 read `completed` although they were closed by the find, not fully searched.
