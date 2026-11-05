<script setup>
import { ref, computed, onMounted, watch, markRaw } from 'vue';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import PersonalityEditorModal from '@/components/modals/PersonalityEditorModal.vue';
import SharePersonalityModal from '@/components/modals/SharePersonalityModal.vue';
import CodeMirrorEditor from '@/components/ui/CodeMirrorComponent/index.vue';
import apiClient from '@/services/api';
import { useUiStore } from '@/stores/ui';
import { useAuthStore } from '@/stores/auth';
import { useDataStore } from '@/stores/data';
import useEventBus from '@/services/eventBus';

import IconUserCircle from '../assets/icons/IconUserCircle.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconDataZone from '../assets/icons/IconDataZone.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconShare from '../assets/icons/IconShare.vue';

const uiStore = useUiStore();
const authStore = useAuthStore();
const dataStore = useDataStore();
const { emit } = useEventBus();
const titleIcon = markRaw(IconUserCircle);

// ---------- Catalog ----------
const catalog = ref({ global: [], personal: [], shared: [] });
const activePreference = ref(null);
const isLoading = ref(true);
const loadError = ref(null);
const receivedShares = ref([]);

// ---------- Selection ----------
const selectedHandbag = ref(null);
const isLoadingDetail = ref(false);
const detail = ref(null);
const activeTab = ref('SOUL');

// ---------- Per-tab editor buffers ----------
// Each buffer is independent so AI generation targeting "skill" cannot corrupt
// the SOUL buffer (or vice versa). `editorContent` is a two-way computed routed
// off the currently-visible tab.
const soulBuffer = ref('');
const skillBuffer = ref('');
const toolBuffer = ref('');
let suppressTabWatch = false;

const editorContent = computed({
  get() {
    if (activeTab.value === 'SOUL') return soulBuffer.value;
    if (activeTab.value === 'Skills') return skillBuffer.value;
    if (activeTab.value === 'Tools') return toolBuffer.value;
    return '';
  },
  set(val) {
    if (activeTab.value === 'SOUL') soulBuffer.value = val;
    else if (activeTab.value === 'Skills') skillBuffer.value = val;
    else if (activeTab.value === 'Tools') toolBuffer.value = val;
  },
});

const isSavingContent = ref(false);

// ---------- Skill / Tool selection ----------
const activeSkillName = ref(null);
const isNewSkill = ref(false);
const activeToolName = ref(null);
const isNewTool = ref(false);
const newNameInput = ref('');

// ---------- Metadata form ----------
const metaForm = ref({
  display_name: '',
  description: '',
  author: '',
  category: '',
  icon_base64: null,
});

// ---------- AI (context-aware) ----------
// The AI panel adapts to the currently-open tab. Each resource descriptor
// carries the buffer the user is editing plus the endpoint that produces an
// updated version of that same resource. This is the single source of truth
// the unified handler uses — no per-tab branching exists here.
const aiPrompt = ref('');
const isGenerating = ref(false);

const activeResource = computed(() => {
  const tab = activeTab.value;
  if (tab === 'SOUL') {
    return {
      type: 'soul',
      label: 'Soul',
      content: soulBuffer.value,
      generateEndpoint: '/api/personalities/studio/generate_soul',
    };
  }
  if (tab === 'Skills') {
    return {
      type: 'skill',
      label: 'Skill',
      content: skillBuffer.value,
      generateEndpoint: '/api/personalities/studio/generate_skill',
    };
  }
  if (tab === 'Tools') {
    return {
      type: 'tool',
      label: 'Tool',
      content: toolBuffer.value,
      generateEndpoint: '/api/personalities/studio/generate_tool',
    };
  }
  return null; // Databases / Metadata have no AI-editable buffer.
});

const activeResourceActionLabel = computed(() => {
  const r = activeResource.value;
  if (!r) return 'No AI target';
  const hasContent = typeof r.content === 'string' && r.content.trim().length > 0;
  return hasContent ? `Update ${r.label} with AI` : `Create ${r.label} with AI`;
});

// TTI icon generation: available only when the user has at least one TTI model
// profile configured (the exact "only if a TTI model profile exists" gate).
const isGeneratingIcon = ref(false);
const isTtiAvailable = computed(() => Boolean((dataStore.availableTtiModels?.length || 0) > 0));

// ---------- Modals ----------
const showEditor = ref(false);
const editorHandbag = ref(null);
const showShareModal = ref(false);
const shareHandbagName = ref(null);
const shareOwner = ref(null);
const uploadInput = ref(null);

// ---------- Helpers ----------
const canEdit = (item) =>
  !!item &&
  (item.scope === 'personal' ||
    (item.scope === 'global' && Boolean(authStore.user?.is_admin)));

function describeError(e) {
  const d = e?.response?.data?.detail;
  if (typeof d === 'string' && d) return d;
  if (d) return JSON.stringify(d);
  if (e?.message) return e.message;
  return null;
}

function initials(name) {
  const s = String(name || '?').trim();
  if (!s) return '?';
  return s.split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
}

function hashColor(str) {
  let hash = 0;
  const s = String(str || '');
  for (let i = 0; i < s.length; i += 1) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
  return `hsl(${hash % 360}, 65%, 45%)`;
}

function isActive(item) {
  if (!activePreference.value || !item) return false;
  return activePreference.value.scope === item.scope &&
    activePreference.value.handbag_name === item.handbag_name &&
    (item.scope !== 'shared' || activePreference.value.owner_id === item.owner_id);
}

// Shared-scope endpoints require `owner_id` in the query string; personal/global do not.
function detailParams(item, extra = {}) {
  const params = { ...extra };
  if (item && item.scope === 'shared' && item.owner_id != null) {
    params.owner_id = item.owner_id;
  }
  return params;
}

// ---------- Catalog fetch ----------
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
    loadError.value = describeError(catRes.reason) || 'Failed to load catalog.';
  }
  activePreference.value = prefRes.status === 'fulfilled' ? (prefRes.value?.data ?? null) : null;
  const sharesPayload = sharesRes.status === 'fulfilled' ? sharesRes.value?.data : null;
  receivedShares.value = Array.isArray(sharesPayload)
    ? sharesPayload.filter(l => l?.shared_with_user_id != null || l?.group_id != null)
    : [];
  isLoading.value = false;

  // Auto-select the active personality, else first personal, else first global.
  if (!selectedHandbag.value) {
    const all = [...catalog.value.global, ...catalog.value.personal, ...catalog.value.shared];
    const target = all.find(i => isActive(i)) ||
      catalog.value.personal[0] ||
      catalog.value.global[0];
    if (target) fetchHandbagDetail(target);
  }
}

// ---------- Detail fetch ----------
async function fetchHandbagDetail(item) {
  if (!item) return;
  selectedHandbag.value = item;
  isLoadingDetail.value = true;
  // Reset buffer state so a stale SOUL/skill/tool cannot bleed across selections.
  soulBuffer.value = '';
  skillBuffer.value = '';
  toolBuffer.value = '';
  activeSkillName.value = null;
  isNewSkill.value = false;
  activeToolName.value = null;
  isNewTool.value = false;
  try {
    const res = await apiClient.get(
      `/api/personalities/studio/handbags/${item.scope}/${encodeURIComponent(item.handbag_name)}`,
      { params: detailParams(item) }
    );
    detail.value = res.data;
    activeTab.value = 'SOUL';
    soulBuffer.value = res.data.prompt_text || '';
    metaForm.value = {
      display_name: res.data.name || '',
      description: res.data.description || '',
      author: res.data.author || '',
      category: res.data.category || '',
      icon_base64: res.data.icon || null,
    };
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Failed to load details.', 'error');
    selectedHandbag.value = null;
    detail.value = null;
  } finally {
    isLoadingDetail.value = false;
  }
}

async function refreshDetail() {
  if (!selectedHandbag.value) return;
  try {
    const res = await apiClient.get(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}`,
      { params: detailParams(selectedHandbag.value) }
    );
    detail.value = res.data;
  } catch (e) {
    uiStore.addNotification('Failed to refresh details.', 'error');
  }
}

// ---------- Preference ----------
async function selectHandbag(item) {
  const payload = { scope: item.scope, handbag_name: item.handbag_name };
  if (item.scope === 'shared') payload.owner_id = item.owner_id ?? null;
  try {
    await apiClient.put('/api/personalities/preference', payload);
    activePreference.value = payload;
    // The global header consumes this event directly, so include the icon and
    // display name — otherwise the header avatar indicator loses the image on
    // selection.
    emit('personality:changed', {
      ...payload,
      name: item.name || item.display_name || item.handbag_name,
      icon: item.icon || null,
    });
    uiStore.addNotification(`Active personality set to "${item.name}"`, 'success');
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Failed to set active.', 'error');
  }
}

// ---------- Modals ----------
function openEditor(item) {
  editorHandbag.value = item;
  showEditor.value = true;
}

function openCreateEditor() {
  editorHandbag.value = null;
  showEditor.value = true;
}

function closeEditor() {
  showEditor.value = false;
  editorHandbag.value = null;
}

function openShare(item) {
  shareHandbagName.value = item.handbag_name;
  shareOwner.value = item.owner;
  showShareModal.value = true;
}

async function deleteHandbag(item) {
  if (!confirm(`Delete personality "${item.name}"?`)) return;
  try {
    await apiClient.delete(
      `/api/personalities/studio/handbags/${item.scope}/${encodeURIComponent(item.handbag_name)}`
    );
    uiStore.addNotification(`"${item.name}" deleted.`, 'success');
    if (selectedHandbag.value?.handbag_name === item.handbag_name) {
      selectedHandbag.value = null;
      detail.value = null;
      soulBuffer.value = '';
      skillBuffer.value = '';
      toolBuffer.value = '';
    }
    fetchCatalog();
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Delete failed.', 'error');
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
    uiStore.addNotification(describeError(e) || 'Upload failed.', 'error');
  }
}

async function revokeShare(link) {
  try {
    await apiClient.delete(`/api/personalities/share/${link.id}`);
    receivedShares.value = receivedShares.value.filter(l => l.id !== link.id);
    uiStore.addNotification('Share revoked.', 'success');
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Revoke failed.', 'error');
  }
}

function handleHandbagChange(event) {
  const key = event.target.value;
  if (!key) return;
  const all = [...catalog.value.global, ...catalog.value.personal, ...catalog.value.shared];
  const item = all.find(i => `${i.scope}:${i.handbag_name}` === key);
  if (item) fetchHandbagDetail(item);
}

// ---------- SOUL ----------
async function saveSoul() {
  if (!selectedHandbag.value) return;
  isSavingContent.value = true;
  try {
    await apiClient.put(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}`,
      { prompt_text: soulBuffer.value }
    );
    uiStore.addNotification('SOUL saved.', 'success');
    if (detail.value) detail.value.prompt_text = soulBuffer.value;
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Save failed.', 'error');
  } finally {
    isSavingContent.value = false;
  }
}

// ---------- Metadata ----------
function handleIconUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => { metaForm.value.icon_base64 = reader.result; };
  reader.readAsDataURL(file);
}

async function saveMetadata() {
  if (!selectedHandbag.value) return;
  isSavingContent.value = true;
  try {
    await apiClient.put(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}`,
      {
        display_name: metaForm.value.display_name,
        description: metaForm.value.description,
        author: metaForm.value.author,
        category: metaForm.value.category,
        icon_base64: metaForm.value.icon_base64,
      }
    );
    uiStore.addNotification('Metadata saved.', 'success');
    await refreshDetail();
    // If the edited handbag is the active personality, notify the global
    // header so the icon / display name update without a page reload.
    if (selectedHandbag.value && isActive(selectedHandbag.value)) {
      const payload = {
        scope: selectedHandbag.value.scope,
        handbag_name: selectedHandbag.value.handbag_name,
        name: metaForm.value.display_name || selectedHandbag.value.name,
        icon: metaForm.value.icon_base64 || detail.value?.icon || null,
      };
      if (selectedHandbag.value.scope === 'shared') {
        payload.owner_id = selectedHandbag.value.owner_id ?? null;
      }
      emit('personality:changed', payload);
    }
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Save failed.', 'error');
  } finally {
    isSavingContent.value = false;
  }
}

// ---------- Icon generation (TTI) ----------
async function generateIcon() {
  if (!isTtiAvailable.value || isGeneratingIcon.value) return;
  if (!canEdit(selectedHandbag.value) || !metaForm.value) return;
  isGeneratingIcon.value = true;
  try {
    const name = metaForm.value.display_name || 'AI Assistant';
    const category = metaForm.value.category || 'General';
    const description = metaForm.value.description || '';
    const prompt = `Profile icon/avatar of ${name}, ${category}. ${description}. High quality digital art, centered, portrait.`;
    const res = await apiClient.post('/api/personalities/generate_icon', { prompt });
    const icon = res?.data?.icon_base64;
    if (typeof icon !== 'string' || !icon) {
      throw new Error('Icon endpoint returned an unexpected response.');
    }
    // Populate the live preview only. The user reviews the result and clicks
    // the existing "Save Metadata" button — do not persist automatically.
    metaForm.value.icon_base64 = icon;
    uiStore.addNotification('Icon generated. Review and Save Metadata.', 'success');
  } catch (e) {
    if (e?.response?.status === 404) {
      uiStore.addNotification(
        'Icon-generation endpoint missing. Restart server after applying backend patches.',
        'error'
      );
    } else {
      uiStore.addNotification(describeError(e) || 'Icon generation failed.', 'error');
    }
  } finally {
    isGeneratingIcon.value = false;
  }
}

// ---------- Skills ----------
async function selectSkill(name) {
  activeSkillName.value = name;
  isNewSkill.value = false;
  if (!name) { skillBuffer.value = ''; return; }
  try {
    const res = await apiClient.get(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/skills/${encodeURIComponent(name)}`,
      { params: detailParams(selectedHandbag.value) }
    );
    skillBuffer.value = res.data.content;
  } catch (e) {
    uiStore.addNotification('Failed to load skill.', 'error');
  }
}

function startNewSkill() {
  activeSkillName.value = null;
  isNewSkill.value = true;
  newNameInput.value = 'new_skill.md';
  skillBuffer.value = '# New Skill\n\n';
}

async function saveSkill() {
  const name = isNewSkill.value ? newNameInput.value : activeSkillName.value;
  if (!name) { uiStore.addNotification('Name required.', 'warning'); return; }
  isSavingContent.value = true;
  try {
    await apiClient.post(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/skills`,
      { name, content: skillBuffer.value }
    );
    uiStore.addNotification('Skill saved.', 'success');
    await refreshDetail();
    activeSkillName.value = name;
    isNewSkill.value = false;
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Save failed.', 'error');
  } finally {
    isSavingContent.value = false;
  }
}

async function exportSkillToLibrary() {
  if (!activeSkillName.value || !selectedHandbag.value) return;
  try {
    await apiClient.post(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/skills/${encodeURIComponent(activeSkillName.value)}/to-library`
    );
    uiStore.addNotification('Skill exported to library.', 'success');
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Export failed.', 'error');
  }
}

async function importSkillFromLibrary() {
  if (!selectedHandbag.value) return;
  const name = prompt('Enter library skill name (e.g., web_search):');
  if (!name) return;
  try {
    await apiClient.post(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/skills/from-library`,
      { name }
    );
    uiStore.addNotification('Skill imported.', 'success');
    await refreshDetail();
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Import failed.', 'error');
  }
}

// ---------- Tools ----------
async function selectTool(name) {
  activeToolName.value = name;
  isNewTool.value = false;
  if (!name) { toolBuffer.value = ''; return; }
  try {
    const res = await apiClient.get(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/tools/${encodeURIComponent(name)}`,
      { params: detailParams(selectedHandbag.value) }
    );
    toolBuffer.value = res.data.content;
  } catch (e) {
    uiStore.addNotification('Failed to load tool.', 'error');
  }
}

function startNewTool() {
  activeToolName.value = null;
  isNewTool.value = true;
  newNameInput.value = 'new_tool.py';
  toolBuffer.value = 'def new_tool():\n    """Tool description."""\n    pass\n';
}

async function saveTool() {
  const name = isNewTool.value ? newNameInput.value : activeToolName.value;
  if (!name) { uiStore.addNotification('Filename required.', 'warning'); return; }
  isSavingContent.value = true;
  try {
    await apiClient.put(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/tools/${encodeURIComponent(name)}`,
      { content: toolBuffer.value }
    );
    uiStore.addNotification('Tool saved.', 'success');
    await refreshDetail();
    activeToolName.value = name;
    isNewTool.value = false;
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Save failed.', 'error');
  } finally {
    isSavingContent.value = false;
  }
}

// ---------- AI generation (unified, context-aware) ----------
// One handler for every tab type. Reads the currently-open tab's buffer,
// forwards it as `existing_content` when it is non-empty (edit) or omits it
// (create), then writes the AI-updated content back into the same buffer. The
// user then clicks the tab's own Save button — no hidden writes.
async function applyPromptToActiveResource() {
  const resource = activeResource.value;
  if (!resource || !aiPrompt.value.trim() || isGenerating.value) return;
  isGenerating.value = true;
  try {
    const payload = { prompt: aiPrompt.value };
    if (typeof resource.content === 'string' && resource.content.trim().length > 0) {
      payload.existing_content = resource.content;
    }

    const res = await apiClient.post(resource.generateEndpoint, payload);
    const raw = res?.data;
    const content = typeof raw === 'string' ? raw : raw?.content;
    if (typeof content !== 'string' || content.length === 0) {
      throw new Error(
        'AI endpoint returned an unexpected response. ' +
        'Verify the backend endpoint exists and a model is configured.'
      );
    }

    // Write directly into the buffer that was targeted — do not switch tabs;
    // the button already sits in the correct editor context.
    if (resource.type === 'soul') {
      soulBuffer.value = content;
    } else if (resource.type === 'skill') {
      skillBuffer.value = content;
      if (!activeSkillName.value && !isNewSkill.value) {
        isNewSkill.value = true;
        newNameInput.value = 'ai_skill.md';
      }
    } else if (resource.type === 'tool') {
      toolBuffer.value = content;
      if (!activeToolName.value && !isNewTool.value) {
        isNewTool.value = true;
        newNameInput.value = 'ai_tool.py';
      }
    }
    uiStore.addNotification(
      `AI drafted the ${resource.label.toLowerCase()}. Review and Save.`,
      'success'
    );
    aiPrompt.value = '';
  } catch (e) {
    if (e?.response?.status === 404) {
      uiStore.addNotification(
        `AI endpoint for ${resource.label} is missing on the backend. Restart the server after applying backend patches.`,
        'error'
      );
    } else {
      uiStore.addNotification(describeError(e) || 'AI generation failed.', 'error');
    }
  } finally {
    isGenerating.value = false;
  }
}

// ---------- Tab change ----------
watch(activeTab, (newTab) => {
  if (!detail.value) return;
  if (newTab === 'SOUL') {
    soulBuffer.value = detail.value.prompt_text || '';
  } else if (newTab === 'Metadata') {
    metaForm.value = {
      display_name: detail.value.name || '',
      description: detail.value.description || '',
      author: detail.value.author || '',
      category: detail.value.category || '',
      icon_base64: detail.value.icon || null,
    };
  } else if (newTab === 'Skills') {
    if (activeSkillName.value) {
      selectSkill(activeSkillName.value);
    } else if (detail.value.skills?.length > 0) {
      selectSkill(detail.value.skills[0]);
    } else {
      startNewSkill();
    }
  } else if (newTab === 'Tools') {
    if (activeToolName.value) {
      selectTool(activeToolName.value);
    } else if (detail.value.tools?.length > 0) {
      selectTool(detail.value.tools[0]);
    } else {
      startNewTool();
    }
  }
});

onMounted(fetchCatalog);
</script>

<template>
  <PageViewLayout title="Personality Studio" :title-icon="titleIcon" :show-sidebar="false">
    <template #main>
      <div class="flex h-full w-full overflow-hidden bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
        <!-- ===== Center canvas ===== -->
        <main class="flex-1 flex flex-col min-w-0 bg-white dark:bg-gray-900">
          <!-- Compact persona picker. The full browseable list lives only in
               the app sidebar (DiscussionList.vue → PERS tab); this control
               merely offers quick switching inside the editor without
               duplicating that list in a second column. -->
          <div class="shrink-0 px-3 py-2 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50 flex items-center gap-2">
            <div class="w-8 h-8 rounded flex-shrink-0 flex items-center justify-center text-xs font-bold text-white shadow-sm"
                 :style="{ backgroundColor: selectedHandbag ? hashColor(selectedHandbag.handbag_name) : 'transparent' }">
              <img v-if="selectedHandbag?.icon" :src="selectedHandbag.icon" class="w-full h-full object-cover rounded" />
              <span v-else-if="selectedHandbag">{{ initials(selectedHandbag.name) }}</span>
              <IconUserCircle v-else class="w-5 h-5 text-gray-400" />
            </div>
            <select
              :value="selectedHandbag ? `${selectedHandbag.scope}:${selectedHandbag.handbag_name}` : ''"
              @change="handleHandbagChange"
              class="input-field text-sm flex-1 min-w-0"
              :disabled="isLoading"
            >
              <option value="" disabled>{{ isLoading ? 'Loading…' : 'Select a personality to edit…' }}</option>
              <optgroup label="Global" v-if="catalog.global.length">
                <option v-for="item in catalog.global" :key="`global:${item.handbag_name}`" :value="`global:${item.handbag_name}`">
                  {{ item.name }}{{ isActive(item) ? ' ●' : '' }}
                </option>
              </optgroup>
              <optgroup label="Personal" v-if="catalog.personal.length">
                <option v-for="item in catalog.personal" :key="`personal:${item.handbag_name}`" :value="`personal:${item.handbag_name}`">
                  {{ item.name }}{{ isActive(item) ? ' ●' : '' }}
                </option>
              </optgroup>
              <optgroup label="Shared" v-if="catalog.shared.length">
                <option v-for="item in catalog.shared" :key="`shared:${item.handbag_name}`" :value="`shared:${item.handbag_name}`">
                  {{ item.name }}{{ isActive(item) ? ' ●' : '' }}
                </option>
              </optgroup>
            </select>
            <button @click="openCreateEditor" class="btn btn-primary btn-sm text-xs font-semibold shrink-0" title="New personality">New</button>
            <button @click="uploadInput?.click()" class="btn btn-secondary btn-sm text-xs shrink-0" title="Upload personality ZIP">Upload</button>
            <input ref="uploadInput" type="file" accept=".zip" class="hidden" @change="handleUploadZip" />
            <button @click="fetchCatalog" class="btn btn-secondary btn-sm text-xs shrink-0" title="Refresh catalog" :disabled="isLoading">⟳</button>
          </div>
          <div v-if="!selectedHandbag" class="flex-1 flex flex-col items-center justify-center text-gray-400">
            <IconUserCircle class="w-16 h-16 mb-4 text-gray-300 dark:text-gray-600" />
            <p class="text-lg">Select a personality to edit</p>
          </div>
          <div v-else-if="isLoadingDetail" class="flex-1 flex items-center justify-center text-gray-500">
            Loading...
          </div>
          <template v-else-if="detail">
            <!-- Tab bar + header actions -->
            <div class="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50 px-4">
              <div class="flex gap-1">
                <button
                  v-for="tab in ['SOUL', 'Skills', 'Tools', 'Databases', 'Metadata']"
                  :key="tab"
                  @click="activeTab = tab"
                  class="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
                  :class="activeTab === tab ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                >
                  {{ tab }}
                </button>
              </div>
              <div class="flex items-center gap-2">
                <button v-if="!isActive(selectedHandbag)" @click="selectHandbag(selectedHandbag)" class="btn btn-secondary btn-sm text-xs font-semibold">Set Active</button>
                <div v-else class="text-xs text-green-600 font-bold flex items-center gap-1 mr-2">
                  <IconCheckCircle class="w-4 h-4" />
                  Active
                </div>
                <button v-if="canEdit(selectedHandbag)" @click="openEditor(selectedHandbag)" class="btn btn-secondary btn-sm text-xs">
                  <IconPencil class="w-3.5 h-3.5 mr-1" /> Edit
                </button>
                <button v-if="selectedHandbag.scope === 'personal'" @click="openShare(selectedHandbag)" class="btn btn-secondary btn-sm text-xs">
                  <IconShare class="w-3.5 h-3.5 mr-1" /> Share
                </button>
                <button v-if="canEdit(selectedHandbag)" @click="deleteHandbag(selectedHandbag)" class="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded" title="Delete">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
              </div>
            </div>

            <!-- Tab panels -->
            <div class="flex-1 flex min-h-0 relative">
              <!-- SOUL -->
              <div v-if="activeTab === 'SOUL'" class="flex-1 flex flex-col min-w-0">
                <div class="p-2 border-b border-gray-200 dark:border-gray-800 flex justify-end bg-white dark:bg-gray-900">
                  <button @click="saveSoul" :disabled="isSavingContent || !canEdit(selectedHandbag)" class="btn btn-primary btn-sm text-xs">
                    <IconCheckCircle class="w-4 h-4 mr-1" /> Save SOUL
                  </button>
                </div>
                <div class="flex-1 relative">
                  <CodeMirrorEditor v-model="editorContent" language="markdown" class="absolute inset-0" :read-only="!canEdit(selectedHandbag)" />
                </div>
              </div>

              <!-- Databases -->
              <div v-if="activeTab === 'Databases'" class="flex-1 p-6 overflow-y-auto">
                <h3 class="text-lg font-medium mb-4">Attached Databases (RAG)</h3>
                <div v-if="detail.databases && detail.databases.length" class="space-y-2 max-w-2xl">
                  <div v-for="db in detail.databases" :key="db" class="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 flex items-center gap-3">
                    <IconDataZone class="w-5 h-5 text-blue-500" />
                    <span class="font-mono text-sm">{{ db }}</span>
                  </div>
                </div>
                <p v-else class="text-gray-500 italic">No databases attached to this personality.</p>
              </div>

              <!-- Metadata -->
              <div v-if="activeTab === 'Metadata'" class="flex-1 p-6 overflow-y-auto w-full max-w-2xl mx-auto space-y-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Display Name</label>
                  <input v-model="metaForm.display_name" type="text" class="input-field mt-1 w-full" :disabled="!canEdit(selectedHandbag)">
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Description</label>
                  <textarea v-model="metaForm.description" rows="3" class="input-field mt-1 w-full" :disabled="!canEdit(selectedHandbag)"></textarea>
                </div>
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Author</label>
                    <input v-model="metaForm.author" type="text" class="input-field mt-1 w-full" :disabled="!canEdit(selectedHandbag)">
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Category</label>
                    <input v-model="metaForm.category" type="text" class="input-field mt-1 w-full" :disabled="!canEdit(selectedHandbag)">
                  </div>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Icon</label>
                  <div class="flex items-start gap-4 mt-1">
                    <img v-if="metaForm.icon_base64" :src="metaForm.icon_base64" class="w-16 h-16 rounded-lg object-cover border border-gray-200 dark:border-gray-700 shrink-0">
                    <div v-else class="w-16 h-16 rounded-lg bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-xs text-gray-500 shrink-0">None</div>
                    <div class="flex flex-col gap-2 min-w-0">
                      <input v-if="canEdit(selectedHandbag)" type="file" accept="image/*" @change="handleIconUpload" class="text-sm">
                      <button
                        v-if="isTtiAvailable && canEdit(selectedHandbag)"
                        @click="generateIcon"
                        :disabled="isGeneratingIcon"
                        class="btn btn-secondary btn-sm text-xs inline-flex items-center"
                        title="Generate an icon with the configured TTI model"
                      >
                        <IconSparkles v-if="!isGeneratingIcon" class="w-3.5 h-3.5 mr-1" />
                        <IconAnimateSpin v-else class="w-3.5 h-3.5 mr-1 animate-spin" />
                        {{ isGeneratingIcon ? 'Generating…' : 'Generate Icon with AI' }}
                      </button>
                    </div>
                  </div>
                </div>
                <div class="pt-4">
                  <button @click="saveMetadata" :disabled="isSavingContent || !canEdit(selectedHandbag)" class="btn btn-primary">
                    <IconCheckCircle class="w-4 h-4 mr-1" /> Save Metadata
                  </button>
                </div>
              </div>

              <!-- Skills / Tools -->
              <template v-if="activeTab === 'Skills' || activeTab === 'Tools'">
                <div class="w-56 border-r border-gray-200 dark:border-gray-800 flex flex-col bg-gray-50 dark:bg-gray-800/50">
                  <div class="p-2 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
                    <span class="text-xs font-bold text-gray-500 uppercase">{{ activeTab }}</span>
                    <button v-if="canEdit(selectedHandbag)" @click="activeTab === 'Skills' ? startNewSkill() : startNewTool()" class="text-blue-500 hover:text-blue-600 text-xs font-semibold">+ New</button>
                  </div>
                  <div class="flex-1 overflow-y-auto">
                    <template v-if="activeTab === 'Skills'">
                      <div
                        v-for="s in (detail.skills || [])"
                        :key="s"
                        @click="selectSkill(s)"
                        class="px-3 py-2 text-sm cursor-pointer truncate hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                        :class="{'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-medium': activeSkillName === s && !isNewSkill}"
                      >
                        {{ s }}
                      </div>
                      <div v-if="!(detail.skills && detail.skills.length)" class="px-3 py-2 text-xs text-gray-400 italic">No skills</div>
                    </template>
                    <template v-if="activeTab === 'Tools'">
                      <div
                        v-for="t in (detail.tools || [])"
                        :key="t"
                        @click="selectTool(t)"
                        class="px-3 py-2 text-sm cursor-pointer truncate hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                        :class="{'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-medium': activeToolName === t && !isNewTool}"
                      >
                        {{ t }}
                      </div>
                      <div v-if="!(detail.tools && detail.tools.length)" class="px-3 py-2 text-xs text-gray-400 italic">No tools</div>
                    </template>
                  </div>
                  <div v-if="activeTab === 'Skills' && canEdit(selectedHandbag)" class="p-2 border-t border-gray-200 dark:border-gray-700">
                    <button @click="importSkillFromLibrary" class="btn btn-secondary btn-sm w-full text-xs">From Library</button>
                  </div>
                </div>
                <div class="flex-1 flex flex-col min-w-0">
                  <div class="p-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between bg-white dark:bg-gray-900 gap-2">
                    <div class="flex items-center gap-2 min-w-0">
                      <span class="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">
                        {{ isNewSkill || isNewTool ? 'New ' + activeTab.slice(0, -1) : (activeTab === 'Skills' ? (activeSkillName || '') : (activeToolName || '')) }}
                      </span>
                      <input v-if="(isNewSkill || isNewTool) && canEdit(selectedHandbag)" v-model="newNameInput" placeholder="filename.ext" class="input-field text-xs px-2 py-1 h-7 w-40">
                    </div>
                    <div class="flex items-center gap-2 shrink-0">
                      <button
                        v-if="activeTab === 'Skills' && !isNewSkill && activeSkillName && canEdit(selectedHandbag)"
                        @click="exportSkillToLibrary"
                        class="btn btn-secondary btn-sm text-xs"
                      >
                        Export to Library
                      </button>
                      <button
                        @click="activeTab === 'Skills' ? saveSkill() : saveTool()"
                        :disabled="isSavingContent || !canEdit(selectedHandbag)"
                        class="btn btn-primary btn-sm text-xs"
                      >
                        <IconCheckCircle class="w-4 h-4 mr-1" /> Save
                      </button>
                    </div>
                  </div>
                  <div class="flex-1 relative">
                    <CodeMirrorEditor
                      v-model="editorContent"
                      :language="activeTab === 'Tools' ? 'python' : 'markdown'"
                      class="absolute inset-0"
                      :read-only="!canEdit(selectedHandbag)"
                    />
                  </div>
                </div>
              </template>
            </div>
          </template>
        </main>

        <!-- ===== Right AI assistant ===== -->
        <aside class="w-72 flex flex-col border-l border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/30">
          <div class="p-4 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
            <h3 class="font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
              <IconSparkles class="w-4 h-4 text-purple-500" /> LoLLMs Copilot
            </h3>
          </div>
          <div class="p-4 space-y-4 flex-1 overflow-y-auto">
            <div class="flex items-center gap-2 text-xs flex-wrap">
              <span class="font-bold text-gray-500 uppercase tracking-wider">AI Target</span>
              <span
                v-if="activeResource"
                class="px-2 py-0.5 rounded-full bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 font-semibold border border-teal-200 dark:border-teal-800"
              >
                {{ activeResource.label }}
              </span>
              <span v-else class="text-amber-600 dark:text-amber-400 font-medium">
                No editable tab open
              </span>
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Instructions</label>
              <textarea
                v-model="aiPrompt"
                rows="4"
                class="input-field w-full text-sm resize-none"
                :placeholder="activeResource ? `e.g. Add a section on error handling...` : 'Open SOUL, Skills, or Tools to use AI editing.'"
                :disabled="!activeResource"
              ></textarea>
            </div>
            <button
              @click="applyPromptToActiveResource"
              :disabled="!aiPrompt || isGenerating || !activeResource || !canEdit(selectedHandbag)"
              class="btn btn-primary w-full text-sm"
              :title="!activeResource ? 'Open SOUL, Skills or Tools to use AI editing' : ''"
            >
              <IconSparkles v-if="!isGenerating" class="w-4 h-4 mr-2" />
              <IconAnimateSpin v-else class="w-4 h-4 mr-2 animate-spin" />
              {{ isGenerating ? 'Generating…' : activeResourceActionLabel }}
            </button>
            <div class="text-[11px] text-gray-500 mt-2">
              <p>
                The current {{ activeResource?.label.toLowerCase() ?? 'tab' }} content is sent as context so the AI
                <strong>{{ activeResource && activeResource.content.trim().length > 0 ? 'updates' : 'writes' }}</strong>
                it instead of starting from scratch. Result lands in the editor; click Save on that tab to persist.
              </p>
            </div>
          </div>
        </aside>
      </div>

      <!-- Modals -->
      <PersonalityEditorModal
        v-if="showEditor"
        :personality="editorHandbag"
        @close="closeEditor"
        @saved="() => { fetchCatalog(); if (selectedHandbag) refreshDetail(); }"
      />
      <SharePersonalityModal
        v-if="showShareModal"
        :handbag-name="shareHandbagName"
        :owner="shareOwner"
        @close="showShareModal = false"
        @shared="fetchCatalog"
      />
    </template>
  </PageViewLayout>
</template>