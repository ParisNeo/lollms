
<script setup>
import { ref, computed, onMounted, watch, markRaw } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import PersonalityEditorModal from '@/components/modals/PersonalityEditorModal.vue';
import SharePersonalityModal from '@/components/modals/SharePersonalityModal.vue';
import CodeMirrorEditor from '@/components/ui/CodeMirrorComponent/index.vue';
import apiClient from '@/services/api';
import { useUiStore } from '@/stores/ui';
import { useAuthStore } from '@/stores/auth';
import { useDataStore } from '@/stores/data';
import useEventBus from '@/services/eventBus';
import { useSettingsPolicy } from '@/composables/useSettingsPolicy';

import IconUserCircle from '../assets/icons/IconUserCircle.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconDataZone from '../assets/icons/IconDataZone.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconShare from '../assets/icons/IconShare.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconTrash from '../assets/icons/IconTrash.vue';

const route = useRoute();
const router = useRouter();
const uiStore = useUiStore();
const authStore = useAuthStore();
const dataStore = useDataStore();
const { emit } = useEventBus();
const titleIcon = markRaw(IconUserCircle);

const { isLocked } = useSettingsPolicy();
const ALLOW_USER_SKILLS_KEY = 'personality_skills_editable';
const ALLOW_USER_TOOLS_KEY = 'personality_tools_editable';
const hasGlobalAdminRights = computed(() => Boolean(authStore.user?.is_admin));
const allowUserSkills = computed(() => hasGlobalAdminRights.value || !isLocked(ALLOW_USER_SKILLS_KEY));
const allowUserTools = computed(() => hasGlobalAdminRights.value || !isLocked(ALLOW_USER_TOOLS_KEY));

const catalog = ref({ global: [], personal: [], shared: [] });
const activePreference = ref(null);
const isLoading = ref(true);
const loadError = ref(null);

const selectedHandbag = ref(null);
const isLoadingDetail = ref(false);
const detail = ref(null);
const activeTab = ref('SOUL');
const tabs = ['SOUL', 'Skills', 'Tools', 'Databases', 'Metadata'];

const soulBuffer = ref('');
const skillBuffer = ref('');
const toolBuffer = ref('');
const savedSoul = ref('');
const savedSkill = ref('');
const savedTool = ref('');

const activeSkillName = ref(null);
const isNewSkill = ref(false);
const activeToolName = ref(null);
const isNewTool = ref(false);
const newNameInput = ref('');
const isSavingContent = ref(false);

const metaForm = ref({
  display_name: '',
  description: '',
  author: '',
  category: '',
  icon_base64: null,
});

const aiPrompt = ref('');
const isGenerating = ref(false);
const showCopilot = ref(true);
const isGeneratingIcon = ref(false);
const isTtiAvailable = computed(() => Boolean((dataStore.availableTtiModels?.length || 0) > 0));

const showEditor = ref(false);
const editorHandbag = ref(null);
const showShareModal = ref(false);
const shareHandbagName = ref(null);
const shareOwner = ref(null);
const skillImportInput = ref(null);

const showLibraryPicker = ref(false);
const librarySkills = ref([]);
const isLoadingLibrary = ref(false);
const selectedLibrarySkill = ref(null);

const editorContent = computed({
  get() {
    if (activeTab.value === 'SOUL') return soulBuffer.value;
    if (activeTab.value === 'Skills') return skillBuffer.value;
    if (activeTab.value === 'Tools') return toolBuffer.value;
    return '';
  },
  set(value) {
    if (activeTab.value === 'SOUL') soulBuffer.value = value;
    else if (activeTab.value === 'Skills') skillBuffer.value = value;
    else if (activeTab.value === 'Tools') toolBuffer.value = value;
  },
});

const activeResource = computed(() => {
  if (activeTab.value === 'SOUL') {
    return {
      type: 'soul',
      label: 'Soul',
      content: soulBuffer.value,
      generateEndpoint: '/api/personalities/studio/generate_soul',
      hint: 'Define the personality, tone, expertise, and behavioral boundaries.',
    };
  }
  if (activeTab.value === 'Skills') {
    return {
      type: 'skill',
      label: 'Skill',
      content: skillBuffer.value,
      generateEndpoint: '/api/personalities/studio/generate_skill',
      hint: 'Create reusable Markdown instructions for a specific task or workflow.',
    };
  }
  if (activeTab.value === 'Tools') {
    return {
      type: 'tool',
      label: 'Tool',
      content: toolBuffer.value,
      generateEndpoint: '/api/personalities/studio/generate_tool',
      hint: 'Create or update a Python tool. Review generated code before saving.',
    };
  }
  return null;
});

const activeResourceActionLabel = computed(() => {
  const resource = activeResource.value;
  if (!resource) return 'No AI target';
  return resource.content.trim() ? `Update ${resource.label} with AI` : `Create ${resource.label} with AI`;
});

const canEdit = (item) => Boolean(item) && (
  item.scope === 'personal' || (item.scope === 'global' && hasGlobalAdminRights.value)
);

function canEditSkills(item) {
  return canEdit(item) && allowUserSkills.value;
}

function canEditTools(item) {
  return canEdit(item) && allowUserTools.value;
}

const canEditActiveResource = computed(() => {
  if (activeTab.value === 'SOUL') return canEdit(selectedHandbag.value);
  if (activeTab.value === 'Skills') return canEditSkills(selectedHandbag.value);
  if (activeTab.value === 'Tools') return canEditTools(selectedHandbag.value);
  return false;
});

const identityDirty = computed(() => {
  if (!detail.value) return false;
  return (
    (metaForm.value.display_name || '') !== (detail.value.name || '') ||
    (metaForm.value.description || '') !== (detail.value.description || '') ||
    (metaForm.value.author || '') !== (detail.value.author || '') ||
    (metaForm.value.category || '') !== (detail.value.category || '') ||
    (metaForm.value.icon_base64 || null) !== (detail.value.icon || null)
  );
});
const soulDirty = computed(() => soulBuffer.value !== savedSoul.value);
const skillDirty = computed(() => skillBuffer.value !== savedSkill.value || (isNewSkill.value && Boolean(newNameInput.value)));
const toolDirty = computed(() => toolBuffer.value !== savedTool.value || (isNewTool.value && Boolean(newNameInput.value)));
const hasUnsavedChanges = computed(() => identityDirty.value || soulDirty.value || skillDirty.value || toolDirty.value);

const allCatalogItems = computed(() => [
  ...catalog.value.personal,
  ...catalog.value.global,
  ...catalog.value.shared,
]);

const catalogSections = computed(() => {
  const query = catalogSearch.value.trim().toLowerCase();
  const scopes = catalogFilter.value === 'all'
    ? ['personal', 'global', 'shared']
    : [catalogFilter.value];
  const labels = { personal: 'My Personalities', global: 'Global', shared: 'Shared with Me' };
  return scopes.map((scope) => ({
    scope,
    label: labels[scope],
    items: catalog.value[scope].filter((item) => {
      if (!query) return true;
      return [item.name, item.handbag_name, item.description, item.author, item.category]
        .some((value) => String(value || '').toLowerCase().includes(query));
    }),
  })).filter((section) => section.items.length > 0);
});

const visibleCatalogCount = computed(() => catalogSections.value.reduce((total, section) => total + section.items.length, 0));

function itemKey(item) {
  if (!item) return '';
  return `${item.scope}:${item.owner_id ?? ''}:${item.handbag_name}`;
}

function isSameHandbag(left, right) {
  return Boolean(left && right) && itemKey(left) === itemKey(right);
}

function isActive(item) {
  if (!activePreference.value || !item) return false;
  return activePreference.value.scope === item.scope &&
    activePreference.value.handbag_name === item.handbag_name &&
    (item.scope !== 'shared' || (activePreference.value.owner_id ?? null) === (item.owner_id ?? null));
}

function describeError(error) {
  const detailValue = error?.response?.data?.detail;
  if (typeof detailValue === 'string' && detailValue) return detailValue;
  if (detailValue) return JSON.stringify(detailValue);
  return error?.message || null;
}

function initials(name) {
  const value = String(name || '?').trim();
  if (!value) return '?';
  return value.split(/\s+/).slice(0, 2).map((word) => word[0]).join('').toUpperCase();
}

function hashColor(value) {
  let hash = 0;
  const text = String(value || '');
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) >>> 0;
  }
  return `hsl(${hash % 360}, 65%, 45%)`;
}

function detailParams(item, extra = {}) {
  const params = { ...extra };
  if (item?.scope === 'shared' && item.owner_id != null) params.owner_id = item.owner_id;
  return params;
}

function confirmDiscardChanges() {
  return !hasUnsavedChanges.value || window.confirm('Discard unsaved changes and switch personality?');
}

function handbagQuery(item) {
  const query = { scope: item.scope, handbag: item.handbag_name };
  if (item.scope === 'shared' && item.owner_id != null) query.owner = String(item.owner_id);
  return query;
}

function itemFromRoute() {
  if (!route.query.handbag) return null;
  return allCatalogItems.value.find((item) =>
    item.scope === route.query.scope &&
    item.handbag_name === route.query.handbag &&
    (item.scope !== 'shared' || String(item.owner_id ?? '') === String(route.query.owner ?? ''))
  ) || null;
}

function notifyCatalogChanged() {
  window.dispatchEvent(new CustomEvent('lollms:personalities-changed'));
}

function itemFromSharedPreference() {
  const preference = dataStore.activePersonalityPreference;
  if (!preference?.handbag_name) return null;
  return allCatalogItems.value.find((item) =>
    item.handbag_name === preference.handbag_name &&
    (!preference.scope || item.scope === preference.scope) &&
    (preference.scope !== 'shared' || (preference.owner_id ?? null) === (item.owner_id ?? null))
  ) || null;
}

watch(
  () => dataStore.activePersonalityPreference,
  (preference) => {
    activePreference.value = preference || null;
    if (!preference?.handbag_name) return;
    const item = itemFromSharedPreference();
    if (item && !isSameHandbag(item, selectedHandbag.value)) fetchHandbagDetail(item);
  },
  { deep: true, immediate: true, flush: 'sync' }
);

async function fetchCatalog() {
  isLoading.value = true;
  loadError.value = null;
  const [catalogResult, preferenceResult] = await Promise.allSettled([
    apiClient.get('/api/personalities/catalog'),
    apiClient.get('/api/personalities/preference'),
  ]);

  if (catalogResult.status === 'fulfilled') {
    const raw = catalogResult.value?.data ?? {};
    catalog.value = {
      global: Array.isArray(raw.global) ? raw.global : [],
      personal: Array.isArray(raw.personal) ? raw.personal : [],
      shared: Array.isArray(raw.shared) ? raw.shared : [],
    };
  } else {
    loadError.value = describeError(catalogResult.reason) || 'Failed to load the personality catalog.';
  }

  activePreference.value = preferenceResult.status === 'fulfilled' ? (preferenceResult.value?.data ?? null) : null;
  if (activePreference.value) dataStore.setActivePersonalityPreference(activePreference.value);
  isLoading.value = false;

  const requested = itemFromRoute();
  if (requested) {
    selectedHandbag.value = requested;
    if (!detail.value || !isSameHandbag(requested, selectedHandbag.value)) {
      await fetchHandbagDetail(requested, { force: true });
    } else if (!detail.value) {
      await fetchHandbagDetail(requested, { force: true });
    }
    return;
  }

  if (selectedHandbag.value) {
    const refreshed = allCatalogItems.value.find((item) => isSameHandbag(item, selectedHandbag.value));
    if (refreshed) selectedHandbag.value = refreshed;
    return;
  }

  const target = allCatalogItems.value.find((item) => isActive(item)) ||
    catalog.value.personal[0] || catalog.value.global[0] || catalog.value.shared[0];
  if (target) {
    router.replace({ name: 'PersonalityStudio', query: handbagQuery(target) });
    await fetchHandbagDetail(target, { force: true });
  }
}

async function fetchHandbagDetail(item, { force = false } = {}) {
  if (!item || isLoadingDetail.value) return;
  if (isSameHandbag(item, selectedHandbag.value) && detail.value && !force) return;
  if (!force && !confirmDiscardChanges()) return;

  selectedHandbag.value = item;
  isLoadingDetail.value = true;
  detail.value = null;
  soulBuffer.value = '';
  skillBuffer.value = '';
  toolBuffer.value = '';
  savedSoul.value = '';
  savedSkill.value = '';
  savedTool.value = '';
  activeSkillName.value = null;
  isNewSkill.value = false;
  activeToolName.value = null;
  isNewTool.value = false;
  newNameInput.value = '';

  try {
    const response = await apiClient.get(
      `/api/personalities/studio/handbags/${item.scope}/${encodeURIComponent(item.handbag_name)}`,
      { params: detailParams(item) }
    );
    detail.value = response.data;
    activeTab.value = 'SOUL';
    soulBuffer.value = response.data.prompt_text || '';
    savedSoul.value = soulBuffer.value;
    metaForm.value = {
      display_name: response.data.name || '',
      description: response.data.description || '',
      author: response.data.author || '',
      category: response.data.category || '',
      icon_base64: response.data.icon || null,
    };
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Failed to load personality details.', 'error');
    selectedHandbag.value = null;
    detail.value = null;
  } finally {
    isLoadingDetail.value = false;
  }
}

async function refreshDetail() {
  if (!selectedHandbag.value) return;
  try {
    const response = await apiClient.get(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}`,
      { params: detailParams(selectedHandbag.value) }
    );
    detail.value = response.data;
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Failed to refresh details.', 'error');
  }
}

async function selectHandbag(item) {
  const payload = { scope: item.scope, handbag_name: item.handbag_name };
  if (item.scope === 'shared') payload.owner_id = item.owner_id ?? null;
  try {
    await apiClient.put('/api/personalities/preference', payload);
    activePreference.value = payload;
    dataStore.setActivePersonalityPreference(payload);
    emit('personality:changed', {
      ...payload,
      name: item.name || item.handbag_name,
      icon: item.icon || null,
    });
    uiStore.addNotification(`"${item.name}" is now your active personality.`, 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Failed to set the active personality.', 'error');
  }
}

function openCreateEditor() {
  editorHandbag.value = null;
  showEditor.value = true;
}

function closeEditor() {
  showEditor.value = false;
  editorHandbag.value = null;
  if (route.query.create) {
    const query = { ...route.query };
    delete query.create;
    router.replace({ query });
  }
}

async function handleEditorSaved() {
  closeEditor();
  await fetchCatalog();
  if (selectedHandbag.value) await refreshDetail();
}

function openShare(item) {
  shareHandbagName.value = item.handbag_name;
  shareOwner.value = item.owner;
  showShareModal.value = true;
}

async function exportHandbag(item) {
  if (!item) return;
  try {
    const response = await apiClient.get(
      `/api/personalities/studio/handbags/${item.scope}/${encodeURIComponent(item.handbag_name)}/export`,
      { params: detailParams(item), responseType: 'blob' }
    );
    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/zip' }));
    const link = document.createElement('a');
    link.href = url;
    let filename = `personality_${item.handbag_name}.zip`;
    const contentDisposition = response.headers?.['content-disposition'];
    const match = contentDisposition?.match(/filename="?([^"]+)"?/);
    if (match) filename = match[1];
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    uiStore.addNotification(`"${item.name}" exported.`, 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Export failed.', 'error');
  }
}

async function deleteHandbag(item) {
  if (!item || !window.confirm(`Delete personality "${item.name}"? This cannot be undone.`)) return;
  try {
    await apiClient.delete(
      `/api/personalities/studio/handbags/${item.scope}/${encodeURIComponent(item.handbag_name)}`
    );
    uiStore.addNotification(`"${item.name}" deleted.`, 'success');
    notifyCatalogChanged();
    if (isSameHandbag(selectedHandbag.value, item)) {
      selectedHandbag.value = null;
      detail.value = null;
      soulBuffer.value = '';
      skillBuffer.value = '';
      toolBuffer.value = '';
      savedSoul.value = '';
      savedSkill.value = '';
      savedTool.value = '';
    }
    await fetchCatalog();
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Delete failed.', 'error');
  }
}

async function handleUploadZip(event) {
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
    const installedName = response?.data?.handbag_name;
    uiStore.addNotification(installedName ? `Personality "${installedName}" imported.` : 'Personality imported.', 'success');
    await fetchCatalog();
    if (installedName) {
      const item = catalog.value.personal.find((handbag) => handbag.handbag_name === installedName);
      if (item) await fetchHandbagDetail(item, { force: true });
    }
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Import failed.', 'error');
  }
}

async function saveSoul() {
  if (!selectedHandbag.value || !canEdit(selectedHandbag.value)) return;
  isSavingContent.value = true;
  try {
    await apiClient.put(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}`,
      { prompt_text: soulBuffer.value }
    );
    savedSoul.value = soulBuffer.value;
    if (detail.value) detail.value.prompt_text = soulBuffer.value;
    uiStore.addNotification('Soul prompt saved.', 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Save failed.', 'error');
  } finally {
    isSavingContent.value = false;
  }
}

function handleIconUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => { metaForm.value.icon_base64 = reader.result; };
  reader.readAsDataURL(file);
}

async function saveMetadata() {
  if (!selectedHandbag.value || !canEdit(selectedHandbag.value)) return;
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
    await refreshDetail();
    await fetchCatalog();
    notifyCatalogChanged();
    if (isActive(selectedHandbag.value)) {
      const payload = {
        scope: selectedHandbag.value.scope,
        handbag_name: selectedHandbag.value.handbag_name,
        name: metaForm.value.display_name || selectedHandbag.value.name,
        icon: metaForm.value.icon_base64 || detail.value?.icon || null,
      };
      if (selectedHandbag.value.scope === 'shared') payload.owner_id = selectedHandbag.value.owner_id ?? null;
      emit('personality:changed', payload);
    }
    uiStore.addNotification('Personality details saved.', 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Save failed.', 'error');
  } finally {
    isSavingContent.value = false;
  }
}

async function generateIcon() {
  if (!isTtiAvailable.value || isGeneratingIcon.value || !canEdit(selectedHandbag.value)) return;
  isGeneratingIcon.value = true;
  try {
    const name = metaForm.value.display_name || 'AI Assistant';
    const category = metaForm.value.category || 'General';
    const description = metaForm.value.description || '';
    const prompt = `Profile icon/avatar of ${name}, ${category}. ${description}. High quality digital art, centered, portrait.`;
    const response = await apiClient.post('/api/personalities/generate_icon', { prompt });
    const icon = response?.data?.icon_base64;
    if (typeof icon !== 'string' || !icon) throw new Error('Icon endpoint returned an unexpected response.');
    metaForm.value.icon_base64 = icon;
    uiStore.addNotification('Icon generated. Review it and save Metadata to keep it.', 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Icon generation failed.', 'error');
  } finally {
    isGeneratingIcon.value = false;
  }
}

async function selectSkill(name) {
  if (name !== activeSkillName.value && skillDirty.value && !window.confirm('Discard unsaved skill changes?')) return;
  activeSkillName.value = name;
  isNewSkill.value = false;
  newNameInput.value = '';
  if (!name) {
    skillBuffer.value = '';
    savedSkill.value = '';
    return;
  }
  try {
    const response = await apiClient.get(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/skills/${encodeURIComponent(name)}`,
      { params: detailParams(selectedHandbag.value) }
    );
    skillBuffer.value = response.data.content;
    savedSkill.value = skillBuffer.value;
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Failed to load skill.', 'error');
  }
}

function startNewSkill() {
  if (!canEditSkills(selectedHandbag.value)) {
    uiStore.addNotification('Skill editing is disabled by your administrator.', 'warning');
    return;
  }
  if (skillDirty.value && !window.confirm('Discard unsaved skill changes?')) return;
  activeSkillName.value = null;
  isNewSkill.value = true;
  newNameInput.value = 'new_skill.md';
  skillBuffer.value = '';
  savedSkill.value = '';
}

async function deleteSkill(name) {
  if (!canEditSkills(selectedHandbag.value) || !name || !window.confirm(`Delete skill "${name}"?`)) return;
  try {
    await apiClient.delete(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/skills/${encodeURIComponent(name)}`
    );
    if (activeSkillName.value === name) {
      activeSkillName.value = null;
      skillBuffer.value = '';
      savedSkill.value = '';
    }
    await refreshDetail();
    uiStore.addNotification('Skill deleted.', 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Delete failed.', 'error');
  }
}

async function saveSkill() {
  const name = (isNewSkill.value ? newNameInput.value : activeSkillName.value)?.trim();
  if (!name || !canEditSkills(selectedHandbag.value)) {
    uiStore.addNotification('A skill filename is required.', 'warning');
    return;
  }
  isSavingContent.value = true;
  try {
    await apiClient.post(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/skills`,
      { name, content: skillBuffer.value }
    );
    activeSkillName.value = name;
    isNewSkill.value = false;
    newNameInput.value = '';
    savedSkill.value = skillBuffer.value;
    await refreshDetail();
    uiStore.addNotification('Skill saved.', 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Save failed.', 'error');
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
    uiStore.addNotification('Skill exported to your library.', 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Export failed.', 'error');
  }
}

async function openLibraryPicker() {
  if (!canEditSkills(selectedHandbag.value)) return;
  showLibraryPicker.value = true;
  selectedLibrarySkill.value = null;
  isLoadingLibrary.value = true;
  try {
    const response = await apiClient.get('/api/personalities/studio/skills-library');
    librarySkills.value = Array.isArray(response.data?.skills) ? response.data.skills : [];
  } catch (error) {
    librarySkills.value = [];
    uiStore.addNotification(describeError(error) || 'Could not load the skills library.', 'error');
  } finally {
    isLoadingLibrary.value = false;
  }
}

function parseSkillFrontmatterName(text) {
  if (typeof text !== 'string') return null;
  const stripped = text.replace(/^\uFEFF/, '').replace(/^\s+/, '');
  if (!stripped.startsWith('---')) return null;
  const end = stripped.indexOf('\n---', 3);
  if (end === -1) return null;
  for (const line of stripped.slice(3, end).split(/\r?\n/)) {
    const match = line.match(/^\s*name\s*:\s*(.+)$/i);
    if (match) {
      const value = match[1].trim().replace(/^['"]|['"]$/g, '');
      if (value) return value;
    }
  }
  return null;
}

async function handleSkillFileImport(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file || !selectedHandbag.value) return;
  if (!file.name.toLowerCase().endsWith('.md')) {
    uiStore.addNotification('Only Markdown (.md) skill files are allowed.', 'warning');
    return;
  }
  const text = await file.text().catch(() => '');
  let resolvedName = parseSkillFrontmatterName(text);
  if (!resolvedName) {
    const answer = window.prompt(
      'This skill has no "name:" in its YAML frontmatter. Enter a name for the skill:',
      file.name.replace(/\.md$/i, '')
    );
    if (answer === null) return;
    resolvedName = answer.trim();
    if (!resolvedName) {
      uiStore.addNotification('A skill name is required.', 'warning');
      return;
    }
  }
  const form = new FormData();
  form.append('file', file);
  try {
    await apiClient.post(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/skills/import`,
      form,
      { params: { name: resolvedName }, headers: { 'Content-Type': 'multipart/form-data' } }
    );
    await refreshDetail();
    await selectSkill(`${resolvedName}.md`);
    uiStore.addNotification(`Skill "${resolvedName}" imported.`, 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Import failed.', 'error');
  }
}

async function confirmImportFromLibrary() {
  const chosen = selectedLibrarySkill.value;
  if (!chosen || !selectedHandbag.value) return;
  const lookupName = chosen.source === 'db' ? chosen.name : (chosen.stem || chosen.name);
  try {
    await apiClient.post(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/skills/from-library`,
      { name: lookupName }
    );
    showLibraryPicker.value = false;
    await refreshDetail();
    uiStore.addNotification(`Skill "${chosen.name}" imported.`, 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Import failed.', 'error');
  }
}

async function selectTool(name) {
  if (name !== activeToolName.value && toolDirty.value && !window.confirm('Discard unsaved tool changes?')) return;
  activeToolName.value = name;
  isNewTool.value = false;
  newNameInput.value = '';
  if (!name) {
    toolBuffer.value = '';
    savedTool.value = '';
    return;
  }
  try {
    const response = await apiClient.get(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/tools/${encodeURIComponent(name)}`,
      { params: detailParams(selectedHandbag.value) }
    );
    toolBuffer.value = response.data.content;
    savedTool.value = toolBuffer.value;
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Failed to load tool.', 'error');
  }
}

function startNewTool() {
  if (!canEditTools(selectedHandbag.value)) {
    uiStore.addNotification('Tool editing is disabled by your administrator. Attach external MCPs instead.', 'warning');
    return;
  }
  if (toolDirty.value && !window.confirm('Discard unsaved tool changes?')) return;
  activeToolName.value = null;
  isNewTool.value = true;
  newNameInput.value = 'new_tool.py';
  toolBuffer.value = '';
  savedTool.value = '';
}

async function deleteTool(name) {
  if (!canEditTools(selectedHandbag.value) || !name || !window.confirm(`Delete tool "${name}"?`)) return;
  try {
    await apiClient.delete(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/tools/${encodeURIComponent(name)}`
    );
    if (activeToolName.value === name) {
      activeToolName.value = null;
      toolBuffer.value = '';
      savedTool.value = '';
    }
    await refreshDetail();
    uiStore.addNotification('Tool deleted.', 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Delete failed.', 'error');
  }
}

async function saveTool() {
  const name = (isNewTool.value ? newNameInput.value : activeToolName.value)?.trim();
  if (!name || !canEditTools(selectedHandbag.value)) {
    uiStore.addNotification('A tool filename is required.', 'warning');
    return;
  }
  isSavingContent.value = true;
  try {
    await apiClient.put(
      `/api/personalities/studio/handbags/${selectedHandbag.value.scope}/${encodeURIComponent(selectedHandbag.value.handbag_name)}/tools/${encodeURIComponent(name)}`,
      { content: toolBuffer.value }
    );
    activeToolName.value = name;
    isNewTool.value = false;
    newNameInput.value = '';
    savedTool.value = toolBuffer.value;
    await refreshDetail();
    uiStore.addNotification('Tool saved.', 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'Save failed.', 'error');
  } finally {
    isSavingContent.value = false;
  }
}

async function applyPromptToActiveResource() {
  const resource = activeResource.value;
  if (!resource || !aiPrompt.value.trim() || isGenerating.value || !canEditActiveResource.value) return;
  isGenerating.value = true;
  try {
    const payload = { prompt: aiPrompt.value };
    if (resource.content.trim()) payload.existing_content = resource.content;
    const response = await apiClient.post(resource.generateEndpoint, payload);
    const raw = response?.data;
    const content = typeof raw === 'string' ? raw : raw?.content;
    if (typeof content !== 'string' || !content) {
      throw new Error('The AI endpoint returned an unexpected response. Verify that a model is configured.');
    }
    if (resource.type === 'soul') {
      soulBuffer.value = content;
    } else if (resource.type === 'skill') {
      skillBuffer.value = content;
      if (!activeSkillName.value && !isNewSkill.value) {
        isNewSkill.value = true;
        newNameInput.value = 'ai_skill.md';
        savedSkill.value = '';
      }
    } else if (resource.type === 'tool') {
      toolBuffer.value = content;
      if (!activeToolName.value && !isNewTool.value) {
        isNewTool.value = true;
        newNameInput.value = 'ai_tool.py';
        savedTool.value = '';
      }
    }
    aiPrompt.value = '';
    uiStore.addNotification(`AI drafted the ${resource.label.toLowerCase()}. Review it, then save.`, 'success');
  } catch (error) {
    uiStore.addNotification(describeError(error) || 'AI generation failed.', 'error');
  } finally {
    isGenerating.value = false;
  }
}

watch(activeTab, (newTab) => {
  if (!detail.value) return;
  if (newTab === 'Skills' && !activeSkillName.value && !isNewSkill.value && !skillBuffer.value) {
    if (detail.value.skills?.length) selectSkill(detail.value.skills[0]);
    else if (canEditSkills(selectedHandbag.value)) startNewSkill();
  }
  if (newTab === 'Tools' && !activeToolName.value && !isNewTool.value && !toolBuffer.value) {
    if (detail.value.tools?.length) selectTool(detail.value.tools[0]);
    else if (canEditTools(selectedHandbag.value)) startNewTool();
  }
});

watch(
  () => [route.query.scope, route.query.handbag, route.query.owner],
  async () => {
    const item = itemFromRoute();
    if (item && (!isSameHandbag(item, selectedHandbag.value) || !detail.value)) {
      await fetchHandbagDetail(item, { force: true });
    }
  }
);

onMounted(() => {
  if (typeof authStore.fetchSettingsPolicy === 'function') authStore.fetchSettingsPolicy().catch(() => {});
  fetchCatalog().finally(() => {
    if (route.query.create === '1') openCreateEditor();
  });
});
</script>

<template>
  <PageViewLayout title="Personality Studio" :title-icon="titleIcon" :show-sidebar="false">
    <template #main>
      <div class="flex flex-col xl:flex-row h-full w-full overflow-hidden bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
        <aside v-if="false" class="hidden">
          <div class="p-4 border-b border-gray-200 dark:border-gray-800 space-y-3">
            <div class="flex items-center justify-between gap-2">
              <div>
                <h2 class="font-bold text-sm">Personality Library</h2>
                <p class="text-[11px] text-gray-500 mt-0.5">Choose a persona to inspect or customize.</p>
              </div>
              <button @click="fetchCatalog" class="btn btn-secondary btn-sm px-2" :disabled="isLoading" title="Refresh library">⟳</button>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <button @click="openCreateEditor" class="btn btn-primary btn-sm text-xs justify-center">
                <IconPlus class="w-3.5 h-3.5 mr-1" /> New
              </button>
              <button @click="uploadInput?.click()" class="btn btn-secondary btn-sm text-xs justify-center">Import ZIP</button>
              <input ref="uploadInput" type="file" accept=".zip,application/zip" class="hidden" @change="handleUploadZip" />
            </div>
            <input v-model="catalogSearch" type="search" class="input-field w-full text-sm" placeholder="Search personalities…" />
            <div class="flex gap-1 p-1 rounded-lg bg-gray-100 dark:bg-gray-800">
              <button
                v-for="filter in [{ value: 'all', label: 'All' }, { value: 'personal', label: 'Mine' }, { value: 'global', label: 'Global' }, { value: 'shared', label: 'Shared' }]"
                :key="filter.value"
                @click="catalogFilter = filter.value"
                class="flex-1 px-2 py-1 rounded-md text-[11px] font-semibold transition-colors"
                :class="catalogFilter === filter.value ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-300 shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'"
              >{{ filter.label }}</button>
            </div>
          </div>

          <div class="flex-1 overflow-y-auto p-2 min-h-0">
            <div v-if="isLoading" class="p-6 text-center text-sm text-gray-500">
              <IconAnimateSpin class="w-5 h-5 animate-spin mx-auto mb-2" /> Loading library…
            </div>
            <div v-else-if="loadError" class="m-2 p-3 rounded-lg bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 text-xs">
              <p class="font-semibold mb-1">Could not load personalities</p>
              <p>{{ loadError }}</p>
              <button @click="fetchCatalog" class="btn btn-secondary btn-sm mt-3">Try again</button>
            </div>
            <div v-else-if="visibleCatalogCount === 0" class="p-6 text-center">
              <IconUserCircle class="w-10 h-10 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
              <p class="text-sm font-medium text-gray-600 dark:text-gray-300">No personalities found</p>
              <p class="text-xs text-gray-500 mt-1">Clear your search or create a new personality.</p>
            </div>
            <div v-else class="space-y-4">
              <section v-for="section in catalogSections" :key="section.scope">
                <h3 class="px-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-gray-400">
                  {{ section.label }} <span class="font-normal">({{ section.items.length }})</span>
                </h3>
                <div class="space-y-1">
                  <button
                    v-for="item in section.items"
                    :key="itemKey(item)"
                    @click="fetchHandbagDetail(item)"
                    class="w-full flex items-center gap-3 p-2 rounded-xl text-left border transition-all"
                    :class="isSameHandbag(selectedHandbag, item)
                      ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-900 shadow-sm'
                      : 'border-transparent hover:bg-gray-100 dark:hover:bg-gray-800'"
                  >
                    <div class="relative w-9 h-9 rounded-lg shrink-0 overflow-hidden flex items-center justify-center text-white text-xs font-bold" :style="{ backgroundColor: hashColor(item.handbag_name) }">
                      <img v-if="item.icon" :src="item.icon" class="w-full h-full object-cover" :alt="`${item.name} icon`" />
                      <span v-else>{{ initials(item.name) }}</span>
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-1.5">
                        <span class="truncate text-sm font-semibold">{{ item.name }}</span>
                        <span v-if="isActive(item)" class="w-2 h-2 rounded-full bg-emerald-500 shrink-0" title="Active personality"></span>
                      </div>
                      <p class="text-[11px] text-gray-500 truncate">{{ item.description || item.category || item.handbag_name }}</p>
                    </div>
                  </button>
                </div>
              </section>
            </div>
          </div>
          <div class="px-4 py-2 border-t border-gray-200 dark:border-gray-800 text-[10px] text-gray-400 flex justify-between">
            <span>{{ visibleCatalogCount }} shown</span>
            <span class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Active</span>
          </div>
        </aside>

        <main class="flex-1 flex flex-col min-w-0 min-h-0 bg-white dark:bg-gray-900">
          <div v-if="selectedHandbag" class="shrink-0 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
            <div class="flex items-center gap-3">
              <div class="w-11 h-11 rounded-xl overflow-hidden shrink-0 flex items-center justify-center text-white font-bold" :style="{ backgroundColor: hashColor(selectedHandbag.handbag_name) }">
                <img v-if="metaForm.icon_base64 || selectedHandbag.icon" :src="metaForm.icon_base64 || selectedHandbag.icon" class="w-full h-full object-cover" :alt="`${selectedHandbag.name} icon`" />
                <span v-else>{{ initials(selectedHandbag.name) }}</span>
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 flex-wrap">
                  <h1 class="font-bold truncate">{{ detail?.name || selectedHandbag.name }}</h1>
                  <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500">{{ selectedHandbag.scope }}</span>
                  <span v-if="!canEdit(selectedHandbag)" class="text-[10px] font-semibold text-amber-600 dark:text-amber-400">Read only</span>
                </div>
                <p class="text-xs text-gray-500 truncate">{{ detail?.description || 'Configure how this personality thinks, works, and responds.' }}</p>
              </div>
              <div class="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">
                <span v-if="hasUnsavedChanges" class="hidden xl:inline text-[10px] font-semibold text-amber-600 dark:text-amber-400 mr-1">Unsaved changes</span>
                <button v-if="!isActive(selectedHandbag)" @click="selectHandbag(selectedHandbag)" class="btn btn-primary btn-sm text-xs">Set Active</button>
                <span v-else class="hidden sm:flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 font-bold px-2"><IconCheckCircle class="w-4 h-4" /> Active</span>
                <button @click="showCopilot = !showCopilot" class="btn btn-secondary btn-sm text-xs" :class="{ '!text-purple-600 dark:!text-purple-400': showCopilot }" title="Toggle AI Copilot">
                  <IconSparkles class="w-3.5 h-3.5 sm:mr-1" /><span class="hidden sm:inline">Copilot</span>
                </button>
                <button @click="exportHandbag(selectedHandbag)" class="btn btn-secondary btn-sm text-xs" title="Export personality">Export</button>
                <button v-if="selectedHandbag.scope === 'personal'" @click="openShare(selectedHandbag)" class="btn btn-secondary btn-sm text-xs" title="Share personality"><IconShare class="w-3.5 h-3.5" /></button>
                <button v-if="canEdit(selectedHandbag)" @click="deleteHandbag(selectedHandbag)" class="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg" title="Delete personality"><IconTrash class="w-4 h-4" /></button>
              </div>
            </div>
          </div>

          <div v-if="!selectedHandbag && !isLoadingDetail" class="flex-1 flex flex-col items-center justify-center text-center p-8 text-gray-400">
            <div class="w-20 h-20 rounded-3xl bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center mb-5">
              <IconUserCircle class="w-10 h-10 text-blue-400" />
            </div>
            <h2 class="text-xl font-bold text-gray-800 dark:text-gray-100">Build your ideal AI personality</h2>
            <p class="text-sm max-w-md mt-2">Select a personality from the library, or create one to define its soul, reusable skills, tools, and knowledge.</p>
            <button @click="openCreateEditor" class="btn btn-primary mt-5"><IconPlus class="w-4 h-4 mr-1" /> Create Personality</button>
          </div>
          <div v-else-if="isLoadingDetail" class="flex-1 flex items-center justify-center text-gray-500">
            <IconAnimateSpin class="w-5 h-5 animate-spin mr-2" /> Loading workspace…
          </div>

          <template v-else-if="detail">
            <div class="shrink-0 flex items-center justify-between gap-2 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/40 px-3">
              <nav class="flex gap-1 overflow-x-auto" aria-label="Personality sections">
                <button
                  v-for="tab in tabs"
                  :key="tab"
                  @click="activeTab = tab"
                  class="relative px-3 sm:px-4 py-3 text-xs sm:text-sm font-medium border-b-2 whitespace-nowrap transition-colors"
                  :class="activeTab === tab ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'"
                >
                  {{ tab }}
                  <span v-if="(tab === 'SOUL' && soulDirty) || (tab === 'Skills' && skillDirty) || (tab === 'Tools' && toolDirty) || (tab === 'Metadata' && identityDirty)" class="absolute top-2 right-1 w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                </button>
              </nav>
              <span class="hidden md:block text-[10px] text-gray-400 pr-2">{{ detail.skills?.length || 0 }} skills · {{ detail.tools?.length || 0 }} tools</span>
            </div>

            <div class="flex-1 flex min-h-0 relative">
              <section v-if="activeTab === 'SOUL'" class="flex-1 flex flex-col min-w-0">
                <div class="shrink-0 px-4 py-2 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between gap-3">
                  <div>
                    <h3 class="text-sm font-semibold">Soul prompt</h3>
                    <p class="text-[11px] text-gray-500">The core instructions that shape this personality’s behavior.</p>
                  </div>
                  <button @click="saveSoul" :disabled="isSavingContent || !canEdit(selectedHandbag) || !soulDirty" class="btn btn-primary btn-sm text-xs shrink-0">
                    <IconCheckCircle class="w-4 h-4 mr-1" /> {{ soulDirty ? 'Save Soul' : 'Saved' }}
                  </button>
                </div>
                <div class="flex-1 relative min-h-0">
                  <CodeMirrorEditor v-model="editorContent" language="markdown" class="absolute inset-0" :read-only="!canEdit(selectedHandbag)" />
                </div>
              </section>

              <section v-else-if="activeTab === 'Metadata'" class="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-950/40">
                <div class="max-w-3xl mx-auto p-5 sm:p-8 space-y-6">
                  <div>
                    <h3 class="text-lg font-bold">Personality details</h3>
                    <p class="text-sm text-gray-500 mt-1">These details appear in your library, chats, and shared catalog entries.</p>
                  </div>
                  <div class="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-5 sm:p-6 space-y-6 shadow-sm">
                    <div class="flex flex-col sm:flex-row items-start gap-6">
                      <div class="relative shrink-0">
                        <label class="block w-28 h-28 rounded-2xl overflow-hidden border-2 border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800" :class="canEdit(selectedHandbag) ? 'cursor-pointer' : 'cursor-not-allowed opacity-70'">
                          <img v-if="metaForm.icon_base64" :src="metaForm.icon_base64" class="w-full h-full object-cover" alt="Personality icon" />
                          <div v-else class="w-full h-full flex items-center justify-center text-3xl font-bold text-gray-400">{{ initials(metaForm.display_name) }}</div>
                          <input v-if="canEdit(selectedHandbag)" type="file" accept="image/*" class="hidden" @change="handleIconUpload" />
                        </label>
                        <button v-if="isTtiAvailable && canEdit(selectedHandbag)" @click.stop="generateIcon" :disabled="isGeneratingIcon" class="absolute -bottom-2 -right-2 w-9 h-9 rounded-full bg-purple-600 text-white flex items-center justify-center shadow-lg ring-2 ring-white dark:ring-gray-900 hover:bg-purple-700 disabled:opacity-60" title="Generate icon with AI">
                          <IconSparkles v-if="!isGeneratingIcon" class="w-4 h-4" />
                          <IconAnimateSpin v-else class="w-4 h-4 animate-spin" />
                        </button>
                      </div>
                      <div class="flex-1 w-full min-w-0 space-y-4">
                        <div>
                          <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Display name</label>
                          <input v-model="metaForm.display_name" type="text" class="input-field w-full text-lg font-semibold" :disabled="!canEdit(selectedHandbag)" placeholder="e.g. Research Assistant" />
                        </div>
                        <div>
                          <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Description</label>
                          <textarea v-model="metaForm.description" rows="3" class="input-field w-full text-sm resize-none" :disabled="!canEdit(selectedHandbag)" placeholder="What is this personality best at?"></textarea>
                        </div>
                      </div>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Author</label>
                        <input v-model="metaForm.author" type="text" class="input-field w-full text-sm" :disabled="!canEdit(selectedHandbag)" />
                      </div>
                      <div>
                        <label class="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">Category</label>
                        <input v-model="metaForm.category" type="text" class="input-field w-full text-sm" :disabled="!canEdit(selectedHandbag)" placeholder="e.g. Productivity" />
                      </div>
                    </div>
                    <div v-if="canEdit(selectedHandbag)" class="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-200 dark:border-gray-800">
                      <label class="btn btn-secondary btn-sm text-xs cursor-pointer mt-3">Upload Icon<input type="file" accept="image/*" class="hidden" @change="handleIconUpload" /></label>
                      <button v-if="isTtiAvailable" @click="generateIcon" :disabled="isGeneratingIcon" class="btn btn-secondary btn-sm text-xs mt-3"><IconSparkles class="w-3.5 h-3.5 mr-1" /> Generate with AI</button>
                    </div>
                  </div>
                  <div v-if="canEdit(selectedHandbag)" class="flex items-center gap-3">
                    <button @click="saveMetadata" :disabled="isSavingContent || !identityDirty" class="btn btn-primary"><IconCheckCircle class="w-4 h-4 mr-1" /> {{ identityDirty ? 'Save Details' : 'Details Saved' }}</button>
                    <span v-if="identityDirty" class="text-xs text-amber-600 dark:text-amber-400 font-semibold">You have unsaved changes</span>
                  </div>
                </div>
              </section>

              <template v-else-if="activeTab === 'Skills' || activeTab === 'Tools'">
                <div class="w-48 sm:w-56 shrink-0 border-r border-gray-200 dark:border-gray-800 flex flex-col bg-gray-50 dark:bg-gray-800/30 min-h-0">
                  <div class="p-3 border-b border-gray-200 dark:border-gray-800">
                    <div class="flex justify-between items-center gap-2">
                      <div>
                        <h3 class="text-xs font-bold uppercase tracking-wider text-gray-500">{{ activeTab }}</h3>
                        <p class="text-[10px] text-gray-400 mt-0.5">{{ activeTab === 'Skills' ? 'Reusable instructions' : 'Executable capabilities' }}</p>
                      </div>
                      <button v-if="activeTab === 'Skills' ? canEditSkills(selectedHandbag) : canEditTools(selectedHandbag)" @click="activeTab === 'Skills' ? startNewSkill() : startNewTool()" class="btn btn-secondary btn-sm px-2 text-xs"><IconPlus class="w-3.5 h-3.5" /> New</button>
                    </div>
                  </div>
                  <div class="flex-1 overflow-y-auto p-2 min-h-0">
                    <template v-if="activeTab === 'Skills'">
                      <div v-for="skill in (detail.skills || [])" :key="skill" @click="selectSkill(skill)" class="group px-3 py-2 text-sm cursor-pointer rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 flex items-center justify-between gap-1" :class="{ 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-medium': activeSkillName === skill && !isNewSkill }">
                        <span class="truncate">{{ skill }}</span>
                        <button v-if="canEditSkills(selectedHandbag)" @click.stop="deleteSkill(skill)" class="opacity-0 group-hover:opacity-100 p-0.5 text-gray-400 hover:text-red-500 shrink-0" title="Delete skill"><IconTrash class="w-3.5 h-3.5" /></button>
                      </div>
                      <p v-if="!detail.skills?.length" class="p-3 text-xs text-gray-400 italic">No skills attached yet.</p>
                    </template>
                    <template v-else>
                      <div v-for="tool in (detail.tools || [])" :key="tool" @click="selectTool(tool)" class="group px-3 py-2 text-sm cursor-pointer rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 flex items-center justify-between gap-1" :class="{ 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-medium': activeToolName === tool && !isNewTool }">
                        <span class="truncate">{{ tool }}</span>
                        <button v-if="canEditTools(selectedHandbag)" @click.stop="deleteTool(tool)" class="opacity-0 group-hover:opacity-100 p-0.5 text-gray-400 hover:text-red-500 shrink-0" title="Delete tool"><IconTrash class="w-3.5 h-3.5" /></button>
                      </div>
                      <p v-if="!detail.tools?.length" class="p-3 text-xs text-gray-400 italic">No tools attached yet.</p>
                    </template>
                  </div>
                  <div v-if="activeTab === 'Skills' && canEditSkills(selectedHandbag)" class="p-2 border-t border-gray-200 dark:border-gray-800 space-y-1.5">
                    <button @click="skillImportInput?.click()" class="btn btn-secondary btn-sm w-full text-xs">Import SKILL.md</button>
                    <input ref="skillImportInput" type="file" accept=".md,text/markdown" class="hidden" @change="handleSkillFileImport" />
                    <button @click="openLibraryPicker" class="btn btn-secondary btn-sm w-full text-xs">Browse Library</button>
                  </div>
                  <div v-if="activeTab === 'Tools' && !allowUserTools" class="p-3 border-t border-gray-200 dark:border-gray-800 text-[10px] text-amber-600 dark:text-amber-400">Tool editing is disabled by your administrator. Use external MCP servers instead.</div>
                </div>

                <section class="flex-1 flex flex-col min-w-0 min-h-0">
                  <div class="shrink-0 p-2 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between gap-2">
                    <div class="flex items-center gap-2 min-w-0">
                      <span class="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">{{ (activeTab === 'Skills' ? isNewSkill : isNewTool) ? `New ${activeTab.slice(0, -1)}` : (activeTab === 'Skills' ? activeSkillName : activeToolName) || `Select a ${activeTab.slice(0, -1).toLowerCase()}` }}</span>
                      <input v-if="(activeTab === 'Skills' ? isNewSkill : isNewTool)" v-model="newNameInput" :placeholder="activeTab === 'Skills' ? 'skill.md' : 'tool.py'" class="input-field text-xs px-2 py-1 h-7 w-36" />
                    </div>
                    <div class="flex items-center gap-2 shrink-0">
                      <button v-if="activeTab === 'Skills' && !isNewSkill && activeSkillName && canEditSkills(selectedHandbag)" @click="exportSkillToLibrary" class="btn btn-secondary btn-sm text-xs hidden sm:inline-flex">Export to Library</button>
                      <button @click="activeTab === 'Skills' ? saveSkill() : saveTool()" :disabled="isSavingContent || !(activeTab === 'Skills' ? skillDirty : toolDirty) || (activeTab === 'Skills' ? !canEditSkills(selectedHandbag) : !canEditTools(selectedHandbag))" class="btn btn-primary btn-sm text-xs"><IconCheckCircle class="w-4 h-4 mr-1" /> {{ (activeTab === 'Skills' ? skillDirty : toolDirty) ? 'Save' : 'Saved' }}</button>
                    </div>
                  </div>
                  <div class="flex-1 relative min-h-0">
                    <CodeMirrorEditor v-model="editorContent" :language="activeTab === 'Tools' ? 'python' : 'markdown'" class="absolute inset-0" :read-only="activeTab === 'Skills' ? !canEditSkills(selectedHandbag) : !canEditTools(selectedHandbag)" />
                  </div>
                </section>
              </template>

              <section v-else-if="activeTab === 'Databases'" class="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-950/40">
                <div class="max-w-3xl mx-auto p-5 sm:p-8">
                  <div class="mb-6">
                    <h3 class="text-lg font-bold">Knowledge databases</h3>
                    <p class="text-sm text-gray-500 mt-1">Retrieval-augmented knowledge available to this personality during conversations.</p>
                  </div>
                  <div v-if="detail.databases?.length" class="grid gap-3 sm:grid-cols-2">
                    <div v-for="database in detail.databases" :key="database" class="p-4 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 flex items-center gap-3 shadow-sm">
                      <div class="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-950/40 flex items-center justify-center"><IconDataZone class="w-5 h-5 text-blue-500" /></div>
                      <div class="min-w-0"><p class="font-mono text-sm truncate">{{ database }}</p><p class="text-[11px] text-gray-500">Attached knowledge source</p></div>
                    </div>
                  </div>
                  <div v-else class="p-8 text-center rounded-2xl border border-dashed border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900">
                    <IconDataZone class="w-10 h-10 mx-auto text-gray-300 dark:text-gray-600 mb-3" />
                    <h4 class="font-semibold text-sm">No databases attached</h4>
                    <p class="text-xs text-gray-500 mt-1 max-w-sm mx-auto">This personality will rely on its soul, skills, and tools without additional retrieval knowledge.</p>
                  </div>
                  <div v-if="!allowUserTools" class="mt-6 p-4 rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20">
                    <p class="text-sm font-semibold text-amber-800 dark:text-amber-200 mb-1">In-persona code tools are restricted</p>
                    <p class="text-xs text-amber-700 dark:text-amber-300">You can still extend this personality with external MCP servers configured in MCP settings.</p>
                  </div>
                </div>
              </section>
            </div>
          </template>
        </main>

        <aside v-if="showCopilot" class="w-full xl:w-80 shrink-0 flex flex-col border-t xl:border-t-0 xl:border-l border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 max-h-96 xl:max-h-none">
          <div class="p-4 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex items-center justify-between">
            <div>
              <h3 class="font-bold text-sm text-gray-800 dark:text-gray-200 flex items-center gap-2"><IconSparkles class="w-4 h-4 text-purple-500" /> LoLLMs Copilot</h3>
              <p class="text-[11px] text-gray-500 mt-0.5">Draft and refine the open resource.</p>
            </div>
            <button @click="showCopilot = false" class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 xl:hidden">✕</button>
          </div>
          <div class="p-4 space-y-4 flex-1 overflow-y-auto">
            <div class="p-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800/50">
              <div class="flex items-center justify-between gap-2">
                <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Current target</span>
                <span v-if="activeResource" class="px-2 py-0.5 rounded-full bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 text-[10px] font-bold">{{ activeResource.label }}</span>
              </div>
              <p class="text-xs text-gray-500 mt-2 leading-relaxed">{{ activeResource?.hint || 'Open Soul, Skills, or Tools to generate content with AI. Metadata and databases are not AI editor targets.' }}</p>
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5">What should the AI do?</label>
              <textarea v-model="aiPrompt" rows="5" class="input-field w-full text-sm resize-none" :placeholder="activeResource ? 'e.g. Make the tone concise and add a verification checklist…' : 'Open an editable content tab first.'" :disabled="!activeResource || !canEditActiveResource"></textarea>
            </div>
            <button @click="applyPromptToActiveResource" :disabled="!aiPrompt.trim() || isGenerating || !activeResource || !canEditActiveResource" class="btn btn-primary w-full text-sm justify-center">
              <IconSparkles v-if="!isGenerating" class="w-4 h-4 mr-2" /><IconAnimateSpin v-else class="w-4 h-4 mr-2 animate-spin" />
              {{ isGenerating ? 'Generating…' : activeResourceActionLabel }}
            </button>
            <p v-if="activeResource && !canEditActiveResource" class="text-xs text-amber-600 dark:text-amber-400">This resource is read-only or restricted by administrator policy.</p>
            <div class="text-[11px] text-gray-500 leading-relaxed border-t border-gray-200 dark:border-gray-800 pt-3">
              Existing content is sent as context. The draft replaces the editor buffer only; nothing is persisted until you click <strong>Save</strong>.
            </div>
          </div>
        </aside>
      </div>

      <PersonalityEditorModal v-if="showEditor" :personality="editorHandbag" @close="closeEditor" @saved="handleEditorSaved" />

      <Teleport to="body">
        <div v-if="showLibraryPicker" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="showLibraryPicker = false">
          <div class="w-full max-w-md bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
            <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
              <div><h3 class="text-sm font-semibold">Import Skill from Library</h3><p class="text-[11px] text-gray-500 mt-0.5">Add a reusable skill to {{ selectedHandbag?.name }}.</p></div>
              <button @click="showLibraryPicker = false" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">✕</button>
            </div>
            <div class="flex-1 overflow-y-auto p-2">
              <div v-if="isLoadingLibrary" class="p-6 text-center text-xs text-gray-500"><IconAnimateSpin class="w-4 h-4 animate-spin mx-auto mb-2" />Loading skills…</div>
              <div v-else-if="!librarySkills.length" class="p-6 text-center text-xs text-gray-500 italic">No skills are available in your library.</div>
              <div v-else class="space-y-1">
                <button v-for="skill in librarySkills" :key="`${skill.source || 'file'}:${skill.name}`" @click="selectedLibrarySkill = skill" class="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-start justify-between gap-2" :class="selectedLibrarySkill?.name === skill.name && selectedLibrarySkill?.source === skill.source ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-medium' : 'hover:bg-gray-100 dark:hover:bg-gray-700'">
                  <span class="min-w-0 flex flex-col"><span class="truncate font-mono">{{ skill.name }}</span><span v-if="skill.description" class="text-[10px] text-gray-500 truncate">{{ skill.description }}</span></span>
                  <span class="flex items-center gap-1 shrink-0"><span class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded" :class="skill.source === 'db' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300'">{{ skill.source === 'db' ? 'DB' : 'FILE' }}</span><IconCheckCircle v-if="selectedLibrarySkill?.name === skill.name && selectedLibrarySkill?.source === skill.source" class="w-4 h-4" /></span>
                </button>
              </div>
            </div>
            <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2"><button class="btn btn-secondary btn-sm text-xs" @click="showLibraryPicker = false">Cancel</button><button class="btn btn-primary btn-sm text-xs" :disabled="!selectedLibrarySkill" @click="confirmImportFromLibrary">Import Skill</button></div>
          </div>
        </div>
      </Teleport>

      <SharePersonalityModal v-if="showShareModal" :handbag-name="shareHandbagName" :owner="shareOwner" @close="showShareModal = false" @shared="fetchCatalog" />
    </template>
  </PageViewLayout>
</template>
