"""Creates the first administrator. Run once:  python scripts/create_admin.py"""
import getpass
import sys
sys.path.append(".")

from modules.database import init_db
from modules.auth import create_user, ADMIN

init_db()
first = input("First name: ")
last = input("Last name: ")
email = input("Email: ")
password = getpass.getpass("Password (min 8 chars): ")
create_user(first, last, email, password, ADMIN)
print("Administrator created. You can now log in.")