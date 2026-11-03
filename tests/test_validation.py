import sys
sys.path.append(".")

import pytest

from modules.auth import create_user, PROVIDER, ADMIN
from modules.database import init_db
from modules.patients import register_patient, update_patient
from modules.validation import (ValidationError, email_error, name_error, password_error,
                                phone_error)


# ---------- the rules themselves ----------
@pytest.mark.parametrize("email", ["12345", "john", "john@", "@x.com", "john@x", "jo hn@x.com",
                                   "john@@x.com", "john@x..com", "", "   "])
def test_bad_emails_rejected(email):
    assert email_error(email)


@pytest.mark.parametrize("email", ["john@example.com", "a.b-c+d@mail.co.ke", "J@X.org"])
def test_good_emails_accepted(email):
    assert email_error(email) is None


@pytest.mark.parametrize("phone", ["071234567", "07123456789", "07123abc89", "0712 34567",
                                   "+254712345", "٠٧١٢٣٤٥٦٧٨"])
def test_bad_phones_rejected(phone):
    assert phone_error(phone)


def test_phone_rules():
    assert phone_error("0712345678") is None
    assert phone_error("") is None and phone_error(None) is None        # optional by default
    assert phone_error("", required=True)                               # unless required


@pytest.mark.parametrize("name", ["", "  ", "John3", "123", "J@hn", "A" * 51, "John  Doe!", "-John"])
def test_bad_names_rejected(name):
    assert name_error(name)


@pytest.mark.parametrize("name", ["Amina", "Mary-Jane", "O'Brien", "Wanjiru Njeri", "Zoë"])
def test_good_names_accepted(name):
    assert name_error(name) is None


def test_password_rules():
    assert password_error("1234567")                    # 7 characters
    assert password_error("        ")                   # only spaces
    assert password_error("") and password_error(None)
    assert password_error("12345678") is None


# ---------- applied when creating users ----------
@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    init_db(p)
    return p


def good_user(db, **overrides):
    args = dict(first_name="Jo", last_name="Doc", email="jo@x.com", password="password1",
                role_name=PROVIDER, phone_no="0712345678", gender="Male", db_path=db)
    args.update(overrides)
    return create_user(**args)


def test_valid_user_created(db):
    assert good_user(db) > 0
    assert good_user(db, email="ann@x.com", role_name=ADMIN, phone_no=None) > 0


@pytest.mark.parametrize("field,value", [("email", "12345"), ("phone_no", "07123"),
                                         ("phone_no", "07123abcde"), ("password", "short"),
                                         ("first_name", "Jo1"), ("last_name", ""),
                                         ("gender", "Robot")])
def test_invalid_user_rejected(db, field, value):
    with pytest.raises(ValidationError):
        good_user(db, **{field: value})


def test_all_problems_reported_together(db):
    with pytest.raises(ValidationError) as e:
        good_user(db, email="12345", phone_no="123", password="x")
    assert len(e.value.errors) == 3
    assert "email" in str(e.value).lower() and "phone" in str(e.value).lower()


def test_validation_error_is_a_value_error(db):
    with pytest.raises(ValueError):
        good_user(db, email="nope")


# ---------- applied when registering / editing patients ----------
def test_patient_phone_and_name_validation(db):
    uid = good_user(db)
    with pytest.raises(ValidationError):
        register_patient(uid, "Amina", "Otieno", "2022-03-01", "Female", phone_no="0712abc890", db_path=db)
    with pytest.raises(ValidationError):
        register_patient(uid, "Amina", "Otieno", "2022-03-01", "Female", phone_no="07123", db_path=db)
    with pytest.raises(ValidationError):
        register_patient(uid, "Am1na", "Otieno", "2022-03-01", "Female", db_path=db)
    pid, _ = register_patient(uid, "Amina", "Otieno", "2022-03-01", "Female",
                              phone_no=" 0712345678 ", db_path=db)
    with pytest.raises(ValidationError):
        update_patient(pid, uid, "Amina", "Otieno", "2022-03-01", "Female", "12345", db_path=db)
    update_patient(pid, uid, "Amina", "Otieno", "2022-03-01", "Female", "", db_path=db)  # cleared: fine