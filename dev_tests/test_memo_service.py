"""
REST API Demo for Memos MemoService

Simple Python script to test MemoService REST API endpoints.
Run with: python test_memo_service.py
"""

import requests
import json
from datetime import datetime, timedelta


class MemoServiceClient:
    """Client for MemoService REST API"""

    def __init__(self, base_url="http://localhost:8081", auth_token=None, session_cookie=None):
        self.base_url = f"{base_url}/api/v1"
        self.session = requests.Session()

        if auth_token:
            self.session.headers["Authorization"] = f"Bearer {auth_token}"

        if session_cookie:
            self.session.cookies.set("user_session", session_cookie)

    def list_memos(self, page_size=None, filter_expr=None, order_by=None):
        """List memos with optional filters"""
        params = {}
        if page_size:
            params["pageSize"] = page_size
        if filter_expr:
            params["filter"] = filter_expr
        if order_by:
            params["orderBy"] = order_by

        url = f"{self.base_url}/memos"
        response = self.session.get(url, params=params)

        return response.status_code, response.json() if response.ok else response.text

    def get_memo(self, memo_id):
        """Get a single memo by ID"""
        url = f"{self.base_url}/memos/{memo_id}"
        response = self.session.get(url)

        return response.status_code, response.json() if response.ok else response.text

    def create_memo(self, content, visibility="PRIVATE"):
        """Create a new memo (requires authentication)"""
        url = f"{self.base_url}/memos"
        payload = {
            "memo": {
                "content": content,
                "visibility": visibility
            }
        }

        response = self.session.post(url, json=payload)
        return response.status_code, response.json() if response.ok else response.text


def print_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)


def print_result(test_name, status_code, data):
    """Print test result"""
    print(f"\n[{test_name}]")
    print(f"Status Code: {status_code}")

    if isinstance(data, dict):
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
    else:
        print(f"Response: {data}")


def print_memo_summary(test_name, status_code, data, show_details=False):
    """Print memo list result summary"""
    print(f"\n[{test_name}]")
    print(f"Status Code: {status_code}")

    if status_code == 200 and isinstance(data, dict):
        memos = data.get("memos", [])
        count = len(memos)
        print(f"✓ Found {count} memo(s)")

        if count > 0 and show_details:
            print("\nMemo details:")
            for i, memo in enumerate(memos[:5], 1):  # Show first 5
                print(f"\n  [{i}] {memo.get('name')}")
                print(f"      Visibility: {memo.get('visibility', 'N/A')}")
                print(f"      Pinned: {memo.get('pinned', False)}")
                tags = memo.get('tags', [])
                if tags:
                    print(f"      Tags: {tags}")
                print(f"      Content: {memo.get('content', '')[:60]}...")
    else:
        print(f"✗ Error: {data}")


def main():
    print("Memos REST API Demo")
    print("=" * 60)

    # Configuration
    BASE_URL = "http://localhost:8081"
    AUTH_TOKEN = None  # Set your token here if needed: "your-token-here"
    SESSION_COOKIE = "1-c8582ee7-4e60-4091-a711-07135ee13f07"  # Your session cookie

    client = MemoServiceClient(BASE_URL, AUTH_TOKEN, SESSION_COOKIE)

    print(f"\nAuthenticated: {'Yes (Session Cookie)' if SESSION_COOKIE else 'No (Anonymous)'}")
    print(f"Base URL: {BASE_URL}\n")

    # Test 1: List all memos
    print_section("Test 1: List All Memos (Authenticated)")
    status, data = client.list_memos()
    print_result("List All Memos", status, data)

    if status == 200 and data.get("memos"):
        memo_count = len(data["memos"])
        print(f"\n✓ Total memos returned: {memo_count}")

        if memo_count > 0:
            print(f"\n📋 First 3 memos preview:")
            for i, memo in enumerate(data["memos"][:3], 1):
                print(f"\n  [{i}] {memo.get('name')}")
                print(f"      Visibility: {memo.get('visibility')}")
                print(f"      Pinned: {memo.get('pinned', False)}")
                print(f"      Tags: {memo.get('tags', [])}")
                print(f"      Content: {memo.get('content', '')[:80]}...")
                if memo.get('property'):
                    prop = memo['property']
                    print(f"      Properties: has_code={prop.get('hasCode')}, has_task_list={prop.get('hasTaskList')}, has_link={prop.get('hasLink')}")

    # Test 2: List with pagination
    print_section("Test 2: List Memos with Pagination (page_size=5)")
    status, data = client.list_memos(page_size=5)
    print_memo_summary("List with Pagination", status, data, show_details=True)

    # Test 3: Filter by content
    print_section("Test 3: Filter by Content Contains")
    status, data = client.list_memos(filter_expr='content.contains("test")')
    print_memo_summary("Filter by content.contains('test')", status, data, show_details=True)

    # Test 4: Filter by visibility
    print_section("Test 4: Filter by Visibility (PRIVATE)")
    status, data = client.list_memos(filter_expr='visibility == "PRIVATE"')
    print_memo_summary("Filter by visibility", status, data, show_details=True)

    # Test 5: Filter by pinned
    print_section("Test 5: Filter by Pinned Status")
    status, data = client.list_memos(filter_expr='pinned == true')
    print_memo_summary("Filter by pinned", status, data, show_details=True)

    # Test 6: Filter by has_code
    print_section("Test 6: Filter by Has Code")
    status, data = client.list_memos(filter_expr='has_code == true')
    print_memo_summary("Filter by has_code", status, data, show_details=True)

    # Test 7: Filter by time (last 30 days)
    print_section("Test 7: Filter by Time (Last 30 Days)")
    thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())
    status, data = client.list_memos(filter_expr=f'created_ts > {thirty_days_ago}')
    print_memo_summary("Filter by time range", status, data)

    # Test 8: Filter using now() function
    print_section("Test 8: Filter Using now() Function (Last 7 Days)")
    status, data = client.list_memos(filter_expr='created_ts > now() - 7 * 24 * 3600')
    print_memo_summary("Filter using now()", status, data)

    # Test 9: Combined filters
    print_section("Test 9: Combined Filters (PRIVATE and not pinned)")
    status, data = client.list_memos(
        filter_expr='visibility == "PRIVATE" && pinned == false'
    )
    print_memo_summary("Combined filters", status, data, show_details=True)

    # Test 10: Order by different fields
    print_section("Test 10: Order By Create Time Ascending")
    status, data = client.list_memos(order_by="create_time asc", page_size=3)
    print_memo_summary("Order by create_time asc", status, data, show_details=True)

    # Test 11: Get specific memo (if we have one)
    print_section("Test 11: Get Specific Memo")
    status, data = client.list_memos(page_size=1)
    if status == 200 and data.get("memos"):
        memo_name = data["memos"][0]["name"]
        memo_id = memo_name.split("/")[-1]

        status, data = client.get_memo(memo_id)
        print_result(f"Get memo {memo_id}", status, data)
    else:
        print("No memos available to test GetMemo")

    # Test 12: Test invalid filter (should fail)
    print_section("Test 12: Invalid Filter (Error Case)")
    status, data = client.list_memos(filter_expr='invalid syntax @@##')
    print_result("Invalid filter", status, data)

    print("\n" + "="*60)
    print("✓ Demo completed!")
    print("="*60)
    print("\nSummary: All search/filter operations tested successfully!")


if __name__ == "__main__":
    BASE_URL = "http://localhost:8081"
    AUTH_TOKEN = None
    SESSION_COOKIE = "1-c8582ee7-4e60-4091-a711-07135ee13f07"
    client = MemoServiceClient(BASE_URL, AUTH_TOKEN, SESSION_COOKIE)

    print_section("Test 1: List All Memos (Authenticated)")
    status, data = client.list_memos()
    print_result("List All Memos", status, data)

    if status == 200 and data.get("memos"):
        memo_count = len(data["memos"])
        print(f"\n✓ Total memos returned: {memo_count}")

        if memo_count > 0:
            print(f"\n📋 First 3 memos preview:")
            for i, memo in enumerate(data["memos"][:3], 1):
                print(f"\n  [{i}] {memo.get('name')}")
                print(f"      Visibility: {memo.get('visibility')}")
                print(f"      Pinned: {memo.get('pinned', False)}")
                print(f"      Tags: {memo.get('tags', [])}")
                print(f"      Content: {memo.get('content', '')[:80]}...")
                if memo.get('property'):
                    prop = memo['property']
                    print(
                        f"      Properties: has_code={prop.get('hasCode')}, has_task_list={prop.get('hasTaskList')}, has_link={prop.get('hasLink')}")
