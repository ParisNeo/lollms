<script setup>
import { ref, computed, watch } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
  userId: { type: Number, required: true },
  username: { type: String, required: true },
});

const adminStore = useAdminStore();
const uiStore = useUiStore();

const quota = ref(null);
const isLoading = ref(true);
const isSaving = ref(false);

// Local editable copy, decoupled from the server snapshot so a user can edit
// several fields before committing a single PUT.
const form = ref({
  exempt: false,
  enabled: null,          // null = inherit global, true/false = per-user override
  input_max: null,        // null = inherit, 0 = unlimited
  output_max: null,
  period: null,           // null = inherit, else 'daily' | 'weekly' | 'monthly'
});

const PERIODS = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
];

function hydrate(src) {
  if (!src) return;
  form.value = {
    exempt: Boolean(src.exempt),
    enabled: src.enabled === null || src.enabled === undefined ? null : Boolean(src.enabled),
    input_max: src.input_max === null || src.input_max === undefined ? null : Number(src.input_max),
    output_max: src.output_max === null || src.output_max === undefined ? null : Number(src.output_max),
    period: src.period || null,
  };
}

async function load() {
  isLoading.value = true;
  try {
    const data = await adminStore.fetchUserTokenQuota(props.userId);
    quota.value = data;
    hydrate(data);
  } catch (e) {
    uiStore.addNotification('Failed to load token quota for this user.', 'error');
    quota.value = null;
  } finally {
    isLoading.value = false;
  }
}

async function save() {
  isSaving.value = true;
  try {
    // Send ``null`` explicitly so cleared fields fall back to global defaults,
    // and ``0`` for "unlimited". The backend distinguishes the two.
    const payload = {
      exempt: form.value.exempt,
      enabled: form.value.enabled,
      input_max: normalizeMax(form.value.input_max),
      output_max: normalizeMax(form.value.output_max),
      period: form.value.period || null,
    };
    const updated = await adminStore.updateUserTokenQuota(props.userId, payload);
    quota.value = updated;
    hydrate(updated);
    uiStore.addNotification('Token quota updated.', 'success');
  } catch (e) {
    const detail = e?.response?.data?.detail || 'Failed to update token quota.';
    uiStore.addNotification(detail, 'error');
  } finally {
    isSaving.value = false;
  }
}

function normalizeMax(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

// ── Derived display values ────────────────────────────────────────────────
const usage = computed(() => quota.value?.usage || null);

function pct(used, max) {
  if (!max || max <= 0) return 0;
  return Math.min(100, Math.round((Number(used || 0) / Number(max)) * 100));
}

const inputPct = computed(() => pct(usage.value?.input_used, usage.value?.input_max));
const outputPct = computed(() => pct(usage.value?.output_used, usage.value?.output_max));
const inputExhausted = computed(() => Number(usage.value?.input_max) > 0 && Number(usage.value?.input_used) >= Number(usage.value?.input_max));
const outputExhausted = computed(() => Number(usage.value?.output_max) > 0 && Number(usage.value?.output_used) >= Number(usage.value?.output_max));

const resetLabel = computed(() => {
  const r = quota.value?.reset_at || usage.value?.period_end;
  if (!r) return '—';
  try {
    return new Date(r).toLocaleString();
  } catch {
    return String(r);
  }
});

function formatInt(n) {
  return (Number(n) || 0).toLocaleString();
}

watch(() => props.userId, () => load(), { immediate: true });
</script>

<template>
  <div class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
    <div class="flex items-center justify-between mb-3">
      <h4 class="text-sm font-black tracking-tight flex items-center gap-2" style="color: var(--text-main);">
        Token quota
        <span v-if="quota?.exempt" class="text-[9px] font-black uppercase px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">Exempt</span>
        <span v-else-if="quota?.enforced" class="text-[9px] font-black uppercase px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">Enforced</span>
      </h4>
      <span class="text-[10px] font-mono" style="color: var(--text-dim);">
        Resets: {{ resetLabel }}
      </span>
    </div>

    <div v-if="isLoading" class="flex justify-center py-6">
      <IconAnimateSpin class="w-6 h-6 text-blue-500" />
    </div>

    <div v-else class="space-y-4">
      <!-- Live usage bars for the current period -->
      <div v-if="usage" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <div class="flex justify-between text-[10px] font-bold mb-1" style="color: var(--text-dim);">
            <span>Input (prompt)</span>
            <span class="font-mono">
              {{ formatInt(usage.input_used) }}<template v-if="Number(usage.input_max) > 0"> / {{ formatInt(usage.input_max) }}</template><template v-else> · ∞</template>
            </span>
          </div>
          <div class="h-2 rounded-full overflow-hidden" style="background-color: var(--bg-input, rgba(0,0,0,0.08));">
            <div class="h-full transition-all" :class="inputExhausted ? 'bg-rose-500' : 'bg-sky-500'" :style="{ width: Number(usage.input_max) > 0 ? inputPct + '%' : '0%' }"></div>
          </div>
        </div>
        <div>
          <div class="flex justify-between text-[10px] font-bold mb-1" style="color: var(--text-dim);">
            <span>Output (completion)</span>
            <span class="font-mono">
              {{ formatInt(usage.output_used) }}<template v-if="Number(usage.output_max) > 0"> / {{ formatInt(usage.output_max) }}</template><template v-else> · ∞</template>
            </span>
          </div>
          <div class="h-2 rounded-full overflow-hidden" style="background-color: var(--bg-input, rgba(0,0,0,0.08));">
            <div class="h-full transition-all" :class="outputExhausted ? 'bg-rose-500' : 'bg-rose-400'" :style="{ width: Number(usage.output_max) > 0 ? outputPct + '%' : '0%' }"></div>
          </div>
        </div>
      </div>

      <!-- Editing controls -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <label class="flex items-center gap-2 cursor-pointer font-bold" style="color: var(--text-main);">
          <input type="checkbox" v-model="form.exempt" class="rounded text-emerald-600 focus:ring-emerald-500 w-4 h-4">
          Exempt from quota
        </label>

        <div class="flex items-center gap-2">
          <span class="font-bold" style="color: var(--text-dim);">Enforcement</span>
          <select v-model="form.enabled" class="form-select text-xs py-1 px-2 rounded" style="background-color: var(--bg-input); color: var(--text-main);">
            <option :value="null">Inherit global</option>
            <option :value="true">Force ON</option>
            <option :value="false">Force OFF</option>
          </select>
        </div>

        <div class="flex items-center gap-2">
          <span class="font-bold w-24" style="color: var(--text-dim);">Input max</span>
          <input
            type="number" min="0" v-model.number="form.input_max"
            placeholder="Inherit (blank) · 0 = ∞"
            class="form-input text-xs py-1 px-2 rounded w-full"
            style="background-color: var(--bg-input); color: var(--text-main);"
          >
        </div>

        <div class="flex items-center gap-2">
          <span class="font-bold w-24" style="color: var(--text-dim);">Output max</span>
          <input
            type="number" min="0" v-model.number="form.output_max"
            placeholder="Inherit (blank) · 0 = ∞"
            class="form-input text-xs py-1 px-2 rounded w-full"
            style="background-color: var(--bg-input); color: var(--text-main);"
          >
        </div>

        <div class="flex items-center gap-2">
          <span class="font-bold w-24" style="color: var(--text-dim);">Period</span>
          <select v-model="form.period" class="form-select text-xs py-1 px-2 rounded" style="background-color: var(--bg-input); color: var(--text-main);">
            <option :value="null">Inherit global</option>
            <option v-for="p in PERIODS" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
        </div>
      </div>

      <div class="flex items-center justify-between pt-1">
        <p class="text-[10px] italic" style="color: var(--text-dim);">
          Blank fields inherit the global default. 0 means unlimited. Admins are always exempt.
        </p>
        <button @click="save" class="btn btn-primary btn-sm" :disabled="isSaving">
          {{ isSaving ? 'Saving...' : 'Save quota' }}
        </button>
      </div>
    </div>
  </div>
</template>