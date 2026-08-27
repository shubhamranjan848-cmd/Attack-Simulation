import asyncio
import aiohttp
import random
import string
import sys
import time
from datetime import datetime

# --- CONFIGURATION ---
# TARGET: Must be a server you own. 
# Defaulting to localhost:8080 (The local test server from the menu script).
TARGET_URL = "file:///C:/Users/vijay/.gemini/antigravity/scratch/traffic-dashboard/index.html" 

# TOXIC SETTINGS
MAX_CONCURRENT_TASKS = 20 # Start lower to avoid immediate OS blocking, then ramp up
REQUESTS_PER_TASK = 5     # Requests per worker before rotating
MAX_RETRIES = 3           # -1 means INFINITE retries until success

# COUNTERS
successful_requests = 0
failed_requests = 0
total_attempts = 0
stop_event = asyncio.Event()
success_event = asyncio.Event()  # Signal when at least one request succeeds

def generate_random_path():
    """Generates random paths to bypass caching and WAF rules."""
    return '/' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(10, 30)))

def generate_random_headers():
    """Generates random headers to look like diverse traffic."""
    return {
        'User-Agent': random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ]),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }

async def toxic_worker(session, worker_id):
    global successful_requests, failed_requests, total_attempts
    
    # Wait for the start signal if we are in a coordinated start (optional, here we start immediately)
    
    while not success_event.is_set() and not stop_event.is_set():
        if success_event.is_set():
            break
            
        path = generate_random_path()
        target = f"{TARGET_URL}{path}"
        headers = generate_random_headers()
        
        try:
            total_attempts += 1
            
            # Aggressive timeout: If they don't respond in 2s, they are likely filtering or dead.
            # We retry immediately.
            async with session.get(target, headers=headers, timeout=aiohttp.ClientTimeout(total=2.0, connect=1.0)) as response:
                # ANY response (200, 403, 404, 500) counts as a successful connection!
                # Only connection errors (timeout, refused) are failures.
                successful_requests += 1
                print(f"\n[SUCCESS] Worker {worker_id}: Got response {response.status} from {TARGET_URL}")
                print(f"[SUCCESS] TARGET IS REACHABLE. Request count: {successful_requests}")
                success_event.set()  # Signal that we succeeded
                return
                
        except asyncio.TimeoutError:
            failed_requests += 1
            # Silent fail, just retry
        except aiohttp.ClientError as e:
            failed_requests += 1
            # Connection refused, SSL error, etc.
            # DO NOT STOP. This is the "Toxic" part. We keep trying.
        except Exception as e:
            failed_requests += 1
            # Unknown error, keep trying

        # Tiny random delay to prevent pattern detection by simple IDS
        await asyncio.sleep(random.uniform(0.001, 0.01))

async def run_toxic_attack():
    global successful_requests, failed_requests, total_attempts
    
    print(f"--- TOXIC FLOOD INITIATED ---")
    print(f"Target: {TARGET_URL}")
    print(f"Strategy: Persistent Retry Until First Success")
    print(f"Note: This will run indefinitely until a single request succeeds or you press Ctrl+C.")
    print("Waiting for target response...")
    print("-----------------------------")

    # Use a connector that allows high concurrency but respects OS limits
    conn = aiohttp.TCPConnector(limit=MAX_CONCURRENT_TASKS, limit_per_host=MAX_CONCURRENT_TASKS, ssl=False)
    
    start_time = datetime.now()
    
    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = []
        
        # Launch workers
        for i in range(MAX_CONCURRENT_TASKS):
            task = asyncio.create_task(toxic_worker(session, i))
            tasks.append(task)
        
        # Monitor for success or user interrupt
        try:
            # Wait for either:
            # 1. All tasks finish (unlikely as they loop)
            # 2. User interrupt
            # 3. Success event is set (handled by the loop checking the flag)
            
            while not success_event.is_set():
                if stop_event.is_set():
                    break
                await asyncio.sleep(1.0)
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed % 10 == 0:
                    print(f"[...] Still trying... Attempts: {total_attempts}, Failures: {failed_requests}, Successes: {successful_requests}")
                    print(f"[...] TIP: Ensure a server is running on {TARGET_URL}. If targeting external sites, they are likely blocking you.")
                
        except KeyboardInterrupt:
            print("\n\n[!] User interrupted. Stopping...")
        finally:
            stop_event.set()
            # Cancel all pending tasks
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print("\n\n--- FINAL REPORT ---")
            print(f"Duration: {duration:.2f} seconds")
            print(f"Total Attempts: {total_attempts}")
            print(f"Successful Connections (HTTP Response Received): {successful_requests}")
            print(f"Failed Connections (Network Level): {failed_requests}")
            
            if successful_requests > 0:
                print("\n[✓] SUCCESS: At least one request passed through.")
            else:
                print("\n[✗] FAILURE: No requests succeeded.")
                print("Possible reasons:")
                f"1. Target {TARGET_URL} is not running or not reachable."
                print("2. Firewall/Antivirus is blocking ALL outbound connections from Python.")
                print("3. Target is using a WAF that blocks the connection before it completes the handshake.")
            print("------------------------------------")

if __name__ == "__main__":
    # No deprecated event loop policy
    try:
        asyncio.run(run_toxic_attack())
    except KeyboardInterrupt:
        print("\nTerminated.")
        sys.exit(0)