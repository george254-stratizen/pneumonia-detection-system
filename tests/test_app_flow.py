"""Runs the real app screens (headless) against a temporary database, in a separate process
so that the PNEUMONIA_DB setting is picked up cleanly."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import sys; sys.path.insert(0, ".")
from modules.database import init_db
from modules.auth import create_user, reset_password, ADMIN, PROVIDER
from streamlit.testing.v1 import AppTest

init_db()
admin = create_user("Ann", "Admin", "ann@x.com", "password1", ADMIN)
jo = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER)
temp = reset_password(jo, admin)

def login(email, pw):
    at = AppTest.from_file("app.py", default_timeout=30).run()
    at.text_input[0].set_value(email); at.text_input[1].set_value(pw)
    at.button[0].click().run()
    return at

# 1. admin-reset user is held on the change-password page
at = login("jo@x.com", temp)
assert not at.exception, at.exception
assert [t.value for t in at.title] == ["🔑 My Account"], [t.value for t in at.title]
assert any("set by an administrator" in w.value for w in at.warning)
assert len(at.sidebar.button) == 1                       # only Log out, no other pages offered

# 2. wrong confirmation is refused, page stays locked
f = {t.label: t for t in at.text_input}
f["Current password"].set_value(temp); f["New password (min 8 characters)"].set_value("brandnew99")
f["Confirm new password"].set_value("different99")
at.button[0].click().run()
assert any("do not match" in e.value for e in at.error)
assert [t.value for t in at.title] == ["🔑 My Account"]

# 3. correct change unlocks the account (the screen switch itself is checked in a real browser)
f = {t.label: t for t in at.text_input}
f["Current password"].set_value(temp); f["New password (min 8 characters)"].set_value("brandnew99")
f["Confirm new password"].set_value("brandnew99")
at.button[0].click().run()
assert not at.exception, at.exception
assert at.session_state["user"]["must_change_password"] is False

# 4. new password works at the next login, old temp one does not
assert any("Welcome" in t.value for t in login("jo@x.com", "brandnew99").title)
assert login("jo@x.com", temp).error
print("FLOW OK")
'''


def test_forced_password_change_flow(tmp_path):
    env = {**os.environ, "PNEUMONIA_DB": str(tmp_path / "flow.db")}
    r = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=180)
    assert "FLOW OK" in r.stdout, r.stdout[-1500:] + r.stderr[-1500:]


LOCKOUT_SCRIPT = r'''
import sys; sys.path.insert(0, ".")
from modules.database import init_db
from modules.auth import create_user, PROVIDER
from streamlit.testing.v1 import AppTest

init_db()
create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER)

def attempt(pw):
    at = AppTest.from_file("app.py", default_timeout=30).run()
    at.text_input[0].set_value("jo@x.com"); at.text_input[1].set_value(pw)
    at.button[0].click().run()
    assert not at.exception, at.exception
    return at

for i in range(4):
    at = attempt("wrong-password")
    assert any("Invalid credentials" in e.value for e in at.error), [e.value for e in at.error]
at = attempt("wrong-password")                                        # 5th wrong one
assert any("Too many failed attempts" in e.value and "15" in e.value for e in at.error), [e.value for e in at.error]
at = attempt("password1")                                             # right password, still locked
assert any("Too many failed attempts" in e.value for e in at.error)
assert not any("Welcome" in t.value for t in at.title)
print("LOCKOUT OK")
'''


def test_lockout_flow_in_the_real_login_screen(tmp_path):
    env = {**os.environ, "PNEUMONIA_DB": str(tmp_path / "lock.db")}
    r = subprocess.run([sys.executable, "-c", LOCKOUT_SCRIPT], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=180)
    assert "LOCKOUT OK" in r.stdout, r.stdout[-1500:] + r.stderr[-1500:]