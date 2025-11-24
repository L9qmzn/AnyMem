"""
Index manager for incremental updates (add, update, delete).
Manages persistent vector indexes for memos.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from chromadb import PersistentClient
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import Document, ImageDocument
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.vector_stores.chroma import ChromaVectorStore

from ai_parts.config import get_settings
from ai_parts.indexing.memo_loader import MemoMultimodalDocs


class IndexManager:
    """
    Manages text and image vector indexes with incremental update support.
    """

    def __init__(
        self,
        text_persist_dir: Path,
        image_persist_dir: Path,
        text_collection: str,
        image_collection: str,
        text_embed_model: BaseEmbedding,
        image_embed_model: Optional[BaseEmbedding] = None,
    ):
        self.text_persist_dir = Path(text_persist_dir)
        self.image_persist_dir = Path(image_persist_dir)
        self.text_collection = text_collection
        self.image_collection = image_collection
        self.text_embed_model = text_embed_model
        self.image_embed_model = image_embed_model or text_embed_model

        # Ensure directories exist
        self.text_persist_dir.mkdir(parents=True, exist_ok=True)
        self.image_persist_dir.mkdir(parents=True, exist_ok=True)

        # Load or create indexes
        self.text_index = self._load_or_create_text_index()
        self.image_index = self._load_or_create_image_index()

        # Load memo -> vector mapping
        self.memo_vector_map = self._load_memo_vector_map()

    def _build_chroma_context(self, persist_dir: Path, collection: str) -> StorageContext:
        """Build ChromaDB storage context."""
        client = PersistentClient(path=str(persist_dir))
        vector_store = ChromaVectorStore(
            chroma_collection=client.get_or_create_collection(name=collection),
        )
        return StorageContext.from_defaults(
            docstore=SimpleDocumentStore(),
            vector_store=vector_store,
        )

    def _load_or_create_text_index(self) -> VectorStoreIndex:
        """Load existing text index or create a new one."""
        storage_context = self._build_chroma_context(self.text_persist_dir, self.text_collection)

        try:
            # Try to load existing index
            index = VectorStoreIndex.from_vector_store(
                storage_context.vector_store,
                embed_model=self.text_embed_model,
            )
            return index
        except Exception:
            # Create new empty index
            return VectorStoreIndex.from_documents(
                [],
                storage_context=storage_context,
                embed_model=self.text_embed_model,
            )

    def _load_or_create_image_index(self) -> Optional[VectorStoreIndex]:
        """Load existing image index or create a new one."""
        storage_context = self._build_chroma_context(self.image_persist_dir, self.image_collection)

        try:
            index = VectorStoreIndex.from_vector_store(
                storage_context.vector_store,
                embed_model=self.image_embed_model,
            )
            return index
        except Exception:
            return VectorStoreIndex.from_documents(
                [],
                storage_context=storage_context,
                embed_model=self.image_embed_model,
            )

    def _load_memo_vector_map(self) -> Dict[str, Dict[str, List[str]]]:
        """Load memo -> vector IDs mapping from disk."""
        map_path = self.text_persist_dir / "memo_vector_map.json"
        if map_path.exists():
            try:
                return json.loads(map_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Warning: Failed to load memo_vector_map: {e}")
        return {}

    def _save_memo_vector_map(self):
        """Save memo -> vector IDs mapping to disk."""
        map_path = self.text_persist_dir / "memo_vector_map.json"
        map_path.write_text(
            json.dumps(self.memo_vector_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_or_update_memo(self, docs: MemoMultimodalDocs) -> Tuple[int, int]:
        """
        Add or update a memo in the indexes.
        If memo already exists, delete old vectors first.

        Args:
            docs: MemoMultimodalDocs from load_memo_to_llama_docs

        Returns:
            (text_vectors_added, image_vectors_added)
        """
        memo_uid = docs.base_doc.metadata.get("memo_uid")
        if not memo_uid:
            raise ValueError("memo_uid not found in document metadata")

        # Delete existing vectors if present
        if memo_uid in self.memo_vector_map:
            self.delete_memo(memo_uid)

        # Add text documents (base + attachments)
        text_docs = [docs.base_doc] + docs.attachment_docs
        text_vector_ids = []

        for doc in text_docs:
            self.text_index.insert(doc)
            text_vector_ids.append(doc.doc_id)

        # Add image documents
        image_vector_ids = []
        if docs.image_docs and self.image_index:
            for img_doc in docs.image_docs:
                self.image_index.insert(img_doc)
                image_vector_ids.append(img_doc.doc_id)

        # Update mapping
        self.memo_vector_map[memo_uid] = {
            "text": text_vector_ids,
            "image": image_vector_ids,
        }
        self._save_memo_vector_map()

        return len(text_vector_ids), len(image_vector_ids)

    def delete_memo(self, memo_uid: str) -> Tuple[int, int]:
        """
        Delete all vectors for a memo.

        Args:
            memo_uid: Memo UID (e.g., "memos/abc123")

        Returns:
            (text_vectors_deleted, image_vectors_deleted)
        """
        if memo_uid not in self.memo_vector_map:
            return 0, 0

        mapping = self.memo_vector_map[memo_uid]

        # Delete text vectors
        text_deleted = 0
        for doc_id in mapping.get("text", []):
            try:
                self.text_index.delete_ref_doc(doc_id, delete_from_docstore=True)
                text_deleted += 1
            except Exception as e:
                print(f"Warning: Failed to delete text vector {doc_id}: {e}")

        # Delete image vectors
        image_deleted = 0
        if self.image_index:
            for doc_id in mapping.get("image", []):
                try:
                    self.image_index.delete_ref_doc(doc_id, delete_from_docstore=True)
                    image_deleted += 1
                except Exception as e:
                    print(f"Warning: Failed to delete image vector {doc_id}: {e}")

        # Remove from mapping
        del self.memo_vector_map[memo_uid]
        self._save_memo_vector_map()

        return text_deleted, image_deleted

    def get_memo_info(self, memo_uid: str) -> Optional[Dict]:
        """Get indexing info for a specific memo."""
        if memo_uid not in self.memo_vector_map:
            return None

        mapping = self.memo_vector_map[memo_uid]
        return {
            "memo_uid": memo_uid,
            "indexed": True,
            "text_vector_ids": mapping.get("text", []),
            "image_vector_ids": mapping.get("image", []),
            "text_count": len(mapping.get("text", [])),
            "image_count": len(mapping.get("image", [])),
        }

    def get_index_status(self) -> Dict:
        """Get overall index status."""
        total_text = sum(len(m.get("text", [])) for m in self.memo_vector_map.values())
        total_image = sum(len(m.get("image", [])) for m in self.memo_vector_map.values())

        return {
            "total_memos": len(self.memo_vector_map),
            "total_text_vectors": total_text,
            "total_image_vectors": total_image,
            "collections": {
                "text": self.text_collection,
                "image": self.image_collection,
            },
            "persist_dirs": {
                "text": str(self.text_persist_dir),
                "image": str(self.image_persist_dir),
            },
        }


def create_index_manager(
    text_embed_model: BaseEmbedding,
    image_embed_model: Optional[BaseEmbedding] = None,
    base_dir: Optional[Path] = None,
) -> IndexManager:
    """
    Factory function to create IndexManager with default settings.
    """
    settings = get_settings()

    if base_dir is None:
        base_dir = Path(".memo_indexes/chroma")

    text_persist_dir = base_dir / "text"
    image_persist_dir = base_dir / "image"

    # Build collection names from model names
    text_model_name = getattr(text_embed_model, "model_name", text_embed_model.__class__.__name__)
    col_suffix = text_model_name.replace("/", "_").replace("-", "_")
    text_collection = f"memo_text_{col_suffix}"
    image_collection = f"memo_image_{col_suffix}"

    return IndexManager(
        text_persist_dir=text_persist_dir,
        image_persist_dir=image_persist_dir,
        text_collection=text_collection,
        image_collection=image_collection,
        text_embed_model=text_embed_model,
        image_embed_model=image_embed_model,
    )
