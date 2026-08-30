#!/usr/bin/env python3
"""
The scheduled half of Doorway. Run once each morning from cron:

    0 9 * * *  cd /srv/doorway && python jobs.py run --org 1

Commands:
    run       evaluate reminder rules, then send everything that is due
    nudges    evaluate reminder rules only (add --dry-run to preview)
    dispatch  send queued messages whose quiet-hours hold has expired
"""
import argparse
import sys

import db
import messaging
import nudges


def main():
    parser = argparse.ArgumentParser(description="Doorway scheduled jobs.")
    parser.add_argument("command", choices=["run", "nudges", "dispatch"])
    parser.add_argument("--db", default=db.DEFAULT_DB_PATH)
    parser.add_argument("--org", type=int, help="Limit to one agency (default: all).")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent.")
    args = parser.parse_args()

    conn = db.connect(args.db)
    org_ids = [args.org] if args.org else [
        row["id"] for row in conn.execute("SELECT id FROM organizations ORDER BY id")]

    total_queued = total_skipped = total_sent = total_failed = 0
    for org_id in org_ids:
        if args.command in ("run", "nudges"):
            results = nudges.run(conn, org_id, dry_run=args.dry_run)
            for row in results:
                if row["status"] == "queued":
                    total_queued += 1
                    if args.dry_run:
                        print("  would send to %s (%s): %s"
                              % (row["contact"], row.get("language"), row["preview"]))
                else:
                    total_skipped += 1
                    print("  skipped %s: %s" % (row["contact"], row["reason"]))
        if args.command in ("run", "dispatch") and not args.dry_run:
            sent, failed = messaging.dispatch_due(conn, org_id)
            total_sent += sent
            total_failed += failed

    print("%d queued, %d skipped, %d sent, %d failed"
          % (total_queued, total_skipped, total_sent, total_failed))
    conn.close()
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
