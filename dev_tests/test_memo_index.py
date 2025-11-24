"""
Build LlamaIndex indexes from real memos (text + image).

Prereqs:
- Backend running on http://localhost:8081 (override via MEMO_API_BASE)
- Session/token via env MEMO_SESSION / MEMO_AUTH_TOKEN
- Embedding models: by default uses LlamaIndex defaults; swap in Jina embeddings when available.

Run:
    python dev_tests/test_memo_index.py
"""

import os
import sys
import time
from pathlib import Path

# Make repo root importable.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from ai_parts.index_service import build_memo_indexes
from ai_parts.memo_loader import load_memo_to_llama_docs
from ai_parts.models import Memo
from ai_parts.config import get_settings
from ai_parts.embeddings import get_jina_embeddings
from dev_tests.test_memo_loader import MemoLoaderClient, _enrich_attachments
from llama_index.core.embeddings import MockEmbedding
from ai_parts import image_captioner


def main():
    t0 = time.time()
    settings = get_settings()
    base_url = os.getenv("MEMO_API_BASE", "http://localhost:8081")
    auth_token = os.getenv("MEMO_AUTH_TOKEN")
    session_cookie = os.getenv("MEMO_SESSION", "1-c8582ee7-4e60-4091-a711-07135ee13f07")

    client = MemoLoaderClient(base_url, auth_token, session_cookie)
    print(f"[0] Fetching memos from {base_url} ...")
    status, data = client.list_memos(page_size=5)
    if status != 200 or not data.get("memos"):
        print(f"List memos failed: {status} {data}")
        return

    print(f"[1] Got {len(data['memos'])} memos, enriching attachments ...")
    memo_models = []
    for memo_raw in data["memos"]:
        memo_raw["attachments"] = _enrich_attachments(client, memo_raw)
        memo_models.append(Memo.model_validate(memo_raw))

    print(f"[2] use_image_caption={settings.use_image_caption}, vision_provider={settings.vision_provider}")
    caption_fn = None
    if settings.use_image_caption:
        def _caption(image_payload: str, meta: dict) -> str | None:
            hint = meta.get("filename") or meta.get("attachment_uid")
            if settings.vision_provider.lower() == "qwen":
                from ai_parts import image_captioner_qwen
                return image_captioner_qwen.generate_caption(image_payload, hint=hint)
            return image_captioner.generate_caption(image_payload, hint=hint)
        caption_fn = _caption

    print(f"[3] Converting to LlamaIndex docs ...")
    docs = [load_memo_to_llama_docs(m, image_caption_fn=caption_fn) for m in memo_models]
    text_count = sum(1 + len(d.attachment_docs) for d in docs)
    image_count = sum(len(d.image_docs) for d in docs)

    text_embed, image_embed = get_jina_embeddings(settings)
    if text_embed is None:
        text_embed = MockEmbedding(embed_dim=512)
    if image_embed is None:
        image_embed = text_embed

    print(f"[4] Embeddings ready: text={getattr(text_embed, 'model_name', text_embed.__class__.__name__)}, image={getattr(image_embed, 'model_name', image_embed.__class__.__name__)}")

    # Use current working directory for index path (allows different paths for dev_tests vs root)
    persist_dir = Path(os.getenv("MEMO_INDEX_DIR", ".memo_indexes/chroma")).resolve()
    col_suffix = getattr(text_embed, "model_name", text_embed.__class__.__name__).replace("/", "_").replace("-", "_")
    text_collection = f"memo_text_{col_suffix}"
    image_collection = f"memo_image_{col_suffix}"

    print(f"[5] Building indexes into {persist_dir} (text_collection={text_collection}, image_collection={image_collection}) ...")
    bundle = build_memo_indexes(
        docs,
        text_embed_model=text_embed,
        image_embed_model=image_embed,
        text_persist_dir=persist_dir / "text",
        image_persist_dir=persist_dir / "image",
        text_collection=text_collection,
        image_collection=image_collection,
    )
    bundle.persist()

    print("Built indexes:")
    print(f"- Text docs (input): {text_count}")
    if bundle.image_index:
        print(f"- Image docs (input): {image_count}")
    else:
        print("- Image docs: 0 (no images or image index not built)")
    print(f"Persisted to: {persist_dir}")
    print("Memo -> vector IDs mapping (counts):")
    for memo_uid, ids in bundle.memo_vector_map.items():
        print(f"  {memo_uid}: text={len(ids.get('text', []))}, image={len(ids.get('image', []))}")
    print(f"Total elapsed: {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
