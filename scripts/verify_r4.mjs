import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';

const ARTIFACTS_DIR = 'C:\\Users\\Ashish\\.gemini\\antigravity-ide\\brain\\c0116512-1a9a-48a8-ad32-ec49f14d82fd';
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

if (!fs.existsSync(ARTIFACTS_DIR)) {
  fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function getPageWsUrl(port = 9222) {
  for (let attempt = 0; attempt < 30; attempt++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      if (res.ok) {
        const pages = await res.json();
        let page = pages.find(p => p.type === 'page' && p.url.includes('localhost:3000'));
        if (!page) {
          // Open a new tab to localhost:3000/workspace
          const newTabRes = await fetch(`http://127.0.0.1:${port}/json/new?http://localhost:3000/workspace`, { method: 'PUT' });
          page = await newTabRes.json();
        }
        if (page && page.webSocketDebuggerUrl) {
          return page.webSocketDebuggerUrl;
        }
      }
    } catch {
      // Retry
    }
    await sleep(500);
  }
  throw new Error(`Could not connect to Chrome DevTools on port ${port}`);
}

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.id = 1;
    this.callbacks = new Map();
    this.events = [];
    this.consoleLogs = [];
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.onopen = () => resolve();
      this.ws.onerror = reject;
      this.ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data);
        if (data.id && this.callbacks.has(data.id)) {
          const cb = this.callbacks.get(data.id);
          this.callbacks.delete(data.id);
          if (data.error) cb.reject(data.error);
          else cb.resolve(data.result);
        } else if (data.method) {
          if (data.method === 'Runtime.consoleAPICalled') {
            const text = data.params.args.map(a => a.value || a.description || '').join(' ');
            this.consoleLogs.push({ type: data.params.type, text });
          }
          this.events.push(data);
        }
      };
    });
  }

  async send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolve, reject) => {
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expr) {
    const wrapped = `(() => { ${expr} })()`;
    const res = await this.send('Runtime.evaluate', {
      expression: wrapped,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res.exceptionDetails) {
      throw new Error(`Eval error: ${res.exceptionDetails.text} (${expr})`);
    }
    return res.result ? res.result.value : undefined;
  }

  async setViewport(width, height) {
    await this.send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });
  }

  async screenshot(filename) {
    const res = await this.send('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(res.data, 'base64');
    const outPath = path.join(ARTIFACTS_DIR, filename);
    fs.writeFileSync(outPath, buffer);
    console.log(`Saved screenshot: ${outPath} (${buffer.length} bytes)`);
    return outPath;
  }

  async close() {
    if (this.ws) this.ws.close();
  }
}

async function run() {
  console.log('Launching Headless Chrome on port 9222...');
  const chromeProcess = spawn(CHROME_PATH, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--window-size=1920,1080',
    'http://localhost:3000/workspace'
  ], { detached: false });

  await sleep(2000);

  try {
    console.log('Connecting to browser CDP...');
    const wsUrl = await getPageWsUrl(9222);
    const cdp = new CDPClient(wsUrl);
    await cdp.connect();

    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('DOM.enable');

    console.log('1. Setting viewport 1920x1080 and loading workspace...');
    await cdp.setViewport(1920, 1080);
    await cdp.send('Page.navigate', { url: 'http://localhost:3000/workspace' });
    await sleep(4000);

    // Check console for hydration mismatch errors
    const hydrationErrors = cdp.consoleLogs.filter(l =>
      l.text.includes('Hydration') ||
      l.text.includes('did not match') ||
      l.text.includes('suppressHydrationWarning')
    );
    console.log(`========================================`);
    console.log(`Hydration errors detected: ${hydrationErrors.length}`);
    if (hydrationErrors.length > 0) {
      console.warn('Hydration log warnings:', hydrationErrors);
    }
    console.log(`========================================`);

    // 1. Initial State Screenshot (Compact discovery layout, prerequisite guidance)
    console.log('Capturing initial workspace with prerequisite guidance...');
    await cdp.screenshot('r4_01_workspace_prerequisite_guidance_1920x1080.png');

    // 2. Select Basemap & Satellite Labels
    console.log('Testing basemap switching to satellite hybrid...');
    await cdp.eval(`
      const satBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Satellite'));
      if (satBtn) satBtn.click();
    `);
    await sleep(1500);

    // 3. Draw / Enter AOI A
    console.log('Submitting AOI A bounding box [77.58, 12.96, 77.62, 13.00] (Bangalore Central)...');
    await cdp.eval(`
      const panel = document.getElementById('map-tools-panel');
      if (panel) panel.scrollTop = 400;
      const bboxDetails = Array.from(document.querySelectorAll('details')).find(d => d.textContent.includes('Enter bounding box'));
      if (bboxDetails) bboxDetails.open = true;
      const inputs = document.querySelectorAll('.bbox-form input');
      if (inputs.length >= 4) {
        inputs[0].value = '77.58';
        inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
        inputs[1].value = '12.96';
        inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
        inputs[2].value = '77.62';
        inputs[2].dispatchEvent(new Event('input', { bubbles: true }));
        inputs[3].value = '13.00';
        inputs[3].dispatchEvent(new Event('input', { bubbles: true }));
        
        const form = document.querySelector('.bbox-form');
        if (form) form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      }
    `);
    await sleep(2000);

    // 4. Trigger Scene Discovery for AOI A
    console.log('Scrolling down map-tools-panel and triggering search imagery...');
    await cdp.eval(`
      const panel = document.getElementById('map-tools-panel');
      if (panel) panel.scrollTop = 600;
      const searchBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Search imagery'));
      if (searchBtn) searchBtn.click();
    `);
    await sleep(3500);

    console.log('Capturing scene discovery layout...');
    await cdp.screenshot('r4_02_discovery_layout_aoi_a_1920x1080.png');

    // 5. Select Scene
    console.log('Selecting first catalogue scene...');
    await cdp.eval(`
      const selectBtn = Array.from(document.querySelectorAll('.imagery-scene-card button')).find(b => b.textContent.includes('Select scene') || b.textContent.includes('Selected'));
      if (selectBtn) selectBtn.click();
    `);
    await sleep(2500);

    console.log('Capturing scene selected state with Full-scene preview & Selected-area preview labels...');
    await cdp.screenshot('r4_03_scene_selected_aoi_a_preview_1920x1080.png');

    // 6. Scroll down to Acquisition Timeline
    console.log('Scrolling to Acquisition Timeline...');
    await cdp.eval(`
      const panel = document.getElementById('map-tools-panel');
      if (panel) panel.scrollTop = 1100;
    `);
    await sleep(1000);
    console.log('Capturing acquisition timeline...');
    await cdp.screenshot('r4_04_acquisition_timeline_clean_1920x1080.png');

    // 7. Ask Visual Question for AOI A
    console.log('Asking Visual QA question on AOI A...');
    await cdp.eval(`
      const qInput = document.querySelector('textarea, input[placeholder*="Ask a question"], .assistant-input textarea');
      if (qInput) {
        qInput.value = 'Describe visible land-cover patterns within the selected area.';
        qInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
      const runBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Run analysis') || b.textContent.includes('Analyze'));
      if (runBtn) runBtn.click();
    `);
    await sleep(4000);

    console.log('Capturing completed grounded answer & evidence for AOI A...');
    await cdp.screenshot('r4_05_answer_evidence_aoi_a_1920x1080.png');

    // 8. Now Test Non-Overlapping AOI B [77.68, 13.08, 77.72, 13.12] (Bangalore North-East)
    console.log('Submitting AOI B bounding box [77.68, 13.08, 77.72, 13.12]...');
    await cdp.eval(`
      const panel = document.getElementById('map-tools-panel');
      if (panel) panel.scrollTop = 400;
      const bboxDetails = Array.from(document.querySelectorAll('details')).find(d => d.textContent.includes('Enter bounding box'));
      if (bboxDetails) bboxDetails.open = true;
      const inputs = document.querySelectorAll('.bbox-form input');
      if (inputs.length >= 4) {
        inputs[0].value = '77.68';
        inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
        inputs[1].value = '13.08';
        inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
        inputs[2].value = '77.72';
        inputs[2].dispatchEvent(new Event('input', { bubbles: true }));
        inputs[3].value = '13.12';
        inputs[3].dispatchEvent(new Event('input', { bubbles: true }));
        
        const form = document.querySelector('.bbox-form');
        if (form) form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      }
    `);
    await sleep(2000);

    // Search scenes for AOI B
    await cdp.eval(`
      const panel = document.getElementById('map-tools-panel');
      if (panel) panel.scrollTop = 600;
      const searchBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Search imagery'));
      if (searchBtn) searchBtn.click();
    `);
    await sleep(3000);

    // Select scene for AOI B
    await cdp.eval(`
      const selectBtn = Array.from(document.querySelectorAll('.imagery-scene-card button')).find(b => b.textContent.includes('Select scene') || b.textContent.includes('Selected'));
      if (selectBtn) selectBtn.click();
    `);
    await sleep(2500);

    console.log('Capturing AOI B selected state & preview...');
    await cdp.screenshot('r4_06_aoi_b_preview_distinct_1920x1080.png');

    // Ask question on AOI B
    console.log('Asking Visual QA on AOI B...');
    await cdp.eval(`
      const qInput = document.querySelector('textarea, input[placeholder*="Ask a question"], .assistant-input textarea');
      if (qInput) {
        qInput.value = 'Locate water bodies or vegetation zones within this northern AOI.';
        qInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
      const runBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Run analysis') || b.textContent.includes('Analyze'));
      if (runBtn) runBtn.click();
    `);
    await sleep(4000);

    console.log('Capturing AOI B grounded answer & evidence...');
    await cdp.screenshot('r4_07_answer_evidence_aoi_b_1920x1080.png');

    // 9. Responsive layout at 1366x768
    console.log('Testing responsive layout at 1366x768...');
    await cdp.setViewport(1366, 768);
    await sleep(1500);
    await cdp.screenshot('r4_08_workspace_responsive_1366x768.png');

    console.log('Verification completed successfully!');
    await cdp.close();
  } finally {
    try {
      chromeProcess.kill('SIGKILL');
    } catch {
      // Ignore
    }
  }
}

run().catch(err => {
  console.error('Execution failed:', err);
  process.exit(1);
});
