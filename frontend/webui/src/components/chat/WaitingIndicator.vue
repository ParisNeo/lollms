
<script setup>
/**
 * WaitingIndicator
 * -----------------
 * Displayed while an assistant message is streaming but no answer text has
 * painted yet — the pre-first-token ("TTFT") gap that otherwise feels broken.
 *
 * Design:
 *   • A thin progress bar that grows with a sqrt curve (fast early feedback,
 *     then slows toward `maxPercent` so it never falsely looks complete).
 *   • Colour interpolates continuously GREEN → AMBER → RED over `redAfter`
 *     seconds so the user perceives the wait getting "heavier" over time.
 *   • A rotating set of short reassuring messages (or the parent-supplied
 *     `detail`) so the wait feels alive.
 *   • Updates at ~10 Hz (100 ms) with CSS transitions to keep the fill silky.
 *
 * All timers are cleaned up on unmount; the component is purely presentational.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  // Optional explicit status line (from the generation stream). Overrides the
  // rotating waiting messages while non-empty.
  detail: { type: String, default: '' },
  // Seconds until the bar reaches amber, then red. Lower = quicker escalation.
  amberAfter: { type: Number, default: 12 },
  redAfter: { type: Number, default: 30 },
  // Hard cap for the visual fill (%) — never a full bar (it isn't real progress).
  maxPercent: { type: Number, default: 92 },
});

// Playful, reassuring prefill messages. While the model is doing its
// prompt-processing ("prefill") pass — before the first token arrives — we
// rotate through fun, concrete imagery so the wait feels alive and human
// instead of a dead spinner. Rotates every ~3.2 s (see currentMessage).
const WAITING_MESSAGES = [
  'Summoning the demon… 😈🔥',
  'Warming up the engine… 🏎️💨',
  'Linking the data gnomes… 🧙‍♂️',
  'Priming the mainframe… 🖥️⚡',
  'Stealing jokes from a hedgehog… 🦔',
  'Consulting the forbidden camera… 📷',
  'Waking the dragon… 🐉',
  'Bribing the tokens… 💰🪙',
  'Untangling the neural spaghetti… 🍝',
  'Rerouting power to the subwoofer… 🔊🛡️',
  'Asking the intern politely… 🙙',
  'Lubricating the gears… ⚙️🛢️',
  'Spinning up the hamster wheels… 🐹🌀',
  'Charging the flux capacitor… ⚡🚗',
  'Consulting the ancient scrolls… 📜',
  'Overclocking the toaster… 🍞🔌',
  'Whispering to the raccoons… 🦝',
  'Sharpening the attention blades… 🗡️',
  'Hailing the satellite… 🛰️📡',
  'Polishing the crystal ball… 🔮✨',
  'Negotiating with the swarm… 🐝',
  'Calibrating the vibes… 🎛️',
  'Feeding the clean-room gremlin… 👾',
  'Tuning the quantum antenna… 📡',
];



const startedAt = ref(0);
const nowMs = ref(0);
let tickTimer = null;

const elapsed = computed(() => Math.max(0, (nowMs.value - startedAt.value) / 1000));
const elapsedSec = computed(() => Math.floor(elapsed.value));

const progress = computed(() => {
  const red = Math.max(props.redAfter, 1);
  const frac = Math.min(1, Math.sqrt(elapsed.value / red));
  return Math.max(2, frac * props.maxPercent);
});

function lerp(a, b, k) { return a + (b - a) * k; }

// Continuous green (34,197,94) → amber (245,158,11) → red (239,68,68).
const fillColor = computed(() => {
  const red = Math.max(props.redAfter, 1);
  const t = Math.min(1, elapsed.value / red);
  let r, g, b;
  if (t < 0.5) {
    const k = t / 0.5;
    r = lerp(34, 245, k); g = lerp(197, 158, k); b = lerp(94, 11, k);
  } else {
    const k = (t - 0.5) / 0.5;
    r = lerp(245, 239, k); g = lerp(158, 68, k); b = lerp(11, 68, k);
  }
  return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
});

const currentMessage = computed(() => {
  // When the parent supplies an explicit, meaningful activity (e.g. "Executing
  // tool: x", "Patching an artefact"), prefer it. Otherwise rotate the playful
  // prefill messages so the wait never looks frozen.
  const d = (props.detail || '').trim();
  if (d) return d;
  const idx = Math.floor(elapsedSec.value / 3.2) % WAITING_MESSAGES.length;
  return WAITING_MESSAGES[idx];
});


function startTimers() {
  stopTimers();
  startedAt.value = Date.now();
  nowMs.value = startedAt.value;
  tickTimer = setInterval(() => { nowMs.value = Date.now(); }, 100);
}

function stopTimers() {
  if (tickTimer) { clearInterval(tickTimer); tickTimer = null; }
}

onMounted(startTimers);
onUnmounted(stopTimers);
</script>

<template>
  <div class="waiting-indicator" role="status" aria-live="polite">
    <div class="waiting-track">
      <div
        class="waiting-fill"
        :style="{ width: progress + '%', backgroundColor: fillColor }"
      ></div>
    </div>

    <div class="waiting-row">
      <span
        class="waiting-spinner"
        :style="{ borderTopColor: fillColor }"
        aria-hidden="true"
      ></span>
      <span class="waiting-message">{{ currentMessage }}</span>
      <span class="waiting-elapsed">{{ elapsedSec }}s</span>
    </div>
  </div>
</template>

<style scoped>
.waiting-indicator {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0 2px;
  max-width: 640px;
  width: 100%;
}

.waiting-track {
  width: 100%;
  height: 6px;
  border-radius: 9999px;
  background: var(--brand-bg-elevated, #eef2f7);
  overflow: hidden;
}

.waiting-fill {
  height: 100%;
  border-radius: 9999px;
  /* 100 ms tick + short transitions = continuous, non-jittery fill. */
  transition: width 0.12s linear, background-color 0.2s linear;
}

.waiting-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
  color: var(--brand-text-dim, #64748b);
}

.waiting-spinner {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid transparent;
  animation: waiting-spin 0.8s linear infinite;
  flex-shrink: 0;
}

.waiting-message {
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.waiting-elapsed {
  margin-left: auto;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 0.7rem;
  opacity: 0.65;
  flex-shrink: 0;
}

@keyframes waiting-spin {
  to { transform: rotate(360deg); }
}
</style>
