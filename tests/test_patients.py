import sys
sys.path.append(".")

from datetime import date, timedelta

import pytest
from modules.database import init_db
from modules.auth import create_user, PROVIDER
from modules.patients import (register_patient, search_patients, get_patient,
                              update_patient, age_text)


@pytest.fixture
def ctx(tmp_path):
    p = tmp_path / "t.db"
    init_db(p)
    uid = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=p)
    return p, uid


def test_register_gives_unique_numbers(ctx):
    p, uid = ctx
    _, n1 = register_patient(uid, "Amina", "Otieno", "2022-03-01", "Female", db_path=p)
    _, n2 = register_patient(uid, "Brian", "Kamau", "2021-06-10", "Male", db_path=p)
    assert n1 != n2 and n1.startswith("PT-")


def test_search_by_name_number_phone(ctx):
    p, uid = ctx
    _, n = register_patient(uid, "Amina", "Otieno", "2022-03-01", "Female",
                            phone_no="0712345678", db_path=p)
    register_patient(uid, "Brian", "Kamau", "2021-06-10", "Male", db_path=p)
    assert len(search_patients("amin", db_path=p)) == 1
    assert len(search_patients("Amina Otieno", db_path=p)) == 1
    assert len(search_patients(n, db_path=p)) == 1
    assert len(search_patients("0712", db_path=p)) == 1
    assert len(search_patients("", db_path=p)) == 2


def test_validation(ctx):
    p, uid = ctx
    with pytest.raises(ValueError):
        register_patient(uid, "", "X", "2022-01-01", "Male", db_path=p)
    with pytest.raises(ValueError):
        register_patient(uid, "A", "X", "2022-01-01", "Select...", db_path=p)
    future = date.today() + timedelta(days=1)
    with pytest.raises(ValueError):
        register_patient(uid, "A", "X", future, "Male", db_path=p)


def test_update_patient(ctx):
    p, uid = ctx
    pid, _ = register_patient(uid, "Amina", "Otieno", "2022-03-01", "Female", db_path=p)
    update_patient(pid, uid, "Amina", "Odhiambo", "2022-03-01", "Female", "0700", "Kisumu", db_path=p)
    got = get_patient(pid, db_path=p)
    assert got["last_name"] == "Odhiambo" and got["address"] == "Kisumu"
    with pytest.raises(ValueError):
        update_patient(999, uid, "A", "B", None, "Male", db_path=p)


def test_age_text():
    assert age_text(None) == "-"
    d = date.today().replace(year=date.today().year - 3)
    assert age_text(str(d)).startswith("3 yrs")