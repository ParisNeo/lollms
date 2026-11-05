<script setup>
import { ref, computed, watch } from 'vue';
import apiClient from '@/services/api';
import { useUiStore } from '@/stores/ui';
import { useAuthStore } from '@/stores/auth';

const props = defineProps({
  personality: { type: Object, default: null }
});
const emit = defineEmits(['close', 'saved']);

const uiStore = useUiStore();
const authStore = useAuthStore();

const isEditing = computed(() => Boolean(props.personality?.handbag_name));

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

watch(() => props.personality, (p) => {
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

function describeError(e) {
  const detail = e?.response?.data?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (detail) return JSON.stringify(detail);
  if (e?.message) return e.message;
  return null;
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

async function submit() {
  if (!isEditing.value && !form.value.name.trim()) {
    uiStore.addNotification('Name is required for a new personality.', 'warning');
    return;
  }
  isLoading.value = true;
  try {
    if (isEditing.value) {
      await apiClient.put(
        `/api/personalities/studio/handbags/${form.value.scope}/${encodeURIComponent(form.value.name)}`,
        {
          display_name: form.value.display_name,
          description: form.value.description,
          author: form.value.author,
          category: form.value.category,
          prompt_text: form.value.prompt_text,
          icon_base64: form.value.icon_base64,
        }
      );
    } else {
      await apiClient.post('/api/personalities/studio/handbags', {
        name: form.value.name,
        display_name: form.value.display_name || form.value.name,
        description: form.value.description,
        author: form.value.author,
        category: form.value.category,
        prompt_text: form.value.prompt_text,
        icon_base64: form.value.icon_base64,
        scope: form.value.scope,
      });
    }
    uiStore.addNotification(isEditing.value ? 'Personality updated.' : 'Personality created.', 'success');
    emit('saved');
    emit('close');
  } catch (e) {
    uiStore.addNotification(describeError(e) || 'Save failed.', 'error');
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="emit('close')">
      <div class="w-full max-w-2xl bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-100">
            {{ isEditing ? 'Edit Personality' : 'Create Personality' }}
          </h3>
          <button @click="emit('close')" class="p-1 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto p-6 space-y-4">
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
          </div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2 bg-gray-50 dark:bg-gray-900/50">
          <button type="button" class="px-4 py-2 text-sm font-medium rounded-md bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors" @click="emit('close')" :disabled="isLoading">Cancel</button>
          <button type="button" class="px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50" @click="submit" :disabled="isLoading">
            {{ isLoading ? 'Saving…' : (isEditing ? 'Save Changes' : 'Create Personality') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>