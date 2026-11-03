<script setup>
import { ref, onMounted } from 'vue';
import apiClient from '@/services/api';
import { useUiStore } from '@/stores/ui';
import { useAuthStore } from '@/stores/auth';
import PersonalityEditorModal from '@/components/modals/PersonalityEditorModal.vue';
import SharePersonalityModal from '@/components/modals/SharePersonalityModal.vue';
import IconCheckCircle from '@/assets/icons/IconCheckCircle.vue';
import IconUserCircle from '@/assets/icons/IconUserCircle.vue';
import IconUserGroup from '@/assets/icons/IconUserGroup.vue';
import IconGlobeAlt from '@/assets/icons/IconGlobeAlt.vue';
import IconCode from '@/assets/icons/IconCode.vue';
import IconDataZone from '@/assets/icons/IconDataZone.vue';
import IconDocumentText from '@/assets/icons/IconDocumentText.vue';
import IconMagic from '@/assets/icons/IconMagic.vue';
import IconBookOpen from '@/assets/icons/IconBookOpen.vue';
import IconPencil from '@/assets/icons/IconPencil.vue';
import IconShare from '@/assets/icons/IconShare.vue';
import IconTrash from '@/assets/icons/IconTrash.vue';

const uiStore = useUiStore();
const authStore = useAuthStore();

const catalog = ref({ global: [], personal: [], shared: [] });
const activePreference = ref(null);
const isLoading = ref(true);
const loadError = ref(null);

const showEditor = ref(false);
const editorHandbag = ref(null);
const showShareModal = ref(false);
const shareHandbagName = ref(null);
const shareOwner = ref(null);
const receivedShares = ref([]);

const uploadInput = ref(null);

const canEdit = (item) =>
  item.scope === 'personal' ||
  (item.scope === 'global' && Boolean(authStore.user?.is_admin));

function describeError(e) {
  const detail = e?.response?.data?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (detail) return JSON.stringify(detail);
  if (e?.message) return e.message;
  return null;
}

/* ---------- Avatar helpers (catalog has no icon field) ---------- */
function initials(name) {
  const source = String(name || '?').trim();
  if (!source) return '?';
  const words = source.split(/\s+/).filter(Boolean);
  if (words.length === 0) return '?';
  const chars = words.slice(0, 2).map((w) => w[0]);
  return chars.join('').toUpperCase();
}

function hashColor(str) {
  const source = String(str || '');
  let hash = 0;
  for (let i = 0; i < source.length; i += 1) {
    // Deterministic hue from char codes; keep it simple and stable.
    hash = (hash * 31 + source.charCodeAt(i)) >>> 0;
  }
  return `hsl(${hash % 360}, 65%, 45%)`;
}

/* ------------------------------------------------------------- */

async function fetchCatalog() {
  isLoading.value = true;
  loadError.value = null;

  const [catRes, prefRes, sharesRes] = await Promise.allSettled([
    apiClient.get('/api/personalities/catalog'),
    apiClient.get('/api/personalities/preference'),
    apiClient.get('/api/personalities/share/received'),
  ]);

  if (catRes.status === 'fulfilled') {
    const raw = catRes.value?.data ?? {};
    catalog.value = {
      global: Array.isArray(raw.global) ? raw.global : [],
      personal: Array.isArray(raw.personal) ? raw.personal : [],
      shared: Array.isArray(raw.shared) ? raw.shared : [],
    };
  } else {
    loadError.value = describeError(catRes.reason) || 'Failed to load personalities catalog.';
    // eslint-disable-next-line no-console
    console.error('[PersonalitiesSettings] /catalog failed', catRes.reason);
  }

  activePreference.value = prefRes.status === 'fulfilled'
    ? (prefRes.value?.data ?? null)
    : null;

  const sharesPayload = sharesRes.status === 'fulfilled'
    ? sharesRes.value?.data
    : null;
  receivedShares.value = Array.isArray(sharesPayload)
    ? sharesPayload.filter((l) => l?.shared_with_user_id != null || l?.group_id != null)
    : [];

  isLoading.value = false;
}

const isActive = (item) =>
  Boolean(activePreference.value) &&
  activePreference.value.scope === item.scope &&
  activePreference.value.handbag_name === item.handbag_name &&
  (item.scope !== 'shared' || activePreference.value.owner_id === item.owner_id);

async function selectHandbag(item) {
  const payload = { scope: item.scope, handbag_name: item.handbag_name };
  if (item.scope === 'shared') payload.owner_id = item.owner_id ?? null;
  try {
    await apiClient.put('/api/personalities/preference', payload);
    activePreference.value = payload;
    uiStore.addNotification(`Active personality set to "${item.name}"`, 'success');
  } catch (e) {
    uiStore.addNotification(
      describeError(e) || 'Failed to set active personality.',
      'error'
    );
  }
}

function openEditor(item) {
  editorHandbag.value = item;
  showEditor.value = true;
}

async function deleteHandbag(item) {
  if (!confirm(`Delete personality "${item.name}"? Its handbag folder will be removed.`)) return;
  try {
    await apiClient.delete(
      `/api/personalities/studio/handbags/${item.scope}/${encodeURIComponent(item.handbag_name)}`
    );
    uiStore.addNotification(`"${item.name}" deleted.`, 'success');
    fetchCatalog();
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Failed to delete personality.', 'error');
  }
}

async function handleUploadZip(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  try {
    await apiClient.post('/api/personalities/studio/upload', form, {
      params: { scope: 'personal' },
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    uiStore.addNotification('Personality installed.', 'success');
    fetchCatalog();
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Failed to install personality ZIP.', 'error');
  }
}

function openShare(item) {
  shareHandbagName.value = item.handbag_name;
  shareOwner.value = item.owner;
  showShareModal.value = true;
}

async function revokeShare(link) {
  try {
    await apiClient.delete(`/api/personalities/share/${link.id}`);
    receivedShares.value = receivedShares.value.filter((l) => l.id !== link.id);
    uiStore.addNotification('Share revoked.', 'success');
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Failed to revoke share.', 'error');
  }
}

const sectionIcon = (scope) =>
  scope === 'global' ? IconGlobeAlt : scope === 'personal' ? IconUserCircle : IconUserGroup;

onMounted(fetchCatalog);
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-100">Personalities</h3>
      <div class="flex items-center gap-2">
        <input ref="uploadInput" type="file" accept=".zip" class="hidden" @change="handleUploadZip">
        <button
          class="px-3 py-1.5 text-sm rounded bg-gray-200 dark:bg-gray-700 hover:bg-gray-300"
          @click="uploadInput?.click()"
        >
          Upload ZIP
        </button>
        <button
          class="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          :disabled="isLoading"
          @click="fetchCatalog"
        >
          Refresh
        </button>
      </div>
    </div>

    <p v-if="loadError" class="text-sm text-red-600 dark:text-red-400">{{ loadError }}</p>
    <p v-if="isLoading" class="text-sm text-gray-500 dark:text-gray-400">Loading catalog…</p>

    <template v-else>
      <section
        v-for="scope in ['global', 'personal', 'shared']"
        :key="scope"
        class="space-y-3"
      >
        <div class="flex items-center gap-2">
          <component :is="sectionIcon(scope)" class="w-5 h-5 text-gray-600 dark:text-gray-300" />
          <h4 class="text-base font-medium capitalize text-gray-700 dark:text-gray-200">
            {{ scope === 'personal' ? 'My Personalities' : scope === 'global' ? 'Global Personalities' : 'Shared With Me' }}
          </h4>
          <span class="text-xs text-gray-500">({{ catalog[scope].length }})</span>
        </div>

        <ul v-if="catalog[scope].length" class="divide-y divide-gray-200 dark:divide-gray-700 rounded border border-gray-200 dark:border-gray-700">
          <li
            v-for="item in catalog[scope]"
            :key="`${item.scope}:${item.owner || ''}:${item.handbag_name}`"
            class="flex items-center justify-between gap-3 p-3"
            :class="{ 'bg-blue-50 dark:bg-blue-900/20': isActive(item) }"
          >
            <!-- Avatar -->
            <div class="shrink-0">
              <img
                v-if="item.icon_base64"
                :src="item.icon_base64"
                alt=""
                class="w-10 h-10 rounded-xl object-cover"
              >
              <div
                v-else
                class="w-10 h-10 rounded-xl flex items-center justify-center text-white text-sm font-bold select-none"
                :style="{ backgroundColor: hashColor(item.handbag_name || item.name) }"
                :title="item.name"
              >
                {{ initials(item.name) }}
              </div>
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium truncate">{{ item.name }}</span>
                <code class="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{{ item.handbag_name }}</code>
                <span v-if="isActive(item)" class="inline-flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                  <IconCheckCircle class="w-4 h-4" /> Active
                </span>
                <span v-if="item.scope === 'shared'" class="text-xs text-gray-500">
                  by {{ item.owner }}
                </span>
              </div>
              <p class="text-xs text-gray-500 truncate">
                {{ item.category || 'Uncategorized' }} · {{ item.author || 'Unknown author' }}
              </p>
              <p v-if="item.description" class="text-sm text-gray-600 dark:text-gray-300 mt-1 line-clamp-2">
                {{ item.description }}
              </p>
              <div class="flex flex-wrap gap-1 mt-2">
                <span v-if="item.has_soul" class="inline-flex items-center gap-1 rounded bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 text-xs">
                  <IconBookOpen class="w-3.5 h-3.5" /> Soul
                </span>
                <span v-if="item.has_tools" class="inline-flex items-center gap-1 rounded bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 text-xs">
                  <IconCode class="w-3.5 h-3.5" /> Tools
                </span>
                <span v-if="item.has_rag" class="inline-flex items-center gap-1 rounded bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 text-xs">
                  <IconDataZone class="w-3.5 h-3.5" /> RAG
                </span>
                <span v-if="item.has_docs" class="inline-flex items-center gap-1 rounded bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 text-xs">
                  <IconDocumentText class="w-3.5 h-3.5" /> Docs
                </span>
                <span v-if="item.has_skills" class="inline-flex items-center gap-1 rounded bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 text-xs">
                  <IconMagic class="w-3.5 h-3.5" /> Skills
                </span>
              </div>
            </div>

            <div class="flex shrink-0 items-center gap-2">
              <button
                class="px-3 py-1 text-xs rounded"
                :class="isActive(item)
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 cursor-default'
                  : 'bg-blue-600 text-white hover:bg-blue-700'"
                :disabled="isActive(item)"
                @click="selectHandbag(item)"
              >
                {{ isActive(item) ? 'Selected' : 'Select' }}
              </button>
              <button
                class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                title="View details"
                @click="openEditor(item)"
              >
                <IconPencil class="w-4 h-4" />
              </button>
              <button
                v-if="item.scope === 'personal'"
                class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                title="Share"
                @click="openShare(item)"
              >
                <IconShare class="w-4 h-4" />
              </button>
              <button
                v-if="canEdit(item)"
                class="p-1.5 rounded text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30"
                title="Delete"
                @click="deleteHandbag(item)"
              >
                <IconTrash class="w-4 h-4" />
              </button>
            </div>
          </li>
        </ul>
        <p v-else class="text-sm text-gray-400 italic">No personalities in this scope.</p>
      </section>

      <section v-if="receivedShares.length" class="space-y-2">
        <h4 class="text-base font-medium text-gray-700 dark:text-gray-200">Share Links</h4>
        <ul class="divide-y divide-gray-200 dark:divide-gray-700 rounded border border-gray-200 dark:border-gray-700">
          <li
            v-for="link in receivedShares"
            :key="link.id"
            class="flex items-center justify-between p-3 text-sm"
          >
            <span>
              <strong>{{ link.handbag_name }}</strong>
              <span class="text-gray-500">
                shared with {{ link.shared_with_user_id != null ? `user #${link.shared_with_user_id}` : `group #${link.group_id}` }}
              </span>
            </span>
            <button
              class="p-1.5 rounded text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30"
              title="Revoke share"
              @click="revokeShare(link)"
            >
              <IconTrash class="w-4 h-4" />
            </button>
          </li>
        </ul>
      </section>
    </template>

    <PersonalityEditorModal
      v-if="showEditor"
      :handbag="editorHandbag"
      @close="showEditor = false"
    />
    <SharePersonalityModal
      v-if="showShareModal"
      :handbag-name="shareHandbagName"
      :owner="shareOwner"
      @close="showShareModal = false"
      @shared="fetchCatalog"
    />
  </div>
</template>