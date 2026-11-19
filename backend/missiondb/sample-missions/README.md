# Sample missions

Mission data for local testing. Each folder holds one seed file (plain SQL) that
fills an empty mission database. Build your own copy, point the backend at it,
break it, rebuild it.

Real missions live on a commander's laptop and never in this repository. The
missions here are samples made for development.

| Mission | Folder | What it is |
| --- | --- | --- |
| Arizona07 | `arizona07/` | One-night search, 5 radios, 5 sectors, about 6,900 positions |

## Build a mission file

From `backend/`:

```sh
export MISSIONDB_URL=sqlite:///missions/arizona07/day-01.sqlite3
uv run alembic upgrade 0001
sqlite3 missions/arizona07/day-01.sqlite3 < missiondb/sample-missions/arizona07/arizona07-seed.sql
uv run alembic upgrade head
```

1. `alembic upgrade 0001` creates the file at the schema version the seed was written for.
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
  The schema has no column for either. The scenario is built around them.
- The outline of the story: a lone hiker lost his trail after dark, a Border
  Patrol helicopter found him with FLIR, and a ground team walked him out.

### Reconstructed

Everything else was made up for demonstration: the date and times, groups,
radios, searchers, sectors, tracks and messages. The tracks were generated over
the real terrain. Searchers 10 to 13 are the MaroonNet team; every other name is
invented. Radio `!7f3b21a2` is a team test radio; the other node numbers are
invented.

### The night (local time, MST; the database stores UTC)

| Time | Event |
| --- | --- |
| 8:30 pm | Command post opens. S1, S2, S3 drawn. |
| 8:50 pm | Briefing. Group 1 (radios 1, 2, 3) takes S1, Group 2 (radio 4) S3, Group 3 (radio 5) S2. |
| 11:08 pm | S3 completed. Group 2 returns and reports a helicopter landing zone at 11:48 pm. |
| 11:25 pm | S4 drawn. |
| 11:30 pm | Radio 3 moves from Group 1 to Group 3. |
| 12:13 am | S2 completed. Group 3 is assigned S4. |
| 12:34 to 12:54 am | Radio 5 is out of range. Its positions arrive about 21 minutes late. |
| 12:50 am | S5 drawn. It is never assigned. |
| 1:38 am | Helicopter sighting passed to Group 1. |
| 1:47 am | Group 1 confirms the subject. |
| 1:50 am | S1 and S4 completed. All teams recalled. |
| 3:25 am | Mission closed. |

### Things to test against

- Radio 6 was registered and never deployed. Searcher 16 (the commander) never carried a radio.
- Radio 3 has two group assignments.
- Radios 1, 2 and 3 cross S2 on the way to S1, and radios 1 and 2 cross S4 on the
  way home. These produce `sector_entry` rows for sectors that are not theirs.
- Positions come every 10 s inside a radio's own sector and every 60 s elsewhere.
  About 3% are missing, as lost reports.
- S1 and S4 read `completed` although they were closed by the find, not fully searched.
