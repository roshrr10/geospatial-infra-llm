import requests
import time

def check():
    url = "http://127.0.0.1:8000/heatmap?metric=avg_road_density"
    t0 = time.time()
    r = requests.get(url)
    total = (time.time() - t0) * 1000
    server_side = r.headers.get("X-Query-Time-Ms")
    internal = r.headers.get("X-Internal-Time-Ms")
    print(f"Total Server-Side (Middleware): {server_side}ms")
    print(f"Internal Logic Time: {internal}ms")
    print(f"Total Client-Side Time: {total:.2f}ms")
    
    # Check if it was a cache hit (second run)
    t0 = time.time()
    r = requests.get(url)
    total_cached = (time.time() - t0) * 1000
    server_side_cached = r.headers.get("X-Query-Time-Ms")
    internal_cached = r.headers.get("X-Internal-Time-Ms")
    print(f"\nCached Total Server-Side: {server_side_cached}ms")
    print(f"Cached Internal Logic Time: {internal_cached}ms")
    print(f"Cached Total Client-Side Time: {total_cached:.2f}ms")

if __name__ == "__main__":
    check()
