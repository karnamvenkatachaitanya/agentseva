import requests
import json
import base64
import time

API_URL = "http://localhost:8000"

def test_health():
    print("Testing Backend health...")
    try:
        # Just check if we can connect, maybe /docs
        requests.get(f"{API_URL}/docs")
        print("Backend is up!")
    except:
        print("Backend seems down. Please start it with 'uvicorn backend.main:app'")
        return False
    return True

def test_rag_flow(text_query):
    print(f"\n--- Testing RAG Flow with query: '{text_query}' ---")
    
    # 1. Simulate STT (Mocking the endpoint call or just skipping to RAG since we don't have an audio file handy)
    # But let's test the RAG endpoint directly as that's the core logic.
    payload = {"text": text_query}
    
    start_time = time.time()
    response = requests.post(f"{API_URL}/rag-query", json=payload)
    end_time = time.time()
    
    if response.status_code == 200:
        data = response.json()
        print(f"Time taken: {end_time - start_time:.2f}s")
        print(f"AI Response: {data['response_text']}")
        
        if data.get('order'):
            print("Order Generated:")
            print(json.dumps(data['order'], indent=2))
        else:
            print("No order generated.")
    else:
        print("Error:", response.text)

def main():
    if not test_health():
        return

    # 1. Ask general question
    test_rag_flow("What do you have for dinner?")
    
    # 2. Place an order
    test_rag_flow("I'll have two classic burgers and a lemonade")
    
    # 3. Ask about unknown item
    test_rag_flow("Do you sell Pizza?")

if __name__ == "__main__":
    main()
