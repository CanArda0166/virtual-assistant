import os
import traceback
from datetime import datetime
from config import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

RED    = "\033[31m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
RESET  = "\033[0m"

_seen_errors: dict = {}

def _log_file() -> str:
    return os.path.join(LOGS_DIR, datetime.now().strftime("%d.%m.%Y") + ".log")

def _error_key(source: str, short: str) -> str:
    return f"{source}::{short}"

def _write_log(level: str, source: str, short: str, detail: str = ""):
    now  = datetime.now().strftime("%H:%M:%S")
    line = f"[{now}] [{level}] [{source}] {short}"
    if detail:
        line += f"\n{'─'*60}\n{detail}\n{'─'*60}"
    line += "\n"
    try:
        with open(_log_file(), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

def _write_repeat(source: str, short: str):
    now = datetime.now().strftime("%H:%M:%S")
    try:
        with open(_log_file(), "a", encoding="utf-8") as f:
            f.write(f"  ↺ [{now}] tekrar — {source}: {short}\n")
    except Exception:
        pass

def info(source: str, message: str):
    print(f"{YELLOW}[{source}]: {message}{RESET}")
    _write_log("INFO", source, message)

def success(source: str, message: str):
    print(f"{GREEN}[{source}]: {message}{RESET}")
    _write_log("OK", source, message)

def warn(source: str, message: str):
    print(f"{YELLOW}[{source}]: {message}{RESET}")
    _write_log("WARN", source, message)

def error(source: str, short: str, exception: Exception = None, extra: str = ""):
    print(f"{RED}[{source} Hatasi]: {short}{RESET}")
    key = _error_key(source, short)
    if key in _seen_errors:
        _write_repeat(source, short)
        return
    _seen_errors[key] = datetime.now().strftime("%H:%M:%S")
    detail_parts = []
    if extra:
        detail_parts.append(f"Detay: {extra}")
    if exception:
        detail_parts.append(f"Exception: {type(exception).__name__}: {exception}")
        detail_parts.append("Traceback:\n" + traceback.format_exc())
    _write_log("ERROR", source, short, "\n".join(detail_parts))

def log_raw(source: str, label: str, content: str):
    _write_log("RAW", source, label, content)
