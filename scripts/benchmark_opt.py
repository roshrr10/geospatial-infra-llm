import requests
import time

def benchmark(url, name):
    print(f"--- Benchmarking {name} ---")
    
    # 1. First run (potentially uncached or cold start)
    start = time.time()
    r = requests.get(url)
    cold_time = (time.time() - start) * 1000
    server_time = r.headers.get('X-Query-Time-Ms', 'N/A')
    print(f"Cold Run: {cold_time:.2f}ms (Server: {server_time}ms) | Status: {r.status_code}")
    
    # 2. Second run (should be cached)
    start = time.time()
    r = requests.get(url)
    cached_time = (time.time() - start) * 1000
    server_time = r.headers.get('X-Query-Time-Ms', 'N/A')
    print(f"Cached Run: {cached_time:.2f}ms (Server: {server_time}ms) | Status: {r.status_code}")
    
    return cold_time, cached_time

if __name__ == "__main__":
    # Test Heatmap (Fast now due to vectorization + decoupling)
    benchmark("http://localhost:8000/heatmap?metric=avg_road_density&level=district", "Heatmap Endpoint")
    
    # Test Scoring (Cached)
    # Using POST for scoring
    print("\n--- Benchmarking Scoring Endpoint ---")
    start = time.time()
    r = requests.post("http://localhost:8000/scoring", json={"level": "district"})
    print(f"Cold Run: {(time.time() - start) * 1000:.2f}ms")
    
    start = time.time()
    r = requests.post("http://localhost:8000/scoring", json={"level": "district"})
    print(f"Cached Run: {(time.time() - start) * 1000:.2f}ms")
