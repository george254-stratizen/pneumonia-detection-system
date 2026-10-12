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