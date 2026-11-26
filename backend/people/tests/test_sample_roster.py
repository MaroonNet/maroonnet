"""The sample roster: a command adds the people of the Arizona07 sample mission to the roster."""

import os
import re
import subprocess
import sys
from pathlib import Path

from maps.folders import DATA_DIR_VARIABLE
from people import roster
from people.sample_roster import ARIZONA07, add_missing, main

BACKEND = Path(__file__).parents[2]
SEED = BACKEND / "missiondb" / "sample-missions" / "arizona07" / "arizona07-seed.sql"


def said(capsys) -> str:
    return capsys.readouterr().out


def test_the_sample_is_the_searchers_of_the_arizona07_seed():
    line = next(line for line in SEED.read_text().splitlines() if line.startswith("INSERT INTO searcher "))
    assert re.findall(r"\(\d+, '([^']*)', '([^']*)'\)", line) == ARIZONA07


def test_on_an_empty_roster_it_adds_all_21_with_names_only(capsys):
    main()
    people = roster.list_people()
    assert len(people) == 21
    assert all(person.middle_initial is None and person.phone is None for person in people)
    assert said(capsys) == f"Added 21 of Arizona07's people to the roster at {roster.roster_path()}.\n"


def test_run_again_it_adds_nobody(capsys):
    main()
    main()
    assert len(roster.list_people()) == 21
    assert said(capsys).splitlines()[-1] == f"All 21 of Arizona07's people are already in the roster at {roster.roster_path()}."


def test_someone_already_in_the_roster_is_kept_as_they_are_and_others_are_left_alone():
    roster.add_person(roster.PersonDetails(first_name="Corey", middle_initial="B", last_name="Greene", phone="555-0142"))
    roster.add_person(roster.PersonDetails(first_name="Ben", last_name="Cho"))
    assert add_missing(ARIZONA07) == 20
    people = {f"{person.first_name} {person.last_name}": person for person in roster.list_people()}
    assert len(people) == 22
    assert (people["Corey Greene"].middle_initial, people["Corey Greene"].phone) == ("B", "555-0142")
    assert "Ben Cho" in people


def test_it_says_how_many_were_already_in_the_roster(capsys):
    roster.add_person(roster.PersonDetails(first_name="Diego", last_name="Alas"))
    main()
    assert said(capsys) == f"Added 20 of Arizona07's people to the roster at {roster.roster_path()}. 1 was already in it.\n"


def test_it_runs_as_the_readme_says(tmp_path):
    folder = tmp_path / "app-data-of-its-own"
    done = subprocess.run(
        [sys.executable, "-m", "people.sample_roster"],
        cwd=BACKEND, env={**os.environ, DATA_DIR_VARIABLE: str(folder)}, capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == f"Added 21 of Arizona07's people to the roster at {folder / 'roster.sqlite3'}.\n"
