import sys
sys.path.append(".")

import pytest
from modules.database import init_db, get_connection
from modules.auth import create_user, authenticate, ADMIN, PROVIDER


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "t.db"
    init_db(p)
    return p


def test_create_and_login_admin(path):
    create_user("Ann", "Admin", "Ann@X.com", "password1", ADMIN, db_path=path)
    u = authenticate("ann@x.com", "password1", db_path=path)
    assert u and u["role"] == ADMIN


def test_provider_row_created(path):
    uid = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER,
                      license_number="L1", db_path=path)
    c = get_connection(path)
    assert c.execute("SELECT license_number FROM healthcare_provider WHERE user_id=?", (uid,)).fetchone()[0] == "L1"
    c.close()


def test_wrong_password_and_unknown_email(path):
    create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=path)
    assert authenticate("jo@x.com", "nope", db_path=path) is None
    assert authenticate("ghost@x.com", "password1", db_path=path) is None


def test_deactivated_user_blocked(path):
    uid = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=path)
    c = get_connection(path)
    c.execute("UPDATE user SET is_active=0 WHERE user_id=?", (uid,))
    c.commit(); c.close()
    assert authenticate("jo@x.com", "password1", db_path=path) is None


def test_short_password_rejected(path):
    with pytest.raises(ValueError):
        create_user("A", "B", "a@b.com", "short", PROVIDER, db_path=path)


def test_logins_are_logged(path):
    create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=path)
    authenticate("jo@x.com", "password1", db_path=path)
    authenticate("jo@x.com", "bad", db_path=path)
    c = get_connection(path)
    actions = {r[0] for r in c.execute("SELECT action FROM system_log")}
    c.close()
    assert {"LOGIN", "LOGIN_FAILED", "CREATE_USER"} <= actions


from modules.auth import list_users, set_user_active, get_logs


def test_admin_deactivate_and_reactivate(path):
    admin = create_user("Ann", "Admin", "ann@x.com", "password1", ADMIN, db_path=path)
    jo = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=path)
    set_user_active(jo, False, admin, db_path=path)
    assert authenticate("jo@x.com", "password1", db_path=path) is None
    set_user_active(jo, True, admin, db_path=path)
    assert authenticate("jo@x.com", "password1", db_path=path) is not None


def test_admin_cannot_deactivate_self(path):
    admin = create_user("Ann", "Admin", "ann@x.com", "password1", ADMIN, db_path=path)
    with pytest.raises(ValueError):
        set_user_active(admin, False, admin, db_path=path)


def test_list_users_and_logs(path):
    create_user("Ann", "Admin", "ann@x.com", "password1", ADMIN, db_path=path)
    create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, department="ER", db_path=path)
    users = list_users(db_path=path)
    assert len(users) == 2 and users[1]["department"] == "ER"
    logs = get_logs(db_path=path)
    assert logs[0]["action"] == "CREATE_USER" and logs[0]["date_time"]


def test_create_user_with_gender_and_second_admin(path):
    first = create_user("Ann", "Admin", "ann@x.com", "password1", ADMIN, gender="Female", db_path=path)
    second = create_user("Bob", "Admin", "bob@x.com", "password1", ADMIN, gender="Male", db_path=path)
    assert authenticate("bob@x.com", "password1", db_path=path)["role"] == ADMIN
    users = {u["email"]: u for u in list_users(db_path=path)}
    assert users["ann@x.com"]["gender"] == "Female" and users["bob@x.com"]["role_name"] == ADMIN
    c = get_connection(path)
    assert c.execute("SELECT COUNT(*) FROM admin").fetchone()[0] == 2
    c.close()


def test_invalid_gender_rejected(path):
    with pytest.raises(ValueError):
        create_user("A", "B", "a@b.com", "password1", PROVIDER, gender="Robot", db_path=path)


# ---------- password change and reset ----------
from modules.auth import change_password, reset_password, generate_temp_password


def test_user_changes_own_password(path):
    uid = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=path)
    change_password(uid, "password1", "newpass99", db_path=path)
    assert authenticate("jo@x.com", "password1", db_path=path) is None
    assert authenticate("jo@x.com", "newpass99", db_path=path) is not None


def test_change_password_rules(path):
    uid = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=path)
    with pytest.raises(ValueError, match="incorrect"):
        change_password(uid, "wrong-one", "newpass99", db_path=path)
    with pytest.raises(ValueError, match="at least 8"):
        change_password(uid, "password1", "short", db_path=path)
    with pytest.raises(ValueError, match="different"):
        change_password(uid, "password1", "password1", db_path=path)
    assert authenticate("jo@x.com", "password1", db_path=path) is not None   # unchanged


def test_admin_reset_gives_working_temp_password_and_forces_change(path):
    admin = create_user("Ann", "Admin", "ann@x.com", "password1", ADMIN, db_path=path)
    jo = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=path)
    assert authenticate("jo@x.com", "password1", db_path=path)["must_change_password"] is False
    temp = reset_password(jo, admin, db_path=path)
    assert len(temp) >= 8 and temp != "password1"
    assert authenticate("jo@x.com", "password1", db_path=path) is None          # old one dead
    user = authenticate("jo@x.com", temp, db_path=path)
    assert user and user["must_change_password"] is True
    change_password(jo, temp, "mynewpass1", db_path=path)                        # clears the flag
    assert authenticate("jo@x.com", "mynewpass1", db_path=path)["must_change_password"] is False


def test_reset_is_admin_only_and_not_for_self(path):
    admin = create_user("Ann", "Admin", "ann@x.com", "password1", ADMIN, db_path=path)
    jo = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=path)
    li = create_user("Li", "Nurse", "li@x.com", "password1", PROVIDER, db_path=path)
    with pytest.raises(ValueError, match="Only administrators"):
        reset_password(li, jo, db_path=path)
    with pytest.raises(ValueError, match="own account"):
        reset_password(admin, admin, db_path=path)
    with pytest.raises(ValueError, match="not found"):
        reset_password(999, admin, db_path=path)
    assert authenticate("li@x.com", "password1", db_path=path) is not None      # untouched


def test_temp_passwords_are_random_and_readable():
    a, b = generate_temp_password(), generate_temp_password()
    assert a != b and len(a) == 10 and not set(a) & set("O0oIl1")


def test_new_user_can_be_forced_to_change_password(path):
    create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, must_change_password=True, db_path=path)
    assert authenticate("jo@x.com", "password1", db_path=path)["must_change_password"] is True


def test_password_events_are_logged(path):
    admin = create_user("Ann", "Admin", "ann@x.com", "password1", ADMIN, db_path=path)
    jo = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=path)
    with pytest.raises(ValueError):
        change_password(jo, "wrong", "newpass99", db_path=path)
    temp = reset_password(jo, admin, db_path=path)
    change_password(jo, temp, "newpass99", db_path=path)
    actions = {l["action"] for l in get_logs(db_path=path)}
    assert {"PASSWORD_CHANGE_FAILED", "PASSWORD_RESET", "PASSWORD_CHANGED"} <= actions
    assert all(temp not in (l["description"] or "") for l in get_logs(db_path=path))   # never logged