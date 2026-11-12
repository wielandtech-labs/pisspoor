"""Settings for pytest: the real settings, plus a throwaway SECRET_KEY.

config.settings refuses to load without SECRET_KEY when DEBUG is off.
"""

import os

if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = "test-only-not-a-real-secret"

from config.settings import *  # noqa: E402, F403
