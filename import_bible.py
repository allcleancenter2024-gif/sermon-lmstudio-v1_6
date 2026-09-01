from __future__ import annotations

import argparse
from pathlib import Path

from app.core import DB_PATH, db_stats, import_json


def main() -> None:
    parser = argparse.ArgumentParser(description="허가된 성경 JSON 자료를 로컬 DB에 일괄 등록합니다.")
    parser.add_argument("json_file", type=Path, help="sample_bible_data.json 형식의 JSON 파일")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite DB 경로")
    args = parser.parse_args()
    count = import_json(args.json_file, args.db)
    stats = db_stats(args.db)
    print(f"등록 완료: {count}건 / 전체 {stats['passages']}건 / 번역·자료 {stats['translations']}종")


if __name__ == "__main__":
    main()
