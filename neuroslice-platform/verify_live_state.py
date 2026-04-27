import time
import requests
import redis
import json

def test_live_state():
    print("Connecting to Redis on localhost:6379...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        print("Connected to Redis.")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        return False

    entity_id = "cell-12345"
    
    # 1. Provide mock entity state
    print(f"Pushing mock entity state for {entity_id}...")
    mock_entity = {
        "entity_id": entity_id,
        "node_id": "node-A",
        "site_id": "site-1",
        "domain": "ran",
        "entity_type": "cell",
        "slice_id": "eMBB-1",
        "slice_type": "eMBB",
        "timestamp": time.time(),
        "healthScore": 0.95,
        "congestionScore": 0.1,
        "misroutingScore": 0.05,
        "kpis": json.dumps({"latency": 10, "throughput": 100}),
        "active_faults": json.dumps(["link_down"])
    }
    r.hset(f"entity:{entity_id}", mapping=mock_entity)
    
    # 2. Provide mock aiops states
    print("Pushing mock AIOps states...")
    r.hset(f"aiops:congestion:{entity_id}", mapping={
        "entity_id": entity_id,
        "domain": "ran",
        "timestamp": time.time(),
        "model_name": "CongestionXGB",
        "prediction": "True",
        "confidence": "0.85",
        "severity": "HIGH",
        "explanation": "High user count"
    })
    
    r.hset(f"aiops:sla:{entity_id}", mapping={
        "entity_id": entity_id,
        "domain": "ran",
        "timestamp": time.time(),
        "model_name": "SlaLGBM",
        "prediction": "False",
        "confidence": "0.99",
        "severity": "LOW",
        "explanation": "All KPIs normal"
    })
    
    # 3. Test BFF Endpoints
    print("Testing BFF Endpoints on localhost:8000...")
    base_url = "http://localhost:8000/api/v1/live"
    
    try:
        # Overview
        resp = requests.get(f"{base_url}/overview")
        print("Overview:", resp.json() if resp.status_code == 200 else resp.status_code)
        
        # Entities list
        resp = requests.get(f"{base_url}/entities")
        print("Entities:", resp.json() if resp.status_code == 200 else resp.status_code)
        
        # Single entity
        resp = requests.get(f"{base_url}/entities/{entity_id}")
        data = resp.json() if resp.status_code == 200 else {}
        print(f"Entity {entity_id}:", data)
        assert data.get('entity_id') == entity_id, "Entity endpoint failed"
        
        # AIOps for entity
        resp = requests.get(f"{base_url}/entities/{entity_id}/aiops")
        aiops = resp.json() if resp.status_code == 200 else {}
        print("AIOps:", aiops)
        assert len(aiops) >= 2, "AIOps endpoint did not return expected number of models"
        
        print("\nAll tests passed successfully!")
        return True
    except Exception as e:
        print(f"Error calling BFF endpoints: {e}")
        return False

if __name__ == "__main__":
    test_live_state()
