"""
Check and fix invalid UTF-8 in SQLite database
"""

import sqlite3
import sys

def check_and_fix_database(db_path, fix=False):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"Checking database: {db_path}")
    print(f"Fix mode: {fix}\n")

    # Get all memos
    cursor.execute("SELECT id, uid, content, payload FROM memo")
    rows = cursor.fetchall()

    print(f"=== Checking {len(rows)} memos ===\n")

    total = len(rows)
    invalid_count = 0
    fixed_count = 0

    for row in rows:
        memo_id, uid, content, payload = row
        has_issue = False

        # Check content
        try:
            # Try to encode to UTF-8
            content.encode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError, AttributeError) as e:
            print(f"❌ Memo ID={memo_id} UID={uid}: Invalid UTF-8 in content")
            print(f"   Error: {e}")
            has_issue = True
            invalid_count += 1

            if fix:
                # Fix by re-encoding
                if isinstance(content, bytes):
                    fixed_content = content.decode('utf-8', errors='replace')
                else:
                    fixed_content = content.encode('utf-8', errors='replace').decode('utf-8')

                cursor.execute("UPDATE memo SET content = ? WHERE id = ?", (fixed_content, memo_id))
                fixed_count += 1
                print(f"   ✓ Fixed")

        # Check payload
        try:
            payload.encode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError, AttributeError) as e:
            print(f"❌ Memo ID={memo_id} UID={uid}: Invalid UTF-8 in payload")
            print(f"   Error: {e}")
            has_issue = True
            invalid_count += 1

            if fix:
                if isinstance(payload, bytes):
                    fixed_payload = payload.decode('utf-8', errors='replace')
                else:
                    fixed_payload = payload.encode('utf-8', errors='replace').decode('utf-8')

                cursor.execute("UPDATE memo SET payload = ? WHERE id = ?", (fixed_payload, memo_id))
                fixed_count += 1
                print(f"   ✓ Fixed")

        # Also check if we can decode as UTF-8 (for BLOB data stored as text)
        if isinstance(content, bytes):
            try:
                content.decode('utf-8')
            except UnicodeDecodeError:
                print(f"⚠️  Memo ID={memo_id} UID={uid}: Content is BLOB data")
                has_issue = True

        if isinstance(payload, bytes):
            try:
                payload.decode('utf-8')
            except UnicodeDecodeError:
                print(f"⚠️  Memo ID={memo_id} UID={uid}: Payload is BLOB data")
                has_issue = True

    if fix:
        conn.commit()

    conn.close()

    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Total memos: {total}")
    print(f"  Issues found: {invalid_count}")
    if fix:
        print(f"  Memos fixed: {fixed_count}")
    else:
        print(f"  (Dry-run mode - no changes made)")
    print(f"{'='*60}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Check and fix UTF-8 issues in database')
    parser.add_argument('--db', default='../memos_dev.db', help='Database file path')
    parser.add_argument('--fix', action='store_true', help='Fix issues (default is dry-run)')

    args = parser.parse_args()

    check_and_fix_database(args.db, args.fix)
