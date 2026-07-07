import json
import os

LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.json")



def _read_log():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, "r") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def _write_log(entries):
    with open(LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def append_log_entry(entry: dict):
    entries = _read_log()
    entries.append(entry)
    _write_log(entries)


def get_log(limit: int = None, creator_id: str = None):
    entries = list(reversed(_read_log()))
    if creator_id:
        entries = [e for e in entries if e.get("creator_id") == creator_id]
    if limit:
        entries = entries[:limit]
    return entries
