import time

from app_paths import runtime_file


LOG_PATH = runtime_file(__file__, "debug.log")


def log(message):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass
