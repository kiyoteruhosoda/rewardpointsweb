"""マスタデータ投入スクリプト（冪等・デプロイ後の再実行可）。

使い方::

    uv run python scripts/seed_master_data.py
    uv run python scripts/seed_master_data.py --reset-admin-password

``--reset-admin-password`` を付けると、既存の初期管理者のパスワードを
``ADMIN_INITIAL_PASSWORD``（未設定なら既定値）へ戻す。管理画面へ入れなくなった
ときの復旧経路なので、明示的に指定したときだけ実行する。

値の正本は ``shared/domain/auth/master_data.py``、投入ロジックは
``shared/infrastructure/master_data_seeder.py``（マイグレーションと共用）。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ロール・権限・初期管理者を投入する（冪等）。")
    parser.add_argument(
        "--reset-admin-password",
        action="store_true",
        help="既存の初期管理者のパスワードを ADMIN_INITIAL_PASSWORD（未設定なら既定値）へ戻す",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    load_dotenv()

    from shared.infrastructure.master_data_seeder import seed_master_data
    from shared.kernel.database.db import get_session_factory

    session = get_session_factory()()
    try:
        seed_master_data(
            session,
            admin_password=os.environ.get("ADMIN_INITIAL_PASSWORD") or None,
            reset_admin_password=args.reset_admin_password,
        )
        session.commit()
        print("Master data seeded.")
        if args.reset_admin_password:
            print("Admin password reset.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
