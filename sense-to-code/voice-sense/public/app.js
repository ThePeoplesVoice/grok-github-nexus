const PCM_RATE = 24000;
const micChip = document.getElementById("mic-chip");
const linkChip = document.getElementById("link-chip");
const thinkChip = document.getElementById("think-chip");
const statusEl = document.getElementById("status");
const listenBtn = document.getElementById("listen");
const stopBtn = document.getElementById("stop");
const transcriptEl = document.getElementById("transcript");
const eventsEl = document.getElementById("events");
const mapsEl = document.getElementById("maps");
const textForm = document.getElementById("text-form");
const textInput = document.getElementById("text-input");

const world = {
  gravity: 9.8,
  bounciness: 0.34,
  friction: 0.62,
  objects: [],
  maps: [],
};

let config = null;
let ws = null;
let audioCtx = null;
let mediaStream = null;
let captureNode = null;
let player = null;
let running = false;
let earlyAudio = [];
let pendingToolOutputs = 0;
let continueAfterTurn = false;
let turnClosed = false;
let continueLock = false;
let userPartial = "";
let assistantPartial = "";
let assistantLine = null;

class PcmPlayer {
  constructor(ctx) {
    this.ctx = ctx;
    this.nextTime = 0;
    this.active = 0;
    this.waiters = [];
  }

  enqueueInt16(int16) {
    if (!int16.length) return;
    const f32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i += 1) {
      f32[i] = int16[i] / 32768;
    }
    const buffer = this.ctx.createBuffer(1, f32.length, PCM_RATE);
    buffer.getChannelData(0).set(f32);
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(this.ctx.destination);
    const start = Math.max(this.ctx.currentTime, this.nextTime);
    src.start(start);
    this.nextTime = start + buffer.duration;
    this.active += 1;
    src.onended = () => {
      this.active -= 1;
      if (this.active <= 0) this.flushWaiters();
    };
  }

  waitForPlaybackComplete() {
    if (this.active <= 0 && this.ctx.currentTime >= this.nextTime - 0.03) {
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      this.waiters.push(resolve);
    });
  }

  flushWaiters() {
    const waiters = this.waiters.splice(0);
    waiters.forEach((fn) => fn());
  }

  reset() {
    this.nextTime = 0;
    this.active = 0;
    this.flushWaiters();
  }
}

function setStatus(text) {
  statusEl.textContent = text;
}

function logEvent(type) {
  const line = document.createElement("p");
  line.className = "line event";
  line.textContent = type;
  eventsEl.appendChild(line);
  eventsEl.scrollTop = eventsEl.scrollHeight;
}

function appendTranscript(role, text, replaceLast = false) {
  if (!text) return;
  if (replaceLast && role === "assistant" && assistantLine) {
    assistantLine.textContent = text;
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
    return;
  }
  const line = document.createElement("p");
  line.className = `line ${role}`;
  line.textContent = text;
  transcriptEl.appendChild(line);
  if (role === "assistant") assistantLine = line;
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

function setMic(state, label) {
  micChip.dataset.state = state;
  micChip.textContent = label;
  micChip.className = `chip ${state === "live" ? "chip-live" : "chip-idle"}`;
}

function setLink(live, label) {
  linkChip.textContent = label;
  linkChip.className = `chip ${live ? "chip-live" : "chip-idle"}`;
}

function setThinking(on) {
  thinkChip.classList.toggle("hidden", !on);
}

function floatToPcm16Base64(float32) {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i += 1) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  const bytes = new Uint8Array(int16.buffer);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 1) {
    bin += String.fromCharCode(bytes[i]);
  }
  return btoa(bin);
}

function resample(float32, fromRate, toRate) {
  if (fromRate === toRate) return float32;
  const ratio = fromRate / toRate;
  const outLen = Math.max(1, Math.floor(float32.length / ratio));
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i += 1) {
    const idx = i * ratio;
    const lo = Math.floor(idx);
    const hi = Math.min(lo + 1, float32.length - 1);
    const frac = idx - lo;
    out[i] = float32[lo] * (1 - frac) + float32[hi] * frac;
  }
  return out;
}

function sendAudioChunk(float32, fromRate) {
  const resampled = resample(float32, fromRate, PCM_RATE);
  const audio = floatToPcm16Base64(resampled);
  const msg = { type: "input_audio_buffer.append", audio };
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  } else {
    earlyAudio.push(msg);
  }
}

async function startMic() {
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      channelCount: 1,
    },
  });
  if (!audioCtx) {
    audioCtx = new AudioContext({ sampleRate: PCM_RATE });
  }
  if (audioCtx.state === "suspended") await audioCtx.resume();
  await audioCtx.audioWorklet.addModule("/pcm-worklet.js");
  const source = audioCtx.createMediaStreamSource(mediaStream);
  captureNode = new AudioWorkletNode(audioCtx, "pcm-capture");
  captureNode.port.onmessage = (ev) => {
    if (!running) return;
    sendAudioChunk(ev.data, audioCtx.sampleRate);
  };
  source.connect(captureNode);
  setMic("live", "MIC");
}

function stopMic() {
  if (captureNode) {
    captureNode.port.onmessage = null;
    captureNode.disconnect();
    captureNode = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
  setMic("idle", "NO MIC");
}

async function mintToken() {
  const resp = await fetch("/session", { method: "POST" });
  const data = await resp.json();
  if (!resp.ok || !data.value) {
    throw new Error(data.error || `token mint failed (${resp.status})`);
  }
  return data.value;
}

function applyToolResult(result) {
  if (!result || !result.ok) return;
  if (result.tool === "spawn_shape") {
    const n = result.shape === "tower" ? 6 : result.count;
    const kind = result.shape === "tower" ? "box" : result.shape;
    for (let i = 0; i < n; i += 1) {
      world.objects.push({
        kind,
        x: 360 + (Math.random() - 0.5) * 180,
        y: 80 + i * 18,
        vx: (Math.random() - 0.5) * 40,
        vy: 0,
        r: kind === "sphere" ? 16 : 14,
      });
    }
  }
  if (result.tool === "set_physics_param") {
    world[result.name] = result.value;
    document.getElementById(`p-${result.name}`).textContent = String(result.value);
  }
  if (result.tool === "note_sensation_map") {
    world.maps.unshift(result);
    renderMaps();
  }
  document.getElementById("object-count").textContent = String(world.objects.length);
}

function renderMaps() {
  mapsEl.innerHTML = "";
  if (!world.maps.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "None yet. Spoken maps stay local. Dictionary stays in chat.";
    mapsEl.appendChild(li);
    return;
  }
  world.maps.slice(0, 8).forEach((m) => {
    const li = document.createElement("li");
    li.textContent = `${m.sensation} → ${m.maps_to} (${m.source})`;
    mapsEl.appendChild(li);
  });
}

async function handleFunctionCall(event) {
  let args = {};
  try {
    args = event.arguments ? JSON.parse(event.arguments) : {};
  } catch {
    args = {};
  }
  pendingToolOutputs += 1;
  continueAfterTurn = true;
  let result;
  try {
    const resp = await fetch("/tool", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: event.name, arguments: args }),
    });
    result = await resp.json();
  } catch (err) {
    result = { ok: false, error: String(err) };
  }
  applyToolResult(result);
  logEvent(`tool ${event.name}`);
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        type: "conversation.item.create",
        item: {
          type: "function_call_output",
          call_id: event.call_id,
          output: JSON.stringify(result),
        },
      }),
    );
  }
  pendingToolOutputs -= 1;
  await maybeContinueAfterTools();
}

async function maybeContinueAfterTools() {
  if (!continueAfterTurn || !turnClosed || pendingToolOutputs > 0 || continueLock) {
    return;
  }
  continueLock = true;
  continueAfterTurn = false;
  turnClosed = false;
  setThinking(true);
  setStatus("Waiting for playback, then response.create…");
  if (player) await player.waitForPlaybackComplete();
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "response.create" }));
  }
  setThinking(false);
  setStatus("Listening.");
  continueLock = false;
}

function handleServerEvent(event) {
  const type = event.type || "unknown";
  if (
    type !== "response.output_audio.delta" &&
    type !== "response.output_audio_transcript.delta" &&
    type !== "response.function_call_arguments.delta"
  ) {
    logEvent(type);
  }

  if (type === "session.updated") {
    setStatus("Session ready. Speak an intent.");
  }

  if (type === "input_audio_buffer.speech_started") {
    userPartial = "";
  }

  if (type === "conversation.item.input_audio_transcription.completed") {
    const text = event.transcript || event.item?.formatted?.transcript || "";
    if (text) appendTranscript("user", text);
  }

  if (type === "response.output_audio_transcript.delta") {
    assistantPartial += event.delta || "";
    appendTranscript("assistant", assistantPartial, Boolean(assistantPartial));
  }

  if (type === "response.output_audio_transcript.done") {
    if (event.transcript) appendTranscript("assistant", event.transcript, true);
    assistantPartial = "";
    assistantLine = null;
  }

  if (type === "response.output_audio.delta" && event.delta && player) {
    const raw = atob(event.delta);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
    player.enqueueInt16(new Int16Array(bytes.buffer));
  }

  if (type === "response.function_call_arguments.done") {
    handleFunctionCall(event);
  }

  if (type === "response.done") {
    turnClosed = true;
    maybeContinueAfterTools();
  }

  if (type === "error") {
    const msg = event.error?.message || JSON.stringify(event.error || event);
    setStatus(msg);
  }
}

async function connect() {
  if (!config) {
    const resp = await fetch("/config");
    config = await resp.json();
  }
  setStatus("Minting ephemeral token…");
  const token = await mintToken();
  if (!audioCtx) audioCtx = new AudioContext({ sampleRate: PCM_RATE });
  if (audioCtx.state === "suspended") await audioCtx.resume();
  player = new PcmPlayer(audioCtx);

  const url = config.realtime_url;
  ws = new WebSocket(url, [`xai-client-secret.${token}`]);
  ws.onopen = () => {
    setLink(true, "LIVE");
    ws.send(JSON.stringify(config.session_update));
    earlyAudio.forEach((msg) => ws.send(JSON.stringify(msg)));
    earlyAudio = [];
    setStatus("Connected. Configuring session…");
  };
  ws.onmessage = (ev) => {
    if (typeof ev.data !== "string") return;
    let event;
    try {
      event = JSON.parse(ev.data);
    } catch {
      return;
    }
    handleServerEvent(event);
  };
  ws.onclose = () => {
    setLink(false, "OFFLINE");
    if (running) setStatus("Socket closed.");
  };
  ws.onerror = () => {
    setStatus("WebSocket error.");
  };
}

async function start() {
  running = true;
  listenBtn.disabled = true;
  stopBtn.disabled = false;
  pendingToolOutputs = 0;
  continueAfterTurn = false;
  turnClosed = false;
  continueLock = false;
  earlyAudio = [];
  try {
    const micPromise = startMic();
    const sockPromise = connect();
    await Promise.all([micPromise, sockPromise]);
  } catch (err) {
    setStatus(String(err.message || err));
    await stop();
  }
}

async function stop() {
  running = false;
  continueAfterTurn = false;
  turnClosed = false;
  continueLock = false;
  pendingToolOutputs = 0;
  if (ws) {
    ws.close();
    ws = null;
  }
  stopMic();
  if (player) player.reset();
  setLink(false, "OFFLINE");
  setThinking(false);
  listenBtn.disabled = false;
  stopBtn.disabled = true;
}

textForm.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const text = textInput.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
  textInput.value = "";
  appendTranscript("user", text);
  ws.send(
    JSON.stringify({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "input_text", text }],
      },
    }),
  );
  ws.send(JSON.stringify({ type: "response.create" }));
});

listenBtn.addEventListener("click", start);
stopBtn.addEventListener("click", stop);

const canvas = document.getElementById("stage");
const ctx = canvas.getContext("2d");

function tick() {
  ctx.fillStyle = "#0e1118";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "#223";
  for (let x = 0; x < canvas.width; x += 32) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  ctx.fillStyle = "#1a1f2b";
  ctx.beginPath();
  ctx.ellipse(360, 400, 260, 48, 0, 0, Math.PI * 2);
  ctx.fill();

  const g = world.gravity;
  const bounce = world.bounciness;
  const friction = world.friction;
  const floor = 390;
  world.objects.forEach((obj) => {
    obj.vy += g * 0.12;
    obj.x += obj.vx * 0.04;
    obj.y += obj.vy * 0.04;
    if (obj.y + obj.r > floor) {
      obj.y = floor - obj.r;
      obj.vy *= -bounce;
      obj.vx *= 1 - friction * 0.15;
    }
    if (obj.x < 80 || obj.x > 640) obj.vx *= -1;
    ctx.fillStyle = obj.kind === "sphere" ? "#6ea8ff" : obj.kind === "cylinder" ? "#3dcc7a" : "#e6b84d";
    if (obj.kind === "sphere") {
      ctx.beginPath();
      ctx.arc(obj.x, obj.y, obj.r, 0, Math.PI * 2);
      ctx.fill();
    } else if (obj.kind === "cylinder") {
      ctx.fillRect(obj.x - obj.r, obj.y - obj.r * 1.4, obj.r * 2, obj.r * 2.4);
    } else {
      ctx.fillRect(obj.x - obj.r, obj.y - obj.r, obj.r * 2, obj.r * 2);
    }
  });
  requestAnimationFrame(tick);
}

async function boot() {
  try {
    const health = await fetch("/health").then((r) => r.json());
    const cfg = await fetch("/config").then((r) => r.json());
    config = cfg;
    setStatus(
      health.has_key
        ? `Ready · ${cfg.model}. Grant the mic and listen.`
        : "Server is missing the API key. Set it on the process, restart, then listen.",
    );
  } catch {
    setStatus("Could not reach the local Voice Sense server.");
  }
}

boot();
tick();
