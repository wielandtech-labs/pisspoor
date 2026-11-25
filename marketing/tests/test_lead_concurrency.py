"""The lead limit holds under parallel POSTs. Needs Postgres.

The suite (and CI) run on SQLite, which has no advisory locks and no
concurrent writers, so this test skips there. Run it against a throwaway
Postgres:

    docker run -d --rm --name pp-pg -e POSTGRES_PASSWORD=pp -p 127.0.0.1:55432:5432 postgres:16
    DATABASE_NAME=pp DATABASE_USER=postgres DATABASE_PASSWORD=pp \\
        DATABASE_HOST=127.0.0.1 DATABASE_PORT=55432 pytest -m postgres
"""

import threading
import time

import pytest
from django.db import connection

import marketing.views
from marketing.models import Lead
from marketing.views import LEADS_PER_IP_PER_HOUR

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="needs Postgres"),
]

SENDERS = 4 * LEADS_PER_IP_PER_HOUR


def test_parallel_leads_from_one_ip_stop_at_the_limit(monkeypatch):
    real_check = marketing.views.too_many_leads

    def slow_check(client_hash):
        # Widen the gap between the count and the insert so that, without the
        # lock, every request would pass the count before any of them saves.
        over = real_check(client_hash)
        time.sleep(0.2)
        return over

    monkeypatch.setattr(marketing.views, "too_many_leads", slow_check)
    barrier = threading.Barrier(SENDERS, timeout=30)
    statuses, errors = [], []

    def send():
        from django.db import connection as thread_connection
        from django.test import Client

        try:
            barrier.wait()
            response = Client().post(
                "/",
                {"kind": "venue", "name": "Sam", "email": "sam@example.com"},
                HTTP_X_FORWARDED_FOR="203.0.113.9",
            )
            statuses.append(response.status_code)
        except Exception as exc:  # surface it in the assert, not just stderr
            errors.append(exc)
        finally:
            thread_connection.close()

    threads = [threading.Thread(target=send) for _ in range(SENDERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors
    assert sorted(statuses) == [302] * LEADS_PER_IP_PER_HOUR + [429] * (
        SENDERS - LEADS_PER_IP_PER_HOUR
    )
    assert Lead.objects.count() == LEADS_PER_IP_PER_HOUR
