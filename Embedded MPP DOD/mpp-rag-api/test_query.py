"""
Simple test script to query the MPP RAG API
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    response = requests.get(f"{BASE_URL}/health")
    print(json.dumps(response.json(), indent=2))

def test_query():
    """Test query endpoint"""
    print("\n=== Testing Query Endpoint ===")

    payload = {
        "question": "What are the requirements for mentor eligibility?",
        "top_k": 3,
        "doc_type": None
    }

    response = requests.post(f"{BASE_URL}/query", json=payload)

    if response.status_code == 200:
        result = response.json()
        print(f"\nQuestion: {result['query']}")
        print(f"\nAnswer:\n{result['answer']}")
        print(f"\n--- Sources ---")
        for i, source in enumerate(result['sources'], 1):
            print(f"\n[{i}] {source['document']} (Page {source['page']})")
            print(f"Confidence: {source['confidence']:.2f}")
            print(f"Quote: {source['quote'][:200]}...")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

def test_extract():
    """Test extract endpoint"""
    print("\n=== Testing Extract Endpoint ===")

    payload = {
        "document": "MPP SOP.pdf",
        "page": 1
    }

    response = requests.post(f"{BASE_URL}/extract", json=payload)

    if response.status_code == 200:
        result = response.json()
        print(f"\nDocument: {result['document']}")
        print(f"Page: {result['page']}")
        print(f"Total extracts: {result['total_extracts']}")
        if result['extracts']:
            print(f"\nFirst extract:\n{result['extracts'][0]['text'][:300]}...")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    print("="*60)
    print("MPP RAG API Test Suite")
    print("="*60)

    try:
        test_health()
        test_query()
        test_extract()

        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60)

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to API server")
        print("Make sure the server is running: python api_server.py")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
