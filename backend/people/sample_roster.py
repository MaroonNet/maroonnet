"""The sample roster: the people of the Arizona07 sample mission, added to the roster.

Run from backend/ (README.md in this folder has the step):

    uv run python -m people.sample_roster

It adds each person whose first and last name are not in the roster yet, and changes and
removes no one, so it can be run again. The roster is the app data folder's roster.sqlite3,
or the one in MAROONNET_DATA_DIR when that is set; mission files are not touched.
"""

from .roster import PersonDetails, add_person, people_named, roster_path

# The searchers of missiondb/sample-missions/arizona07/arizona07-seed.sql, in its order: first
# name, last name. The seed has no middle initials or phone numbers.
ARIZONA07 = [
    ("Marcus", "Ibarra"), ("Tessa", "Lindqvist"), ("Owen", "Whitfield"), ("Priya", "Raman"),
    ("Dale", "Kowalski"), ("Renee", "Castillo"), ("Hank", "Morrow"), ("Luis", "Ortega"),
    ("Naomi", "Feld"), ("Diego", "Alas"), ("Corey", "Greene"), ("Elijah", "Heimsoth"),
    ("Joshua", "Wagner"), ("Grant", "Pruitt"), ("Sofia", "Delgado"), ("Ellen", "Brandt"),
    ("Wes", "Hallam"), ("Ana", "Morales"), ("Trevor", "Banks"), ("Mei", "Tanaka"),
    ("Jonah", "Reyes"),
]


def add_missing(names: list[tuple[str, str]]) -> int:
    """Adds each name the roster does not have, matched by first and last name as the app ties
    a mission's person to the roster. Answers how many were added."""
    added = 0
    for first_name, last_name in names:
        if not people_named(first_name, last_name):
            add_person(PersonDetails(first_name=first_name, last_name=last_name))
            added += 1
    return added


def main() -> None:
    added = add_missing(ARIZONA07)
    kept = len(ARIZONA07) - added
    where = f"the roster at {roster_path()}"
    if added == 0:
        print(f"All {len(ARIZONA07)} of Arizona07's people are already in {where}.")
    elif kept == 0:
        print(f"Added {added} of Arizona07's people to {where}.")
    else:
        print(f"Added {added} of Arizona07's people to {where}. {kept} {'was' if kept == 1 else 'were'} already in it.")


if __name__ == "__main__":
    main()
