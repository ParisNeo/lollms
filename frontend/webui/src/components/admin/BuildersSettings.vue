<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const settings = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const builderSettings = computed(() => {
  return adminStore.globalSettings
    .filter(s => s.category === 'Builders')
    .sort((a, b) => a.key.localeCompare(b.key));
});

function populateForm() {
    if (builderSettings.value.length > 0) {
        const settingsObject = {};
        builderSettings.value.forEach(setting => {
            // Ensure boolean values are actual booleans, even if they arrive as strings
            if (setting.type === 'boolean') {
                settingsObject[setting.key] = parseAsBoolean(setting.value);
            } else {
                settingsObject[setting.key] = setting.value;
            }
        });
        settings.value = settingsObject;
        pristineState = JSON.stringify(settings.value);
        hasChanges.value = false;
    }
}

// Defensive boolean parsing
function parseAsBoolean(value) {
    if (typeof value === 'boolean') return value;
    if (typeof value === 'string') return value.toLowerCase() === 'true';
    return !!value;
}

onMounted(() => {
  if (adminStore.globalSettings.length === 0) {
    adminStore.fetchGlobalSettings();
  } else {
    populateForm();
  }
});

watch(() => adminStore.globalSettings, populateForm, { deep: true });

watch(settings, (newSettings) => {
    hasChanges.value = JSON.stringify(newSettings) !== pristineState;
}, { deep: true });

async function saveSettings() {
    isLoading.value = true;
    const settingsToSave = {};
    for (const key in settings.value) {
        if (builderSettings.value.some(s => s.key === key)) {
            settingsToSave[key] = settings.value[key];
        }
    }
  try {
    await adminStore.updateGlobalSettings(settingsToSave);
  } finally {
    isLoading.value = false;
  }
}
</script>
<template>
  <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
    <div class="p-6 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
            Builders & Export Settings
        </h3>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Configure executables for code compilation and enable/disable message export formats.
        </p>
    </div>
    
    <div v-if="adminStore.isLoadingSettings" class="p-6 text-center">Loading settings...</div>
    
    <form v-else @submit.prevent="saveSettings" class="p-6">
      <div v-if="builderSettings.length === 0" class="text-center text-gray-500">
        No builder settings found.
      </div>
      <div v-else class="space-y-4">
        <div v-for="setting in builderSettings" :key="setting.key" 
             class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <span class="flex-grow flex flex-col pr-4">
              <span class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ setting.description || setting.key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) }}</span>
          </span>

          <template v-if="setting.type === 'boolean'">
            <button @click="settings[setting.key] = !settings[setting.key]" type="button" 
                    :class="[parseAsBoolean(settings[setting.key]) ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
              <span :class="[parseAsBoolean(settings[setting.key]) ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
            </button>
          </template>
          <template v-else>
            <input :type="setting.type === 'string' || setting.type === 'text' ? 'text' : 'number'" 
                   :id="setting.key" 
                   v-model="settings[setting.key]" 
                   class="input-field w-full sm:max-w-xs">
          </template>
        </div>
      </div>
      <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
        <div class="flex justify-end">
            <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                {{ isLoading ? 'Saving...' : 'Save Changes' }}
            </button>
        </div>
      </div>
    </form>
  </div>
</template>
