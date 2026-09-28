// Local-only Chrome DevTools check used when the in-app browser bridge is unavailable.
// No credential, provider URL, or application state is persisted by this script.
import { writeFile } from "node:fs/promises";

const targets = await (await fetch("http://127.0.0.1:9222/json/list")).json();
const target = targets.find((item) => item.type === "page" && item.url.includes("/workspace"));
if (!target) throw new Error("Open /workspace in the local debug browser first.");
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});
let sequence = 0;
const pending = new Map();
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  const waiter = pending.get(message.id);
  if (!waiter) return;
  pending.delete(message.id);
  if (message.error) waiter.reject(new Error(message.error.message));
  else waiter.resolve(message.result);
});
function call(method, params = {}) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await call("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.exceptionDetails) throw new Error("Page evaluation failed.");
  return result.result?.value;
}

try {
  const [action, ...args] = process.argv.slice(2);
  if (action === "inspect") {
    const result = await evaluate(`JSON.stringify({
      text: document.body.innerText.slice(0, 3200),
      controls: [...document.querySelectorAll('button,input,textarea,select,a,summary')]
        .filter(e => e.getClientRects().length)
        .map(e => ({tag:e.tagName, text:(e.innerText || e.getAttribute('aria-label') || '').slice(0,90),
          id:e.id, placeholder:e.getAttribute('placeholder'), type:e.getAttribute('type')}))
        .slice(0,100),
      map: [...document.querySelectorAll('canvas')]
        .map(e => {const r=e.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}})
    })`);
    console.log(result);
  } else if (action === "click") {
    const selector = args[0];
    const result = await evaluate(`(() => {const matches=document.querySelectorAll(${JSON.stringify(selector)});
      if(matches.length !== 1) return 'count='+matches.length;
      matches[0].click(); return 'clicked';})()`);
    console.log(result);
  } else if (action === "clickText") {
    const expected = args[0];
    const result = await evaluate(`(() => {const matches=[...document.querySelectorAll('button,a,summary')]
      .filter(e => e.getClientRects().length && (e.innerText || e.getAttribute('aria-label') || '').trim()===${JSON.stringify(expected)});
      if(matches.length !== 1) return 'count='+matches.length;
      matches[0].click(); return 'clicked';})()`);
    console.log(result);
  } else if (action === "fill") {
    const [selector, value] = args;
    const result = await evaluate(`(() => {const matches=document.querySelectorAll(${JSON.stringify(selector)});
      if(matches.length !== 1) return 'count='+matches.length;
      const e=matches[0]; const setter=Object.getOwnPropertyDescriptor(
        e.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,'value').set;
      setter.call(e,${JSON.stringify(value)}); e.dispatchEvent(new Event('input',{bubbles:true}));
      return 'filled';})()`);
    console.log(result);
  } else if (action === "mouse") {
    const [x, y] = args.map(Number);
    await call("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
    await call("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
    console.log("clicked-map-point");
  } else if (action === "navigate") {
    await call("Page.navigate", { url: args[0] });
    console.log(`navigated=${args[0]}`);
  } else if (action === "viewport") {
    const [width, height] = args.map(Number);
    await call("Emulation.setDeviceMetricsOverride", {
      width, height, deviceScaleFactor: 1, mobile: false,
    });
    console.log(`viewport=${width}x${height}`);
  } else if (action === "screenshot") {
    const path = args[0];
    const response = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    await writeFile(path, Buffer.from(response.data, "base64"));
    console.log(`saved=${path}`);
  } else {
    throw new Error("Use inspect, click, clickText, fill, mouse, navigate, viewport, or screenshot.");
  }
} finally {
  socket.close();
}
