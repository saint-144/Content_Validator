import os
import httpx
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load .env from root
load_dotenv(".env")

async def test_nvidia_nim():
    api_key = os.getenv("NVIDIA_API_KEY")
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    model = os.getenv("NVIDIA_MODEL", "mistralai/mistral-large-3-675b-instruct-2512")

    if not api_key:
        print("❌ Error: NVIDIA_API_KEY not found in .env")
        return

    print(f"--- NVIDIA NIM Verification ---")
    print(f"URL: {base_url}")
    print(f"Model: {model}")
    print(f"Key: {api_key[:5]}...{api_key[-5:] if len(api_key)>10 else ''}")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Confirm: NVIDIA NIM is online."}],
        "max_tokens": 1024,
        "temperature": 0.2,
        "top_p": 1.0
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print("\nSending request...")
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"✅ Success! Response: {content}")
                print("\nYour NVIDIA NIM integration is properly configured.")
            else:
                print(f"❌ Failed! Status: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error during request: {e}")

if __name__ == "__main__":
    asyncio.run(test_nvidia_nim())
