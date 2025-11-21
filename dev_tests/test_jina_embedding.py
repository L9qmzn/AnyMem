"""
Quick Jina embedding smoke test for text and image.
"""
import base64
import io
import sys
from pathlib import Path

from PIL import Image

# Make repo root importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from ai_parts.config import get_settings
from ai_parts.embeddings import get_jina_embeddings


def main():
    settings = get_settings()
    text_embed, image_embed = get_jina_embeddings(settings)

    if not text_embed or not image_embed:
        print("Jina API key not set; please configure jina_api_key in ai_parts/config*.py")
        sys.exit(1)

    # Text test
    texts = [
        "这是一个关于大模型基准测试的 memo 内容。",
        "Gemini 3 Pro 在多模态基准上表现更好。",
    ]
    try:
        text_vectors = text_embed.get_text_embedding_batch(texts)
        print(f"Text embeddings ok. dim={len(text_vectors[0])}, count={len(text_vectors)}")
    except Exception as e:
        print(f"Text embedding failed: {e}")
        sys.exit(1)

    # Image test: generate a 32x32 red PNG and base64 encode
    img = Image.new("RGB", (32, 32), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_img = base64.b64encode(buf.getvalue()).decode("ascii")

    try:
        img_vec = image_embed.get_image_embedding(b64_img)
        print(f"Image embedding ok. dim={len(img_vec)}")
    except Exception as e:
        print(f"Image embedding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
