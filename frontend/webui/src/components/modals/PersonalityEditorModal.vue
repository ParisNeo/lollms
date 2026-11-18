<script setup>
import { ref, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import apiClient from '@/services/api';
import { useUiStore } from '@/stores/ui';
import { useAuthStore } from '@/stores/auth';
import { useDataStore } from '@/stores/data';
import { useTasksStore } from '@/stores/tasks';
import IconSparkles from '@/assets/icons/IconSparkles.vue';
import IconAnimateSpin from '@/assets/icons/IconAnimateSpin.vue';

const props = defineProps({
  personality: { type: Object, default: null }
});
const emit = defineEmits(['close', 'saved']);

const uiStore = useUiStore();
const authStore = useAuthStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();
const { tasks } = storeToRefs(tasksStore);

// Resolve the personality either from an explicit prop (inline view usage)
// or from the store when opened via openModal('personalityEditor', { personality }).
const effectivePersonality = computed(
  () => props.personality || uiStore.modalData('personalityEditor')?.personality || null
);

const isEditing = computed(() => Boolean(effectivePersonality.value?.handbag_name));

const form = ref({
  name: '',
  display_name: '',
  description: '',
  author: '',
  category: '',
  prompt_text: '',
  icon_base64: null,
  scope: 'personal',
});

watch(effectivePersonality, (p) => {
  if (p) {
    form.value = {
      name: p.handbag_name || '',
      display_name: p.name || p.display_name || '',
      description: p.description || '',
      author: p.author || '',
      category: p.category || '',
      prompt_text: p.prompt_text || '',
      icon_base64: p.icon || null,
      scope: p.scope || 'personal',
    };
  } else {
    form.value = {
      name: '', display_name: '', description: '', author: '',
      category: '', prompt_text: '', icon_base64: null, scope: 'personal',
    };
  }
}, { immediate: true });

const isLoading = ref(false);

// --- Auto-generate from prompt ---
const genPrompt = ref('');
const isGenerating = ref(false);
const genTaskId = ref(null);

const genTask = computed(() =>
  genTaskId.value ? tasks.value.find(t => t.id === genTaskId.value) : null
);
const genBusy = computed(() =>
  isGenerating.value ||
  (genTask.value && ['pending', 'running'].includes(genTask.value.status))
);

function describeError(e) {
  const detail = e?.response?.data?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (detail) return JSON.stringify(detail);
  if (e?.message) return e.message;
  return null;
}

function slugify(value) {
  return String(value || '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

// The backend expects bare base64, while FileReader yields a data URL.
// Keep data URLs for <img> preview, but strip the prefix at the request boundary.
function stripDataUrl(value) {
  if (typeof value !== 'string' || !value) return value ?? null;
  const comma = value.indexOf(',');
  return value.startsWith('data:') && comma !== -1 ? value.slice(comma + 1) : value;
}

// --- Auto-generate icon (text-to-image) ---
const ttiAvailable = computed(() => (dataStore.availableTtiModels?.length || 0) > 0);
const isGeneratingIcon = ref(false);
const iconGenerateError = ref(null);

function buildIconPrompt() {
  const fromName = form.value.display_name || form.value.name || form.value.description;
  if (fromName && fromName.trim()) return fromName.trim();
  return form.value.prompt_text ? form.value.prompt_text.slice(0, 200) : '';
}

async function autoGenerateIcon() {
  if (!ttiAvailable.value) {
    uiStore.addNotification('No text-to-image model is configured.', 'warning');
    return;
  }
  const basePrompt = buildIconPrompt();
  if (!basePrompt) {
    uiStore.addNotification('Add a name or description first so the icon matches the persona.', 'warning');
    return;
  }

  isGeneratingIcon.value = true;
  iconGenerateError.value = null;
  try {
    const res = await apiClient.post('/api/personalities/generate_icon', { prompt: basePrompt });
    const b64 = res?.data?.icon_base64;
    if (b64) {
      form.value.icon_base64 = b64;
      uiStore.addNotification('Icon generated.', 'success');
    } else {
      iconGenerateError.value = 'Icon generation returned no image.';
      uiStore.addNotification(iconGenerateError.value, 'error');
    }
  } catch (e) {
    const msg = describeError(e) || 'Icon generation failed.';
    iconGenerateError.value = msg;
    uiStore.addNotification(msg, 'error');
  } finally {
    isGeneratingIcon.value = false;
  }
}

function onFileChange(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file) return;
  if (!file.type.startsWith('image/')) {
    uiStore.addNotification('Please select an image file.', 'warning');
    return;
  }
  const reader = new FileReader();
  reader.onload = () => { form.value.icon_base64 = reader.result; };
  reader.readAsDataURL(file);
}

// Single close path: emit for parent wiring AND defensively close the store
// modal when this component was mounted via the store-driven container.
function close() {
  emit('close');
  if (uiStore.isModalOpen('personalityEditor')) {
    uiStore.closeModal('personalityEditor');
  }
}

async function autoGenerate() {
  if (!genPrompt.value.trim()) {
    uiStore.addNotification('Please describe the personality to generate.', 'warning');
    return;
  }

  isGenerating.value = true;
  genTaskId.value = null;

  try {
    const res = await dataStore.generatePersonalityFromPrompt(genPrompt.value);
    genTaskId.value = res.id;
  } catch (error) {
    isGenerating.value = false;
    // error is handled by the axios interceptor
  }
}

watch(genTask, (t) => {
  if (!t) return;

  if (t.status === 'completed') {
    let resultData = t.result;
    if (typeof resultData === 'string') {
      try {
        resultData = JSON.parse(resultData);
      } catch (e) {
        resultData = null;
      }
    }
    if (!resultData || typeof resultData !== 'object') {
      uiStore.addNotification('Personality generation returned malformed data.', 'error');
      isGenerating.value = false;
      return;
    }

    // The generation endpoint returns a full personality payload. Map every
    // editable field — critically including the handbag slug (`name`), which
    // is otherwise left empty and blocks the required-field submit check.
    const resolvedSlug =
      resultData.handbag_name ||
      resultData.slug ||
      slugify(resultData.display_name || resultData.name) ||
      form.value.name;
    if (resolvedSlug) form.value.name = resolvedSlug;

    form.value.display_name = resultData.display_name || resultData.name || form.value.display_name;
    form.value.description = resultData.description || form.value.description;
    form.value.author = resultData.author || form.value.author;
    form.value.category = resultData.category || form.value.category;
    form.value.prompt_text = resultData.prompt_text || resultData.soul || form.value.prompt_text;

    const generatedIcon = resultData.icon_base64 || resultData.icon;
    if (generatedIcon) form.value.icon_base64 = generatedIcon;

    uiStore.addNotification('Personality draft generated — review and save.', 'success');
    isGenerating.value = false;
  } else if (t.status === 'failed' || t.status === 'cancelled') {
    uiStore.addNotification(`Generation failed: ${t.error || 'Unknown error'}`, 'error');
    isGenerating.value = false;
  }
});

async function submit() {
  if (!isEditing.value && !form.value.name.trim()) {
    uiStore.addNotification('Name is required for a new personality.', 'warning');
    return;
  }
  isLoading.value = true;
  try {
    let savedRes;
    if (isEditing.value) {
      savedRes = await apiClient.put(
        `/api/personalities/studio/handbags/${form.value.scope}/${encodeURIComponent(form.value.name)}`,
        {
          display_name: form.value.display_name,
          description: form.value.description,
          author: form.value.author,
          category: form.value.category,
          prompt_text: form.value.prompt_text,
          icon_base64: stripDataUrl(form.value.icon_base64),
        }
      );
    } else {
      savedRes = await apiClient.post('/api/personalities/studio/handbags', {
        name: form.value.name,
        display_name: form.value.display_name || form.value.name,
        description: form.value.description,
        author: form.value.author,
        category: form.value.category,
        prompt_text: form.value.prompt_text,
        icon_base64: stripDataUrl(form.value.icon_base64),
        scope: form.value.scope,
      });
    }

    const saved = savedRes?.data ?? null;
    uiStore.addNotification(isEditing.value ? 'Personality updated.' : 'Personality created.', 'success');

    // Best-effort list refresh so the studio view and the store-driven mount
    // both reflect the change even if the parent's @saved handler does not refetch.
    try {
      await (dataStore.fetchPersonalities?.() || dataStore.fetchUserPersonalities?.());
    } catch {
      // refetch is non-critical; do not block success UX
    }

    emit('saved', saved);
    emit('close');
    if (uiStore.isModalOpen('personalityEditor')) {
      uiStore.closeModal('personalityEditor');
    }
  } catch (e) {
    const status = e?.response?.status;
    if (status === 409) {
      uiStore.addNotification('A personality with this slug already exists. Change the Name (Slug) and try again.', 'error');
    } else if (status === 422) {
      uiStore.addNotification(describeError(e) || 'Some fields were rejected by the server.', 'error');
    } else {
      uiStore.addNotification(describeError(e) || 'Save failed.', 'error');
    }
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="close">
      <div class="w-full max-w-2xl bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-100">
            {{ isEditing ? 'Edit Personality' : 'Create Personality' }}
          </h3>
          <button @click="close" class="p-1 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto p-6 space-y-4">
          <!-- Auto-generate from prompt -->
          <div class="rounded-lg border border-purple-200 dark:border-purple-900/60 bg-purple-50/60 dark:bg-purple-900/10 p-3 space-y-2">
            <label class="flex items-center gap-2 text-sm font-medium text-purple-700 dark:text-purple-300">
              <IconSparkles class="w-4 h-4" />
              Auto-generate from prompt
            </label>
            <textarea
              v-model="genPrompt"
              rows="3"
              class="input-field w-full bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500 resize-none"
              placeholder="Describe the AI personality to generate…"
              :disabled="genBusy"
            ></textarea>
            <div class="flex items-center gap-3">
              <button
                type="button"
                class="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md bg-purple-600 text-white hover:bg-purple-700 transition-colors disabled:opacity-50"
                :disabled="genBusy"
                @click="autoGenerate"
              >
                <IconAnimateSpin v-if="genBusy" class="w-4 h-4 mr-1.5 animate-spin" />
                <IconSparkles v-else class="w-4 h-4 mr-1.5" />
                {{ genBusy ? 'Generating…' : 'Generate' }}
              </button>
              <div v-if="genTask && genBusy" class="flex-1 min-w-0">
                <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                  <span class="truncate">Drafting personality…</span>
                  <span>{{ genTask.progress ?? 0 }}%</span>
                </div>
                <div class="h-1.5 w-full bg-gray-200 dark:bg-gray-700 rounded overflow-hidden">
                  <div class="h-full bg-purple-500 transition-all" :style="{ width: `${genTask.progress ?? 0}%` }"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Name (disabled on edit) -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Name (Slug)</label>
            <input
              v-model="form.name"
              :disabled="isEditing"
              type="text"
              class="input-field mt-1 w-full disabled:opacity-60 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500"
              placeholder="e.g. research_assistant"
            >
            <p v-if="isEditing" class="text-xs text-gray-500 mt-1">Handbag identifier cannot be changed once created.</p>
          </div>

          <!-- Display name -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Display Name</label>
            <input v-model="form.display_name" type="text" class="input-field mt-1 w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500" placeholder="e.g. Research Assistant">
          </div>

          <!-- Category + Author -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Category</label>
              <input v-model="form.category" type="text" class="input-field mt-1 w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Author</label>
              <input v-model="form.author" type="text" class="input-field mt-1 w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500">
            </div>
          </div>

          <!-- Scope (admin only, create only) -->
          <div v-if="!isEditing && authStore.user?.is_admin">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Scope</label>
            <select v-model="form.scope" class="input-field mt-1 w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500">
              <option value="personal">Personal</option>
              <option value="global">Global (all users)</option>
            </select>
          </div>

          <!-- Description -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Description</label>
            <textarea v-model="form.description" rows="2" class="input-field mt-1 w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500"></textarea>
          </div>

          <!-- Prompt / SOUL -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">System Prompt (SOUL.md)</label>
            <textarea v-model="form.prompt_text" rows="8" class="input-field mt-1 w-full font-mono text-sm bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-gray-900 dark:text-gray-100 focus:ring-blue-500 focus:border-blue-500" placeholder="You are..."></textarea>
          </div>

          <!-- Icon -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Icon</label>
            <div class="flex items-center gap-3 mt-1">
              <img v-if="form.icon_base64" :src="form.icon_base64" class="w-16 h-16 rounded-lg object-cover border border-gray-200 dark:border-gray-700">
              <div v-else class="w-16 h-16 rounded-lg bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-xs text-gray-500 border border-gray-300 dark:border-gray-600">None</div>
              <input type="file" accept="image/*" @change="onFileChange" class="text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/30 dark:file:text-blue-300">
            </div>
            <div v-if="ttiAvailable" class="mt-2 flex items-center gap-2">
              <button
                type="button"
                class="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md bg-purple-600 text-white hover:bg-purple-700 transition-colors disabled:opacity-50"
                :disabled="isGeneratingIcon"
                @click="autoGenerateIcon"
              >
                <IconAnimateSpin v-if="isGeneratingIcon" class="w-4 h-4 mr-1.5 animate-spin" />
                <IconSparkles v-else class="w-4 h-4 mr-1.5" />
                {{ isGeneratingIcon ? 'Generating…' : (form.icon_base64 ? 'Regenerate with AI' : 'Generate with AI') }}
              </button>
              <p v-if="!form.icon_base64" class="text-xs text-gray-500 dark:text-gray-400">
                Auto-generate an icon from the persona's name/description using your configured text-to-image model.
              </p>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2 bg-gray-50 dark:bg-gray-900/50">
          <button type="button" class="px-4 py-2 text-sm font-medium rounded-md bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors" @click="close" :disabled="isLoading">Cancel</button>
          <button type="button" class="px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50" @click="submit" :disabled="isLoading">
            {{ isLoading ? 'Saving…' : (isEditing ? 'Save Changes' : 'Create Personality') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>