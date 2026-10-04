"""Consistent, uniquely named SQLite backup before applying schema changes."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / 'backups' / ('before-foundation-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.sqlite3')
destination.parent.mkdir(exist_ok=True)
with sqlite3.connect(root / 'db.sqlite3') as source, sqlite3.connect(destination) as target:
    source.backup(target)
print(destination)
