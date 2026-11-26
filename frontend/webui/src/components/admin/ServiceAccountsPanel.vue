
<script setup>
import { ref, onMounted, computed } from 'vue';
import apiClient from '@/services/api';
import { useUiStore } from '@/stores/ui';
import IconPlus from '@/assets/icons/IconPlus.vue';
import IconAnimateSpin from '@/assets/icons/IconAnimateSpin.vue';
import IconKey from '@/assets/icons/IconKey.vue';
import IconTrash from '@/assets/icons/IconTrash.vue';

const uiStore = useUiStore();
const accounts = ref([]);
const isLoading = ref(false);
const isCreating = ref(false);
const issuedKey = ref(null);

const newAccount = ref({
  username: '',
  account_type: 'mesh',
  display_name: '',
  description: '',
  quota_input_tokens: null,
  quota_output_tokens: null,
  quota_period: 'monthly',
});

const ACCOUNT_TYPES = [
  { value: 'mesh', label: 'Mesh Node', hint: 'A peer LoLLMs instance (corporate consumption bucket).' },
  { value: 'agent', label: 'Agent', hint: 'An AI/bot identity with no human profile.' },
];

const canCreate = computed(() => newAccount.value.username.trim().length >= 3);

function describeError(e) {
  const d = e?.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (d) return JSON.stringify(d);
  return e?.message || 'Request failed.';
}

async function loadAccounts() {
  isLoading.value = true;
  try {
    const res = await apiClient.get('/api/admin/accounts');
    accounts.value = Array.isArray(res.data) ? res.data : [];
  } catch (e) {
    uiStore.addNotification(describeError(e), 'error');
  } finally {
    isLoading.value = false;
  }
}

async function createAccount() {
  if (!canCreate.value) return;
  isCreating.value = true;
  issuedKey.value = null;
  try {
    const payload = { ...newAccount.value };
    if (payload.quota_input_tokens === '' || payload.quota_input_tokens === null) delete payload.quota_input_tokens;
    if (payload.quota_output_tokens === '' || payload.quota_output_tokens === null) delete payload.quota_output_tokens;
    const res = await apiClient.post('/api/admin/accounts', payload);
    issuedKey.value = res.data?.api_key || null;
    uiStore.addNotification(`Service account "${payload.username}" created.`, 'success');
    newAccount.value = {
      username: '', account_type: 'mesh', display_name: '', description: '',
      quota_input_tokens: null, quota_output_tokens: null, quota_period: 'monthly',
    };
    await loadAccounts();
  } catch (e) {
    uiStore.addNotification(describeError(e), 'error');
  } finally {
    isCreating.value = false;
  }
}

async function issueKey(account) {
  try {
    const res = await apiClient.post(`/api/admin/accounts/${account.id}/api-keys`);
    issuedKey.value = res.data || null;
    uiStore.addNotification('New API key issued.', 'success');
  } catch (e) {
    uiStore.addNotification(describeError(e), 'error');
  }
}

async function removeAccount(account) {
  if (!window.confirm(`Delete service account "${account.username}" and revoke its keys?`)) return;
  try {
    await apiClient.delete(`/api/admin/accounts/${account.id}`);
    uiStore.addNotification('Account deleted.', 'success');
    await loadAccounts();
  } catch (e) {
    uiStore.addNotification(describeError(e), 'error');
  }
}

function copyKey() {
  if (issuedKey.value?.key) {
    navigator.clipboard?.writeText(issuedKey.value.key);
    uiStore.addNotification('API key copied to clipboard.', 'success');
  }
}

onMounted(loadAccounts);
</script>

<template>
  <div class="space-y-6">
    <!-- Issued key banner (shown once) -->
    <div
      v-if="issuedKey"
      class="p-4 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-800"
    >
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p class="text-xs font-black uppercase tracking-widest text-emerald-700 dark:text-emerald-300">
            API key issued — copy it now (shown once)
          </p>
          <code class="block mt-1 text-sm break-all font-mono text-gray-900 dark:text-white">{{ issuedKey.key }}</code>
        </div>
        <div class="flex gap-2">
          <button class="btn btn-secondary btn-sm" @click="copyKey">Copy</button>
          <button class="btn btn-secondary btn-sm" @click="issuedKey = null">Dismiss</button>
        </div>
      </div>
    </div>

    <!-- Create form -->
    <div class="p-6 bg-white dark:bg-gray-800 rounded-3xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm space-y-4">
      <div class="border-b dark:border-gray-700/80 pb-3">
        <h3 class="text-base font-black text-gray-900 dark:text-white tracking-tight flex items-center gap-2">
          <span>🔗</span><span>Create Mesh / Agent Account</span>
        </h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          Service principals use the API only (no WebUI login) and are quota-metered like any user.
        </p>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Username</label>
          <input v-model="newAccount.username" type="text" placeholder="node-paris" class="input-field w-full text-sm" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Type</label>
          <select v-model="newAccount.account_type" class="input-field w-full text-sm">
            <option v-for="t in ACCOUNT_TYPES" :key="t.value" :value="t.value">{{ t.label }} — {{ t.hint }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Display name</label>
          <input v-model="newAccount.display_name" type="text" placeholder="Paris Node" class="input-field w-full text-sm" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Quota period</label>
          <select v-model="newAccount.quota_period" class="input-field w-full text-sm">
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Input token quota (0 = unlimited)</label>
          <input v-model.number="newAccount.quota_input_tokens" type="number" min="0" placeholder="inherit" class="input-field w-full text-sm" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Output token quota (0 = unlimited)</label>
          <input v-model.number="newAccount.quota_output_tokens" type="number" min="0" placeholder="inherit" class="input-field w-full text-sm" />
        </div>
      </div>
      <div>
        <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Description</label>
        <input v-model="newAccount.description" type="text" placeholder="Optional notes" class="input-field w-full text-sm" />
      </div>

      <button class="btn btn-primary text-sm" :disabled="!canCreate || isCreating" @click="createAccount">
        <IconAnimateSpin v-if="isCreating" class="w-4 h-4 mr-1.5 animate-spin" />
        <IconPlus v-else class="w-4 h-4 mr-1.5" />
        {{ isCreating ? 'Creating…' : 'Create Account' }}
      </button>
    </div>

    <!-- List -->
    <div class="p-6 bg-white dark:bg-gray-800 rounded-3xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm space-y-3">
      <div class="flex items-center justify-between border-b dark:border-gray-700/80 pb-3">
        <h3 class="text-base font-black text-gray-900 dark:text-white tracking-tight">Service Accounts</h3>
        <button class="btn btn-secondary btn-sm" @click="loadAccounts" :disabled="isLoading">Refresh</button>
      </div>

      <div v-if="isLoading" class="flex justify-center py-10">
        <IconAnimateSpin class="w-6 h-6 animate-spin text-blue-500" />
      </div>
      <div v-else-if="!accounts.length" class="text-center py-10 text-sm italic text-gray-400 dark:text-gray-500">
        No mesh or agent accounts yet.
      </div>
      <div v-else class="space-y-1.5">
        <div
          v-for="acc in accounts"
          :key="acc.id"
          class="flex items-center gap-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-700/40 border border-gray-100 dark:border-gray-700/60"
        >
          <span
            class="text-[10px] font-black uppercase px-2 py-0.5 rounded-full border"
            :class="acc.account_type === 'mesh'
              ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800'
              : 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800'"
          >{{ acc.account_type }}</span>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-bold text-gray-900 dark:text-white truncate">@{{ acc.username }}</div>
            <div class="text-[11px] text-gray-500 dark:text-gray-400 truncate">
              {{ acc.display_name || '—' }}<span v-if="acc.description"> · {{ acc.description }}</span>
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" title="Issue new API key" @click="issueKey(acc)">
            <IconKey class="w-3.5 h-3.5" />
          </button>
          <button class="btn btn-secondary btn-sm !text-red-600" title="Delete account" @click="removeAccount(acc)">
            <IconTrash class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
