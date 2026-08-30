#!/usr/bin/env python3
"""
Create the Doorway database, one agency, and a first admin user.

    python init_db.py                 # starter templates and document list
    python init_db.py --demo          # plus a demo caseload for a walkthrough
"""
import argparse
import getpass
import os
import sys

import db
import models
import seed


def main():
    parser = argparse.ArgumentParser(description="Set up a Doorway database.")
    parser.add_argument("--db", default=db.DEFAULT_DB_PATH)
    parser.add_argument("--org", default="Casco Bay Housing Services")
    parser.add_argument("--kind", default="nonprofit",
                        choices=["nonprofit", "pha", "coc", "tbra", "other"])
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", help="Prompted for if omitted.")
    parser.add_argument("--full-name", default="Agency Admin")
    parser.add_argument("--demo", action="store_true",
                        help="Add a demo caseload so the dashboard has data.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing database.")
    args = parser.parse_args()

    if os.path.exists(args.db):
        if not args.force:
            print("%s already exists. Use --force to start over." % args.db)
            return 1
        os.remove(args.db)

    password = args.password or getpass.getpass("Password for '%s': " % args.username)
    if not password:
        print("A password is required.")
        return 1

    conn = db.connect(args.db)
    db.init_db(conn)
    org_id = seed.seed_org(conn, args.org, args.kind)
    user_id = models.create_user(conn, org_id, args.username, password, args.full_name, "admin")

    if args.demo:
        seed.seed_demo(conn, org_id, user_id)

    print("Created %s" % args.db)
    print("  Agency:   %s" % args.org)
    print("  Sign in:  %s" % args.username)
    print("  Loaded:   %d document types, %d templates in %d languages, %d reminder rules"
          % (len(seed.STARTER_DOCUMENT_TYPES), len(seed.STARTER_TEMPLATES),
             len(seed.STARTER_TEMPLATES[0]["bodies"]), len(seed.STARTER_RULES)))
    if args.demo:
        print("  Demo:     %d participants with open and overdue requests"
              % len(seed.DEMO_PARTICIPANTS))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
