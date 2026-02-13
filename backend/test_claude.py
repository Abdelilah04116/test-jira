
import asyncio
import anthropic
import os
from dotenv import load_dotenv

async def check_key():
    load_dotenv()
    api_key = os.getenv("CLAUDE_API_KEY")
    print(f"Testing key: {api_key[:10]}... (len: {len(api_key)})")
    
    client = anthropic.AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print("✅ Key is valid!")
    except Exception as e:
        print(f"❌ Key is invalid: {e}")

if __name__ == "__main__":
    asyncio.run(check_key())
