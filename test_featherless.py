"""
Script untuk test Featherless AI provider secara langsung
"""
import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

token = os.getenv('HF_API_TOKEN')
model = "meta-llama/Meta-Llama-3-8B"

print("=" * 70)
print("TESTING FEATHERLESS AI PROVIDER")
print("=" * 70)

# Test 1: Check token
print("\n[1/3] Checking token...")
if not token:
    print("❌ ERROR: HF_API_TOKEN not found!")
    exit(1)
print(f"✅ Token found: {token[:15]}...")

# Test 2: Initialize Featherless AI client
print("\n[2/3] Initializing Featherless AI client...")
try:
    client = InferenceClient(
        provider="featherless-ai",
        api_key=token
    )
    print("✅ Featherless AI client initialized successfully")
except Exception as e:
    print(f"❌ ERROR initializing Featherless AI: {e}")
    print("\nTrying default client without provider...")
    try:
        client = InferenceClient(api_key=token)
        print("✅ Default client initialized")
    except Exception as e2:
        print(f"❌ ERROR with default client: {e2}")
        exit(1)

# Test 3: Make test inference
print(f"\n[3/3] Testing text generation with model: {model}")
print("Sending test request...")

prompt = (
    "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
    "You are helpful assistant.<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
    "Say hello in 3 words<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
)

try:
    response = client.text_generation(
        prompt,
        model=model,
        max_new_tokens=20,
        temperature=0.7
    )
    
    print("✅ SUCCESS!")
    print(f"Response: {response}")
    print("\n" + "=" * 70)
    print("RESULT: Featherless AI WORKS! ✅")
    print("=" * 70)
    
except Exception as e:
    print(f"❌ ERROR during inference: {e}")
    print(f"Error type: {type(e).__name__}")
    
    # Try to get more details
    if hasattr(e, 'response'):
        print(f"Response status: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
        print(f"Response text: {e.response.text if hasattr(e.response, 'text') else 'N/A'}")
    
    print("\n" + "=" * 70)
    print("RESULT: Featherless AI FAILED! ❌")
    print("=" * 70)
    
    print("\n💡 POSSIBLE SOLUTIONS:")
    print("1. Featherless AI might not support this model")
    print("2. Token might not have correct permissions")
    print("3. Switch to Groq (much better alternative)")
    print("\nWould you like me to help setup Groq instead?")
