import os
import httpx
import asyncio
import base64
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env")

async def ping_nvidia_nim():
    api_key = os.getenv("NVIDIA_API_KEY")
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    model = os.getenv("NVIDIA_MODEL", "mistralai/mistral-large-3-675b-instruct-2512")

    if not api_key:
        print("❌ Error: NVIDIA_API_KEY not found in .env")
        return

    print(f"--- NVIDIA NIM Diagnostic ---")
    print(f"Endpoint: {base_url}/chat/completions")
    print(f"Model:    {model}")
    print("-" * 30)

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # 1. Test Text Connectivity
        print("\n[1/3] Testing Text Connectivity...")
        text_payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Ping? Reply only with 'Pong'."}],
            "max_tokens": 10
        }
        try:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=text_payload)
            if resp.status_code == 200:
                print(f"✅ Text Success: {resp.json()['choices'][0]['message']['content'].strip()}")
            else:
                print(f"❌ Text Failed! Status: {resp.status_code}")
                print(f"   Response: {resp.text}")
        except Exception as e:
            print(f"❌ Text Error: {e}")

        # 2. Test Vision Capability (1x1 transparent pixel)
        print("\n[2/3] Testing Vision Capability...")
        # Smallest possible 1x1 transparent PNG
        pixel_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        vision_payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe the content of this image."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{pixel_b64}"}}
                    ]
                }
            ],
            "max_tokens": 50
        }
        try:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=vision_payload)
            if resp.status_code == 200:
                print(f"✅ Vision Success: {resp.json()['choices'][0]['message']['content'].strip()}")
            elif resp.status_code == 400:
                print(f"❌ Vision Refused (400 Bad Request)!")
                print(f"   Note: This usually means the model does not support image_url payloads.")
                print(f"   Response: {resp.text}")
            else:
                print(f"❌ Vision Failed! Status: {resp.status_code}")
                print(f"   Response: {resp.text}")
        except Exception as e:
            print(f"❌ Vision Error: {e}")

        # 3. Test Large Prompt (Simulate validation context)
        print("\n[3/3] Testing Large Prompt Capacity...")
        # Generate ~10k chars of dummy context
        dummy_context = "Word " * 2000 
        large_payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": f"Context: {dummy_context}\n\nTask: Say 'Large Prompt OK'."
                }
            ],
            "max_tokens": 10
        }
        try:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=large_payload)
            if resp.status_code == 200:
                print(f"✅ Large Prompt Success: {resp.json()['choices'][0]['message']['content'].strip()}")
            else:
                print(f"❌ Large Prompt Failed! Status: {resp.status_code}")
                print(f"   Response: {resp.text}")
        except Exception as e:
            print(f"❌ Large Prompt Error: {e}")

    print("\n--- Diagnostic Complete ---")

if __name__ == "__main__":
    asyncio.run(ping_nvidia_nim())
