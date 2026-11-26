# Sample roster

The roster is the list of people the team knows. It is its own file, `roster.sqlite3`,
in the app data folder, and it stays between missions. A mission's session file holds
only the people checked in to that mission.

## Fill the roster with Arizona07's people

From `backend/`:

```sh
uv run python -m people.sample_roster
```

It adds the 21 people of the Arizona07 sample mission, names only (the sample has no
phone numbers). Someone whose first and last name are already in the roster is left as
they are, and no one is removed, so it is safe to run again. It prints how many it added
and where the roster is.

The app data folder is `~/Library/Application Support/MaroonNet/` on Mac and
`%LOCALAPPDATA%\MaroonNet\` on Windows, or the folder in `MAROONNET_DATA_DIR` when that
is set.

## Start from an empty roster

Delete `roster.sqlite3` from the app data folder, then run the command above. The roster
then holds exactly Arizona07's 21 people.
