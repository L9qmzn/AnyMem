"""
Use a real memo from the running MemoService and convert it to LlamaIndex documents.

Prereqs:
- Memo backend running (default http://localhost:8081)
- Session cookie or auth token (env: MEMO_SESSION / MEMO_AUTH_TOKEN)
- Dependencies: requests + llama-index-core (install ai_parts/requirements.txt)
Run:
    python dev_tests/test_memo_loader.py
"""

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Make repo root importable.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import requests

from ai_parts.memo_loader import load_memo_to_llama_docs
from ai_parts import image_captioner
from ai_parts import image_captioner_qwen
from ai_parts.models import Memo
from ai_parts.config import get_settings
from dev_tests.test_memo_service import MemoServiceClient


class MemoLoaderClient(MemoServiceClient):
    """Extend MemoServiceClient with attachment helpers."""

    def __init__(self, base_url: str = "http://localhost:8081", auth_token: Optional[str] = None, session_cookie: Optional[str] = None):
        super().__init__(base_url, auth_token, session_cookie)
        self.root_base = base_url.rstrip("/")

    def list_memo_attachments(self, memo_name: str, page_size: Optional[int] = None) -> Tuple[int, Any]:
        params = {}
        if page_size:
            params["pageSize"] = page_size
        url = f"{self.base_url}/{memo_name}/attachments"
        resp = self.session.get(url, params=params)
        return resp.status_code, resp.json() if resp.ok else resp.text

    def get_attachment_binary(self, attachment_name: str, filename: str, thumbnail: bool = False) -> Tuple[int, Union[bytes, str]]:
        params = {"thumbnail": "true"} if thumbnail else {}
        url = f"{self.root_base}/file/{attachment_name}/{filename}"
        resp = self.session.get(url, params=params)
        return resp.status_code, resp.content if resp.ok else resp.text


def _enrich_attachments(client: MemoLoaderClient, memo: Dict[str, Any]) -> List[Dict[str, Any]]:
    attachments = memo.get("attachments") or []
    # If list endpoint didn't include attachments, fetch explicitly.
    if not attachments:
        status, data = client.list_memo_attachments(memo["name"])
        if status == 200 and isinstance(data, dict):
            attachments = data.get("attachments") or []

    enriched: List[Dict[str, Any]] = []
    for att in attachments:
        att_copy = dict(att)
        # If no remote link, try to fetch binary and embed as base64.
        if not att_copy.get("externalLink"):
            status, blob = client.get_attachment_binary(att_copy["name"], att_copy["filename"])
            if status == 200 and isinstance(blob, (bytes, bytearray)):
                att_copy["content"] = base64.b64encode(blob).decode("utf-8")
        enriched.append(att_copy)
    return enriched


def demo_first_memo():
    base_url = os.getenv("MEMO_API_BASE", "http://localhost:8081")
    auth_token = os.getenv("MEMO_AUTH_TOKEN")
    session_cookie = os.getenv("MEMO_SESSION", "1-c8582ee7-4e60-4091-a711-07135ee13f07")

    client = MemoLoaderClient(base_url, auth_token, session_cookie)

    status, data = client.list_memos(page_size=5)
    if status != 200 or not isinstance(data, dict) or not data.get("memos"):
        print(f"Failed to list memos: {status} {data}")
        return

    memos = data["memos"]
    memo_raw = next((m for m in memos if m.get("attachments") and m.get("content")), None)
    if memo_raw is None:
        memo_raw = next((m for m in memos if m.get("attachments")), None)
    if memo_raw is None:
        memo_raw = next((m for m in memos if m.get("content")), memos[0])
    memo_raw["attachments"] = _enrich_attachments(client, memo_raw)

    memo_model = Memo.model_validate(memo_raw)

    settings = get_settings()
    caption_fn = None
    if settings.use_image_caption:
        def _caption(image_payload: str, meta: dict) -> Optional[str]:
            hint = meta.get("filename") or meta.get("attachment_uid")
            if settings.vision_provider.lower() == "qwen":
                print(f"Using Qwen captioner for image: {hint}")
                return image_captioner_qwen.generate_caption(image_payload, hint=hint)
            print(f"Using OpenAI captioner for image: {hint}")
            return image_captioner.generate_caption(image_payload, hint=hint)
        caption_fn = _caption

    mm_docs = load_memo_to_llama_docs(memo_model, image_caption_fn=caption_fn)

    print("\n=== Memo Loader Demo ===")
    print(f"Memo: {memo_model.name}")
    print(f"Base doc id: {mm_docs.base_doc.doc_id}")
    print(f"Base text length: {len(mm_docs.base_doc.text)}")
    print(f"Base metadata keys: {sorted(mm_docs.base_doc.metadata.keys())}")
    if mm_docs.image_docs:
        first_img = mm_docs.image_docs[0]
        caption_preview = (first_img.text or "").strip()
        print(f"Image docs: {len(mm_docs.image_docs)}, first id={first_img.doc_id}, type={first_img.metadata.get('type')}")
        print(f"First image text/caption: {caption_preview or '(empty)'}")
    else:
        print("Image docs: 0")
    if mm_docs.attachment_docs:
        first_att = mm_docs.attachment_docs[0]
        print(f"Attachment docs: {len(mm_docs.attachment_docs)}, first id={first_att.doc_id}, type={first_att.metadata.get('type')}, text_len={len(first_att.text)}")
    else:
        print("Attachment docs: 0")
    print("\nBase doc preview:")
    print(mm_docs.base_doc.text[:500])
    print("\nSerialized base metadata:")
    print(json.dumps(mm_docs.base_doc.metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo_first_memo()
