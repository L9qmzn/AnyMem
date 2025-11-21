"""
Setup Test Data for Memos

This script helps create test memos with authentication.
You need to provide a valid auth token or session cookie.

How to get auth token:
1. Open Memos in browser (http://localhost:8081)
2. Login to your account
3. Open browser DevTools (F12) -> Network tab
4. Make any request
5. Copy the 'Authorization' header or 'user_session' cookie
"""

import requests
import json
from datetime import datetime


class MemoServiceClient:
    """Client for MemoService REST API"""

    def __init__(self, base_url="http://localhost:8081", auth_token=None, session_cookie=None):
        self.base_url = f"{base_url}/api/v1"
        self.session = requests.Session()

        if auth_token:
            self.session.headers["Authorization"] = f"Bearer {auth_token}"

        if session_cookie:
            self.session.cookies.set("user_session", session_cookie)

    def create_memo(self, content, visibility="PUBLIC", pinned=False):
        """Create a new memo"""
        url = f"{self.base_url}/memos"
        payload = {
            "memo": {
                "content": content,
                "visibility": visibility,
                "pinned": pinned
            }
        }

        response = self.session.post(url, json=payload)

        if response.ok:
            return True, response.json()
        else:
            return False, response.text

    def list_memos(self, filter_expr=None):
        """List memos"""
        params = {}
        if filter_expr:
            params["filter"] = filter_expr

        url = f"{self.base_url}/memos"
        response = self.session.get(url, params=params)

        if response.ok:
            return True, response.json()
        else:
            return False, response.text


def create_test_data(client):
    """Create various test memos"""

    test_memos = [
        {
            "content": "# Welcome to Memos!\n\nThis is a test memo for API testing.",
            "visibility": "PUBLIC",
            "pinned": True
        },
        {
            "content": "## Task List Demo\n\n- [x] Task 1 completed\n- [ ] Task 2 pending\n- [ ] Task 3 pending",
            "visibility": "PUBLIC",
            "pinned": False
        },
        {
            "content": "## Code Example\n\n```python\ndef hello():\n    print('Hello, World!')\n```",
            "visibility": "PUBLIC",
            "pinned": False
        },
        {
            "content": "This memo contains a link: https://github.com/usememos/memos",
            "visibility": "PUBLIC",
            "pinned": False
        },
        {
            "content": "#work #important Meeting notes from today",
            "visibility": "PUBLIC",
            "pinned": False
        },
        {
            "content": "#personal #ideas Random thoughts and ideas",
            "visibility": "PROTECTED",
            "pinned": False
        },
        {
            "content": "This is a private memo for testing",
            "visibility": "PRIVATE",
            "pinned": False
        },
    ]

    created_count = 0
    failed_count = 0

    print("Creating test memos...")
    print("=" * 60)

    for i, memo in enumerate(test_memos, 1):
        success, result = client.create_memo(**memo)

        if success:
            created_count += 1
            memo_name = result.get("name", "unknown")
            print(f"✓ [{i}] Created: {memo_name}")
            print(f"    Visibility: {memo['visibility']}")
            print(f"    Content: {memo['content'][:50]}...")
        else:
            failed_count += 1
            print(f"✗ [{i}] Failed to create memo")
            print(f"    Error: {result}")

        print()

    print("=" * 60)
    print(f"Summary: {created_count} created, {failed_count} failed")

    return created_count


def verify_data(client):
    """Verify created data"""
    print("\n" + "=" * 60)
    print("Verifying created memos...")
    print("=" * 60)

    # Test different filters
    filters = [
        ("All memos", None),
        ("PUBLIC memos", 'visibility == "PUBLIC"'),
        ("Pinned memos", 'pinned == true'),
        ("Memos with code", 'has_code == true'),
        ("Memos with tasks", 'has_task_list == true'),
        ("Memos with links", 'has_link == true'),
    ]

    for name, filter_expr in filters:
        success, result = client.list_memos(filter_expr)

        if success:
            count = len(result.get("memos", []))
            print(f"✓ {name}: {count} found")
        else:
            print(f"✗ {name}: Query failed")


def main():
    print("=" * 60)
    print("Memos Test Data Setup")
    print("=" * 60)

    # Configuration - EDIT THESE VALUES
    BASE_URL = "http://localhost:8081"
    AUTH_TOKEN = None  # Set your JWT token here
    SESSION_COOKIE = "1-c8582ee7-4e60-4091-a711-07135ee13f07"  # Or set your session cookie here

    print(f"\nBase URL: {BASE_URL}")
    print(f"Auth Token: {'Set ✓' if AUTH_TOKEN else 'Not set ✗'}")
    print(f"Session Cookie: {'Set ✓' if SESSION_COOKIE else 'Not set ✗'}")

    if not AUTH_TOKEN and not SESSION_COOKIE:
        print("\n" + "!" * 60)
        print("ERROR: Authentication required!")
        print("!" * 60)
        print("\nPlease set AUTH_TOKEN or SESSION_COOKIE in this script.")
        print("\nHow to get credentials:")
        print("1. Open http://localhost:8081 in your browser")
        print("2. Login to your account")
        print("3. Open DevTools (F12) -> Network tab")
        print("4. Refresh the page or make any action")
        print("5. Click on any request -> Headers tab")
        print("6. Copy either:")
        print("   - 'Authorization' header (format: Bearer xxx)")
        print("   - 'Cookie: user_session=xxx' value")
        print("\nExample:")
        print('   AUTH_TOKEN = "your-token-here"')
        print('   SESSION_COOKIE = "1-abc123def456"')
        return

    client = MemoServiceClient(BASE_URL, AUTH_TOKEN, SESSION_COOKIE)

    # Create test data
    created = create_test_data(client)

    if created > 0:
        # Verify data
        verify_data(client)

        print("\n" + "=" * 60)
        print("Test data created successfully!")
        print("=" * 60)
        print("\nYou can now run the test script:")
        print("  python test_memo_service.py")
    else:
        print("\n" + "!" * 60)
        print("Failed to create test data!")
        print("!" * 60)
        print("\nPlease check:")
        print("1. Memos server is running (http://localhost:8081)")
        print("2. Authentication credentials are valid")
        print("3. You have permission to create memos")


if __name__ == "__main__":
    main()
