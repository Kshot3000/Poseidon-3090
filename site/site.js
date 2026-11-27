"use strict";

const byId = (id) => document.getElementById(id);
const wholeNumber = new Intl.NumberFormat("en-US");
const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

const gpuCount = byId("gpu-count");
const powerRate = byId("power-rate");
const rigCost = byId("rig-cost");

function updateRig() {
  const count = gpuCount.valueAsNumber;
  const dailyKwh = (count * 320 / 1000) * 24;
  const cost = dailyKwh * powerRate.valueAsNumber;
  const hasRate = powerRate.value !== "";
  const invalid = !powerRate.validity.valid || (hasRate && !Number.isFinite(cost));

  byId("gpu-count-output").value = count;
  byId("rig-hash").textContent = `≥${wholeNumber.format(count * 125)} TH/s`;
  byId("rig-power").textContent = `≤${wholeNumber.format(count * 320)} W`;
  powerRate.setAttribute("aria-invalid", String(invalid));
  if (invalid) {
    rigCost.textContent = "Enter a valid rate";
  } else {
    rigCost.textContent = hasRate ? dollars.format(cost) : "Enter a rate";
  }
}

gpuCount.addEventListener("input", updateRig);
powerRate.addEventListener("input", updateRig);
updateRig();

const consoleOutput = byId("console-output");
const consolePlay = byId("console-play");
const initialConsole = consoleOutput.innerHTML;
const demoSteps = [
  ["pool", "Example pool job received"],
  ["work", "Sample work queued on RTX 3090"],
  ["share", "Example share submitted"],
  ["pool", "Example share accepted"],
  ["demo", "Sequence complete"],
];
let consoleTimer;
let consoleStep = 0;
let consolePlaying = false;

function renderConsoleStep() {
  const [tag, event] = demoSteps[consoleStep];
  const line = document.createElement("p");
  const label = document.createElement("span");
  label.textContent = `[${tag}]`;
  line.append(label, ` ${event}`);
  consoleOutput.append(line);
  consoleStep += 1;
  if (consoleStep === demoSteps.length) {
    consolePlaying = false;
    syncConsole();
  }
}

function syncConsole() {
  clearInterval(consoleTimer);
  if (consolePlaying && !document.hidden) consoleTimer = setInterval(renderConsoleStep, 880);
  if (consolePlaying) {
    consolePlay.textContent = "Pause demo";
  } else if (consoleStep === demoSteps.length) {
    consolePlay.textContent = "Replay demo";
  } else {
    consolePlay.textContent = consoleStep === 0 ? "Play demo" : "Resume demo";
  }
}

consolePlay.addEventListener("click", () => {
  if (consoleStep === demoSteps.length) {
    consoleStep = 0;
    consoleOutput.innerHTML = initialConsole;
  }
  consolePlaying = !consolePlaying;
  syncConsole();
});
document.addEventListener("visibilitychange", syncConsole);

const walletInput = byId("cfg-wallet");
const poolInput = byId("cfg-pool");
const workerInput = byId("cfg-worker");
const presetInput = byId("cfg-preset");
const formatInput = byId("config-format");
const configOutput = byId("config-output");
const configErrors = byId("config-errors");
const configFeedback = byId("config-feedback");
const copyConfig = byId("copy-config");
const saveConfig = byId("save-config");
const profiles = {
  stock: null,
  bench: { core_lock_mhz: 1600, core_offset_mhz: 200, memory_lock_mhz: 810 },
  memory: { core_lock_mhz: 1600, core_offset_mhz: 200, memory_lock_mhz: 405 },
};

function isPoolEndpoint(value) {
  const parts = /^stratum\+(?:tcp|ssl):\/\/(?:[a-z0-9.-]+|\[[0-9a-f:]+\]):(\d{1,5})$/i.exec(value);
  if (!parts || Number(parts[1]) < 1 || Number(parts[1]) > 65535) return false;
  try {
    // Parse with a standard scheme so the URL parser validates the host and port.
    return Boolean(new URL(value.replace(/^stratum\+(?:tcp|ssl):/i, "http:")).hostname);
  } catch {
    return false;
  }
}

function checkField(field, test) {
  const value = field.value.trim();
  const matches = !value || test(value);
  field.setAttribute("aria-invalid", String(!matches));
  return matches;
}

function commandPreview(format, wallet, pool, worker, clocks) {
  const linux = format === "linux";
  const comment = linux ? "#" : "REM";
  const miner = linux ? "./poseidon-3090" : "poseidon-3090.exe";
  const args = [
    miner,
    `  --pool "${pool || "YOUR_POOL_ENDPOINT"}"`,
    `  --user "${wallet || "YOUR_PEARL_WALLET"}.${worker || "YOUR_WORKER"}"`,
  ];
  if (clocks) {
    args.push(`  --lock-cclock ${clocks.core_lock_mhz}`);
    args.push(`  --coff ${clocks.core_offset_mhz}`);
    args.push(`  --lock-mclock ${clocks.memory_lock_mhz}`);
  }
  const separator = " " + (linux ? "\\" : "^") + "\n";
  return [
    `${comment} Poseidon 3090 configuration preview`,
    `${comment} Miner unreleased. Command syntax may change.`,
    "",
    args.join(separator),
  ].join("\n");
}

function updateConfig() {
  const checks = [
    [walletInput, (value) => /^prl1[0-9a-z]+$/.test(value), "Use a lowercase Pearl address starting with prl1."],
    [poolInput, isPoolEndpoint, "Use a stratum+tcp or stratum+ssl endpoint with a valid port."],
    [workerInput, (value) => /^[a-z0-9_-]+$/i.test(value), "Use letters, numbers, underscores or hyphens for the worker."],
  ];
  const errors = checks.filter(([field, test]) => !checkField(field, test));
  copyConfig.disabled = saveConfig.disabled = errors.length > 0;
  configFeedback.textContent = "";
  configErrors.textContent = errors.map(([, , message]) => message).join(" ");
  if (errors.length) {
    configOutput.textContent = "Correct the highlighted fields to regenerate the preview.";
    return;
  }

  const wallet = walletInput.value.trim();
  const pool = poolInput.value.trim();
  const worker = workerInput.value.trim();
  const clocks = profiles[presetInput.value];
  if (formatInput.value === "json") {
    configOutput.textContent = JSON.stringify({
      preview: true,
      wallet: wallet || null,
      pool: pool || null,
      worker: worker || null,
      clocks,
    }, null, 2);
  } else {
    configOutput.textContent = commandPreview(formatInput.value, wallet, pool, worker, clocks);
  }
}

for (const input of [walletInput, poolInput, workerInput, presetInput, formatInput]) {
  input.addEventListener("input", updateConfig);
}
updateConfig();

async function copyText(text, feedback, element) {
  try {
    await navigator.clipboard.writeText(text);
    feedback.textContent = "Copied.";
  } catch {
    const selection = window.getSelection();
    if (selection) {
      const range = document.createRange();
      range.selectNodeContents(element);
      selection.removeAllRanges();
      selection.addRange(range);
    }
    feedback.textContent = "Clipboard unavailable. Copy the selected text manually.";
  }
}

byId("copyFeeBtn").addEventListener("click", () => {
  const address = byId("feeAddr");
  copyText(address.textContent.trim(), byId("fee-feedback"), address);
});

copyConfig.addEventListener("click", () => {
  copyText(configOutput.textContent, configFeedback, configOutput);
});

saveConfig.addEventListener("click", () => {
  const filenames = {
    json: "poseidon-config-preview.json",
    linux: "poseidon-linux-preview.txt",
    windows: "poseidon-windows-preview.txt",
  };
  const url = URL.createObjectURL(new Blob([configOutput.textContent + "\n"], { type: "text/plain;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filenames[formatInput.value];
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  configFeedback.textContent = "Preview export requested.";
});

const hero = byId("top");
const canvas = byId("gold");
const motionToggle = byId("motion-toggle");
const context = canvas.getContext("2d");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
let heroVisible = false;
let motionPaused = false;
let frame = null;
let previousTime;
let flakes = [];

function resizeScene() {
  const { width, height } = hero.getBoundingClientRect();
  const scale = Math.min(devicePixelRatio || 1, 1.5);
  canvas.width = Math.ceil(width * scale);
  canvas.height = Math.ceil(height * scale);
  const count = Math.min(52, Math.floor(width / 22));
  flakes = Array.from({ length: count }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    size: (0.7 + Math.random() * 1.3) * scale,
    speed: (4 + Math.random() * 9) * scale,
    phase: Math.random() * Math.PI * 2,
  }));
}

function animateScene(time) {
  const step = Math.min((time - (previousTime ?? time)) / 1000, 0.05);
  previousTime = time;
  context.clearRect(0, 0, canvas.width, canvas.height);
  for (const flake of flakes) {
    flake.phase += step * 0.65;
    flake.x += step * 5;
    flake.y += Math.sin(flake.phase) * step * flake.speed;
    if (flake.x > canvas.width + 2) flake.x = -2;
    context.globalAlpha = 0.21 + 0.35 * (0.5 + 0.5 * Math.sin(flake.phase));
    context.fillStyle = "#f1c587";
    context.beginPath();
    context.ellipse(flake.x, flake.y, flake.size, flake.size / 2, flake.phase, 0, Math.PI * 2);
    context.fill();
  }
  frame = requestAnimationFrame(animateScene);
}

function syncMotion() {
  const active = heroVisible && !motionPaused && !reduceMotion.matches && !document.hidden;
  document.body.classList.toggle("motion-active", active);
  motionToggle.hidden = reduceMotion.matches;
  motionToggle.textContent = motionPaused ? "Play motion" : "Pause motion";
  if (active && context && frame === null) {
    previousTime = undefined;
    frame = requestAnimationFrame(animateScene);
  } else if (!active && frame !== null) {
    cancelAnimationFrame(frame);
    frame = null;
  }
  if (reduceMotion.matches && context) context.clearRect(0, 0, canvas.width, canvas.height);
}

motionToggle.addEventListener("click", () => {
  motionPaused = !motionPaused;
  syncMotion();
});
reduceMotion.addEventListener("change", syncMotion);
document.addEventListener("visibilitychange", syncMotion);
new ResizeObserver(resizeScene).observe(hero);
new IntersectionObserver(([entry]) => {
  heroVisible = entry.isIntersecting;
  syncMotion();
}).observe(hero);
