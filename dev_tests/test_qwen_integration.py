"""
Quick test to verify Qwen captioner integration
"""
import os
import sys
from pathlib import Path

# Make repo root importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from ai_parts.config import get_settings
from ai_parts import image_captioner_qwen


def test_config():
    """Test if configuration is loaded correctly"""
    print("=== Testing Configuration ===")
    settings = get_settings()

    print(f"Vision Provider: {settings.vision_provider}")
    print(f"Image Caption Model: {settings.image_caption_model}")
    print(f"Dashscope Base URL: {settings.dashscope_base_url}")
    print(f"Dashscope API Key: {'SET' if settings.dashscope_api_key else 'NOT SET'}")

    if not settings.dashscope_api_key:
        print("\n[!] Warning: DASHSCOPE_API_KEY environment variable is not set!")
        print("Please set it using:")
        print("  Windows: set DASHSCOPE_API_KEY=your_api_key")
        print("  Linux/Mac: export DASHSCOPE_API_KEY=your_api_key")
        return False

    return True


def test_captioner():
    """Test Qwen captioner with a sample image"""
    print("\n=== Testing Qwen Captioner ===")

    if not test_config():
        print("\nSkipping captioner test - API key not configured")
        return

    # Test image URL (replace with your own)
    test_image = "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"

    print(f"\nTesting with image: {test_image}")
    print("Generating caption...")

    try:
        caption = image_captioner_qwen.generate_caption(
            image=test_image,
            hint="测试图片",
        )

        if caption:
            print("\n[+] Caption generated successfully:")
            print("-" * 60)
            print(caption)
            print("-" * 60)
        else:
            print("\n[-] Caption generation returned None")

    except Exception as e:
        print(f"\n[X] Error during caption generation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Qwen Captioner Integration Test\n")

    # Test 1: Check configuration
    config_ok = test_config()

    # Test 2: Test captioner (only if config is OK)
    if config_ok:
        test_captioner()
    else:
        print("\n" + "=" * 60)
        print("Setup Instructions:")
        print("=" * 60)
        print("1. Get your Dashscope API key from: https://help.aliyun.com/zh/model-studio/get-api-key")
        print("2. Set the environment variable:")
        print("   Windows: set DASHSCOPE_API_KEY=sk-xxx")
        print("   Linux/Mac: export DASHSCOPE_API_KEY=sk-xxx")
        print("3. Run this test again")
        print("=" * 60)
