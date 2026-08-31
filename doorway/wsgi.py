#!/usr/bin/env python3
"""
Production entry point. Run under gunicorn:

    gunicorn wsgi:application --bind 0.0.0.0:$PORT

On a fresh deploy the database file will not exist yet, so this bootstraps it
once from environment variables. It never touches an existing database -- a
redeploy leaves participant data alone.

    DOORWAY_DB              path on the persistent volume, e.g. /data/doorway.db
    DOORWAY_SECRET_KEY      required when DOORWAY_ENV=production
    DOORWAY_ORG_NAME        agency name for the first-boot bootstrap
    DOORWAY_ADMIN_USERNAME  first admin (default: admin)
    DOORWAY_ADMIN_PASSWORD  required for the bootstrap to run
"""
import os
import sys

import app as app_module
import db
import models
import seed


def bootstrap_if_empty(db_path):
    """Create the schema, starter content, and first admin exactly once."""
    conn = db.connect(db_path)
    db.init_db(conn)
    existing = conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0]
    if existing:
        conn.close()
        return False

    password = os.environ.get("DOORWAY_ADMIN_PASSWORD")
    if not password:
        conn.close()
        sys.stderr.write(
            "Doorway: database is empty and DOORWAY_ADMIN_PASSWORD is not set, so no "
            "admin account was created. Set it and redeploy, or run init_db.py.\n")
        return False

    org_id = seed.seed_org(conn, os.environ.get("DOORWAY_ORG_NAME", "Your Agency"))
    models.create_user(conn, org_id, os.environ.get("DOORWAY_ADMIN_USERNAME", "admin"),
                       password, os.environ.get("DOORWAY_ADMIN_NAME", "Agency Admin"), "admin")
    conn.close()
    sys.stderr.write("Doorway: bootstrapped a new database at %s\n" % db_path)
    return True


DB_PATH = os.environ.get("DOORWAY_DB", db.DEFAULT_DB_PATH)
directory = os.path.dirname(DB_PATH)
if directory:
    os.makedirs(directory, exist_ok=True)
bootstrap_if_empty(DB_PATH)

application = app_module.create_app(DB_PATH)
