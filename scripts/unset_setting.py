#!/usr/bin/env python3
"""Delete one setting saved from the UI (= fall back to the environment variable or default).

    python scripts/unset_setting.py LOCAL_LOGIN_ENABLED
    python scripts/unset_setting.py --list

⚠ **This is the way back from a lockout.** Resolution order is **DB > environment > default**, so
a value saved from the UI cannot be overridden by an environment variable (ADR-0031). From a
**state where you cannot get into the UI**, such as the IdP going down while `LOCAL_LOGIN_ENABLED`
is false, delete the saved value to fall back to the environment variable / default.

⚠ **Delete only one key.** Deleting the whole row resets the other settings to defaults too.

⚠ **Never print values.** Some keys hold secrets, so only key names are printed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.infrastructure.models import SystemSetting
from shared.kernel.database.session import get_db

_SETTING_KEY = "app.config"


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0

    session = next(get_db())
    row = session.get(SystemSetting, _SETTING_KEY)
    stored = dict(row.setting_json) if row and isinstance(row.setting_json, dict) else {}

    if argv[0] == "--list":
        print(f"画面で保存されている鍵（{len(stored)} 件）:")
        for key in sorted(stored):
            print(f"  {key}")
        return 0

    key = argv[0]
    if row is None or key not in stored:
        print(f"{key} は画面で保存されていない（消すものが無い）。", file=sys.stderr)
        return 1

    del stored[key]
    # ⚠ **Assign a new dict.** If only the contents are mutated, SQLAlchemy may not
    #   pick up the change to the JSON column.
    row.setting_json = stored
    session.commit()
    print(f"{key} の保存を消した。次に読むときは環境変数か既定値へ戻る。")
    print("⚠ 起動時にしか読まれない鍵は、プロセスを起こし直すまで効かない。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
