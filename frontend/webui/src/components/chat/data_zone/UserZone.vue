<script setup>
import { computed, ref, watch, nextTick } from 'vue';
import { useAuthStore } from '../../../stores/auth';
import { storeToRefs } from 'pinia';
import IconSave from '../../../assets/icons/IconSave.vue';

const authStore = useAuthStore();
const { user } = storeToRefs(authStore);

// Local state for form fields, initialized from the store
const generalInfo = ref('');
const codingStyle = ref('');
const langPrefs = ref('');
const tellOS = ref(false);

const hasChanges = ref(false);

// Function to update local state from the store
function updateLocalState() {
  if (user.value) {
    generalInfo.value = user.value.data_zone || '';
    codingStyle.value = user.value.coding_style_constraints || '';
    langPrefs.value = user.value.programming_language_preferences || '';
    tellOS.value = user.value.tell_llm_os || false;
    // Use nextTick to ensure the DOM is updated before resetting hasChanges
    nextTick(() => {
        hasChanges.value = false;
    });
  }
}

// Watch for changes in the user object (e.g., after login or refresh)
watch(user, updateLocalState, { immediate: true, deep: true });

// Watch for changes in local form fields to enable the save button
watch([generalInfo, codingStyle, langPrefs, tellOS], () => {
  hasChanges.value = true;
});

const staticInfo = [
  { label: 'Date', placeholder: '{{date}}' },
  { label: 'Time', placeholder: '{{time}}' },
  { label: 'Date & Time', placeholder: '{{datetime}}' },
  { label: 'Username', placeholder: '{{user_name}}' },
];

async function handleSaveChanges() {
    if (!hasChanges.value) return;
    await authStore.updateUserPreferences({
        data_zone: generalInfo.value,
        coding_style_constraints: codingStyle.value,
        programming_language_preferences: langPrefs.value,
        tell_llm_os: tellOS.value
    });
    hasChanges.value = false; // Disable button after save
}
</script>

<template>
  <div class="flex-1 flex flex-col min-h-0">
    <div class="flex-shrink-0 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
        <span class="text-sm font-medium text-gray-600 dark:text-gray-300">Global User Context</span>
        <button @click="handleSaveChanges" class="btn btn-secondary btn-sm" :disabled="!hasChanges">
            <IconSave class="w-4 h-4 mr-1.5" />
            {{ hasChanges ? 'Save Changes' : 'Saved' }}
        </button>
    </div>
    <div class="flex-grow min-h-0 p-3 overflow-y-auto custom-scrollbar space-y-6">
      
        <!-- Static Info Section -->
        <div class="p-4 bg-gray-50 dark:bg-gray-800/50 border dark:border-gray-700 rounded-lg">
            <h3 class="text-sm font-semibold mb-3 text-gray-700 dark:text-gray-200">Dynamic Information</h3>
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">The AI will automatically know the following information. You can use these placeholders in your prompts.</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <div v-for="info in staticInfo" :key="info.label" class="flex justify-between items-center">
                    <span class="text-gray-800 dark:text-gray-200">{{ info.label }}:</span>
                    <code class="px-2 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">{{ info.placeholder }}</code>
                </div>
            </div>
        </div>

        <!-- OS Toggle -->
        <div class="p-3 bg-gray-50 dark:bg-gray-800/50 border dark:border-gray-700 rounded-lg flex items-center justify-between">
            <div class="flex-grow">
                <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Operating System</h3>
                <p class="text-xs text-gray-500 dark:text-gray-400">Inform the AI about your current operating system.</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="tellOS" class="sr-only peer">
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
            </label>
        </div>

        <!-- Text Areas for Preferences -->
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">Coding Style Constraints</label>
                <textarea v-model="codingStyle" class="styled-textarea" placeholder="e.g., Always follow PEP8 for Python code. Use pathlib instead of os.path."></textarea>
            </div>
            <div>
                <label class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">Programming Language & Library Preferences</label>
                <textarea v-model="langPrefs" class="styled-textarea" placeholder="e.g., I prefer solutions in Python 3.10+. For web development, use Vue.js with Tailwind CSS."></textarea>
            </div>
            <div>
                <label class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">General Info / Notes</label>
                <textarea v-model="generalInfo" class="styled-textarea" placeholder="Add any other information about yourself or general instructions for the AI."></textarea>
            </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.styled-textarea {
    @apply w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 focus:ring-blue-500 focus:border-blue-500 transition text-sm min-h-[100px] resize-y;
}
</style>