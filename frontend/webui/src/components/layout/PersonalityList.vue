
<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import apiClient from '../../services/api';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';

const route = useRoute();
const router = useRouter();
const dataStore = useDataStore();
const uiStore = useUiStore();

const catalog = ref({ personal: [], global: [], shared: [] });
const searchQuery = ref('');
const scopeFilter = ref('all');
const isLoading = ref(false);
const uploadInput = ref(null);

const sections = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  const labels = { personal: 'My Personalities', global: 'Global', shared: 'Shared with Me' };
  const scopes = scopeFilter.value === 'all' ? ['personal', 'global', 'shared'] : [scopeFilter.value];
  return scopes.map((scope) => ({
    scope,
    label: labels[scope],
    items: catalog.value[scope].filter((item) => !query || [
      item.name, item.handbag_name, item.description, item.author, item.category,
    ].some((value) => String(value || '').toLowerCase().includes(query))),
  })).filter((section) => section.items.length);
});

const resultCount = computed(() => sections.value.reduce((count, section) => count + section.items.length, 0));

function itemKey(item) {
  return `${item.scope}:${item.owner_id ?? ''}:${item.handbag_name}`;
}

function isSelected(item) {
  return route.path === '/personality-studio' &&
    route.query.scope === item.scope &&
    route.query.handbag === item.handbag_name &&
    String(route.query.owner ?? '') === String(item.owner_id ?? '');
}

function isActive(item) {
  const preference = dataStore.activePersonalityPreference;
  return preference?.scope === item.scope &&
    preference?.handbag_name === item.handbag_name &&
    (item.scope !== 'shared' || String(preference.owner_id ?? '') === String(item.owner_id ?? ''));
}

function initials(name) {
  return String(name || '?').trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || '?';
}

function selectPersonality(item) {
  const query = { scope: item.scope, handbag: item.handbag_name };
  if (item.scope === 'shared' && item.owner_id != null) query.owner = String(item.owner_id);
  router.push({ name: 'PersonalityStudio', query });
}

function createPersonality() {
  router.push({ name: 'PersonalityStudio', query: { create: '1' } });
}

async function fetchCatalog() {
  isLoading.value = true;
  try {
    const response = await apiClient.get('/api/personalities/catalog');
    const data = response.data || {};
    catalog.value = {
      personal: Array.isArray(data.personal) ? data.personal : [],
      global: Array.isArray(data.global) ? data.global : [],
      shared: Array.isArray(data.shared) ? data.shared : [],
    };
  } catch (error) {
    uiStore.addNotification(error?.response?.data?.detail || 'Failed to load personalities.', 'error');
  } finally {
    isLoading.value = false;
  }
}

async function importPersonality(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.zip')) {
    uiStore.addNotification('Only ZIP personality archives are supported.', 'warning');
    return;
  }
  const form = new FormData();
  form.append('file', file);
  try {
    const response = await apiClient.post('/api/personalities/studio/upload', form, {
      params: { scope: 'personal' },
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    await fetchCatalog();
    const imported = catalog.value.personal.find((item) => item.handbag_name === response.data?.handbag_name);
    if (imported) selectPersonality(imported);
    uiStore.addNotification('Personality imported successfully.', 'success');
  } catch (error) {
    uiStore.addNotification(error?.response?.data?.detail || 'Personality import failed.', 'error');
  }
}

function handleCatalogChanged() {
  fetchCatalog();
}

onMounted(() => {
  fetchCatalog();
  window.addEventListener('lollms:personalities-changed', handleCatalogChanged);
});

onUnmounted(() => {
  window.removeEventListener('lollms:personalities-changed', handleCatalogChanged);
});
</script>

<template>
  <div class="h-full flex flex-col min-h-0 bg-bg-card">
    <div class="shrink-0 p-3 space-y-3 border-b border-border-main">
      <div class="flex items-center justify-between gap-2">
        <div>
          <h2 class="text-sm font-bold">Personalities</h2>
          <p class="text-[11px] text-text-dim">Choose a persona to customize</p>
        </div>
        <button class="btn btn-secondary btn-sm px-2" title="Refresh personalities" :disabled="isLoading" @click="fetchCatalog">⟳</button>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <button class="btn btn-primary btn-sm justify-center text-xs" @click="createPersonality">
          <IconPlus class="w-3.5 h-3.5 mr-1" /> New
        </button>
        <button class="btn btn-secondary btn-sm justify-center text-xs" @click="uploadInput?.click()">Import ZIP</button>
        <input ref="uploadInput" type="file" accept=".zip,application/zip" class="hidden" @change="importPersonality" />
      </div>
      <input v-model="searchQuery" type="search" class="input-field w-full text-sm" placeholder="Search personalities…" />
      <div class="flex gap-1 p-1 rounded-lg bg-bg-app">
        <button
          v-for="filter in [{ value: 'all', label: 'All' }, { value: 'personal', label: 'Mine' }, { value: 'global', label: 'Global' }, { value: 'shared', label: 'Shared' }]"
          :key="filter.value"
          class="flex-1 px-1.5 py-1 rounded-md text-[10px] font-semibold transition-colors"
          :class="scopeFilter === filter.value ? 'bg-bg-card text-blue-600 shadow-sm' : 'text-text-dim hover:text-text-main'"
          @click="scopeFilter = filter.value"
        >{{ filter.label }}</button>
      </div>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-2">
      <div v-if="isLoading" class="p-6 text-center text-xs text-text-dim">
        <IconAnimateSpin class="w-5 h-5 animate-spin mx-auto mb-2" /> Loading personalities…
      </div>
      <div v-else-if="!resultCount" class="p-6 text-center">
        <IconUserCircle class="w-9 h-9 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
        <p class="text-sm font-medium">No personalities found</p>
        <p class="text-xs text-text-dim mt-1">Clear the filters or create a new one.</p>
      </div>
      <div v-else class="space-y-4">
        <section v-for="section in sections" :key="section.scope">
          <h3 class="px-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-text-dim">
            {{ section.label }} <span class="font-normal">({{ section.items.length }})</span>
          </h3>
          <div class="space-y-1">
            <button
              v-for="item in section.items"
              :key="itemKey(item)"
              class="w-full flex items-center gap-2.5 p-2 rounded-xl text-left border transition-colors"
              :class="isSelected(item) ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-900' : 'border-transparent hover:bg-bg-app'"
              @click="selectPersonality(item)"
            >
              <div class="w-9 h-9 rounded-lg overflow-hidden shrink-0 bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-500">
                <img v-if="item.icon" :src="item.icon" class="w-full h-full object-cover" :alt="`${item.name} icon`" />
                <span v-else>{{ initials(item.name) }}</span>
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-1.5">
                  <span class="truncate text-sm font-semibold">{{ item.name }}</span>
                  <IconCheckCircle v-if="isActive(item)" class="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                </div>
                <p class="text-[11px] text-text-dim truncate">{{ item.description || item.category || item.handbag_name }}</p>
              </div>
            </button>
          </div>
        </section>
      </div>
    </div>
    <div class="shrink-0 px-3 py-2 border-t border-border-main text-[10px] text-text-dim">{{ resultCount }} shown</div>
  </div>
</template>
