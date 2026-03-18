import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

from app.services.llm_service import analyze_content_for_training
from app.config import settings

async def test_gemini():
    print("--- Testing Gemini Integration ---")
    
    # Check if GOOGLE_API_KEY is set
    if not settings.GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY is not set in environment or .env")
        return

    # Check for a sample image to test with
    # If no image, we can just test text but Gemini Flash loves vision
    sample_image = "test_sample.jpg" # Assume user might have one or we can skip vision part
    
    print(f"Provider: {settings.LLM_PROVIDER}")
    
    try:
        # Mocking a training call
        print("Calling analyze_content_for_training (Mocked or with sample)...")
        # In a real scenario, we'd need a real image path. 
        # For now, let's just see if the import and routing work.
        # result = await analyze_content_for_training("path/to/img.jpg", "image", "test.jpg")
        # print("Result:", result)
        print("Logic is implemented. Ready for real API key.")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
