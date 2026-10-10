"""Create the first local Sermon LM Studio administrator account.

Usage (PowerShell):
    python create_initial_account.py
    python create_initial_account.py --db C:\\path\\to\\auth.sqlite3

The password is intentionally collected with getpass and is never accepted as
a command-line argument or printed to the console. Existing accounts are never
overwritten; use the normal account-management policy for later users.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime
from pathlib import Path

from app.auth import create_initial_user, replace_users_with_admin, user_count
from app.paths import USER_ROOT


def create_initial_account(db_path: Path, username: str, password: str, confirmation: str) -> int:
    """Return a process-style status code for the non-interactive boundary."""
    if password != confirmation:
        print("오류: 비밀번호 확인이 일치하지 않습니다.", file=sys.stderr)
        return 2
    existing_users = user_count(db_path)
    if existing_users != 0:
        print(f"중단: 이미 계정이 {existing_users}개 있습니다. 기존 계정을 덮어쓰지 않습니다.", file=sys.stderr)
        return 3
    try:
        created = create_initial_user(db_path, username, password)
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    if not created:
        print("중단: 다른 프로세스에서 계정이 먼저 생성되었습니다. 기존 계정을 변경하지 않았습니다.", file=sys.stderr)
        return 3
    print(f"초기 관리자 계정 생성 완료: {username.strip().lower()}")
    print(f"인증 DB: {db_path.resolve()}")
    return 0


def replace_initial_account(db_path: Path, username: str, password: str, confirmation: str, replace_confirmation: str) -> int:
    """Explicitly replace all auth users after a typed confirmation."""
    if password != confirmation:
        print("오류: 비밀번호 확인이 일치하지 않습니다.", file=sys.stderr)
        return 2
    if replace_confirmation.strip().upper() != "REPLACE":
        print("중단: 계정 교체 확인 문구가 올바르지 않습니다. 아무것도 변경하지 않았습니다.", file=sys.stderr)
        return 2
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = db_path.with_name(f"{db_path.name}.pre-replace-{stamp}.bak")
    try:
        result = replace_users_with_admin(db_path, username, password, backup_path)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    print(f"기존 계정 {result['replaced_users']}개를 새 관리자 계정으로 교체했습니다: {result['username']}")
    print(f"rollback 백업: {result['backup']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sermon LM Studio 초기 관리자 계정 생성")
    parser.add_argument("--db", type=Path, default=USER_ROOT / "auth.sqlite3", help="인증 DB 경로(기본: 현재 실행 환경의 인증 DB)")
    parser.add_argument("--username", help="사용자명; 생략하면 안전한 입력 프롬프트를 사용합니다.")
    parser.add_argument("--replace-existing", action="store_true", help="기존 인증 계정을 백업한 뒤 새 관리자 계정 하나로 교체")
    args = parser.parse_args()
    db_path = args.db.expanduser()
    username = (args.username or input("사용자명: ")).strip()
    password = getpass.getpass("비밀번호(10자 이상): ")
    confirmation = getpass.getpass("비밀번호 확인: ")
    if args.replace_existing:
        print("경고: 기존 인증 계정이 모두 교체됩니다. 백업은 자동 생성됩니다.")
        replace_confirmation = input("계속하려면 REPLACE를 입력하세요: ")
        return replace_initial_account(db_path, username, password, confirmation, replace_confirmation)
    return create_initial_account(db_path, username, password, confirmation)


if __name__ == "__main__":
    raise SystemExit(main())
