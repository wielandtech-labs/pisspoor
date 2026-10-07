"""Block until the database accepts connections.

The container runs ``migrate`` before ``exec gunicorn``. When the database is
not yet up, ``migrate`` raises ``OperationalError``, the container exits, and
Kubernetes restarts it - so the pod does eventually come up, but only after a
couple of crash cycles.

That self-healing is worse than it sounds. Two restarts look exactly like a
real crashloop to anyone reading ``kubectl get pods``, which is the signal we
rely on when something is genuinely broken. And the restart backoff is
exponential, so a database that takes a little longer turns a few seconds of
waiting into minutes of delay.

Observed on the first review app for this repo: the app started alongside its
throwaway Postgres, failed twice with

    connection to server at "10.43.221.49", port 5432 failed: Connection refused

and only then came up. Review apps hit this every time because the app and its
database start together. Deployed environments normally do not, since the
shared CNPG cluster is already running - but they would during a failover,
which is exactly when extra crash cycles are least welcome.
"""

from __future__ import annotations

import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Wait until the database is accepting connections."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--timeout",
            type=float,
            default=60.0,
            help="Give up after this many seconds (default: 60).",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=1.0,
            help="Seconds between attempts (default: 1).",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Which configured database to wait for (default: default).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        timeout: float = options["timeout"]
        interval: float = options["interval"]
        alias: str = options["database"]

        connection = connections[alias]
        deadline = time.monotonic() + timeout
        attempts = 0
        last_error: OperationalError | None = None

        while True:
            attempts += 1
            try:
                connection.ensure_connection()
            except OperationalError as exc:
                last_error = exc
                # close_if_unusable_or_obsolete resets the broken handle;
                # without it a retry can reuse the failed connection object.
                connection.close_if_unusable_or_obsolete()
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Database {alias!r} is ready after {attempts} attempt(s).")
                )
                return

            if time.monotonic() >= deadline:
                raise CommandError(
                    f"Database {alias!r} not ready after {timeout:.0f}s "
                    f"({attempts} attempts). Last error: {last_error}"
                )

            # One line per attempt, so a slow start is visible in pod logs
            # rather than looking like a hang.
            self.stdout.write(f"Database {alias!r} unavailable (attempt {attempts}); waiting...")
            time.sleep(interval)
