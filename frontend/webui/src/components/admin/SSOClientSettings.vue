<!-- [CREATE] frontend/webui/src/components/admin/SSOClientSettings.vue -->
<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const settings = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const ssoClientSettings = computed(() => {
  return adminStore.globalSettings
    .filter(s => s.category === 'SSO Client')
    .sort((a, b) => a.key.localeCompare(b.key));
});

function populateForm() {
    if (ssoClientSettings.value.length > 0) {
        const settingsObject = {};
        ssoClientSettings.value.forEach(setting => {
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
        if (ssoClientSettings.value.some(s => s.key === key)) {
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
            SSO Client Settings (OIDC)
        </h3>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Configure lollms to use an external OpenID Connect provider for user authentication.
        </p>
    </div>
    
    <div v-if="adminStore.isLoadingSettings" class="p-6 text-center">Loading settings...</div>
    
    <form v-else @submit.prevent="saveSettings" class="p-6 space-y-6">
      <div v-if="ssoClientSettings.length === 0" class="text-center text-gray-500">
        Could not load SSO settings.
      </div>
      <div v-else class="space-y-6">
        <div v-for="setting in ssoClientSettings" :key="setting.key">
            <template v-if="setting.type === 'boolean'">
                <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <span class="flex-grow flex flex-col pr-4">
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ setting.description || setting.key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) }}</span>
                    </span>
                    <button @click="settings[setting.key] = !settings[setting.key]" type="button" 
                            :class="[parseAsBoolean(settings[setting.key]) ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                        <span :class="[parseAsBoolean(settings[setting.key]) ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                    </button>
                </div>
            </template>
            <template v-else>
                <div>
                    <label :for="setting.key" class="block text-sm font-medium">{{ setting.description || setting.key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) }}</label>
                    <input :type="setting.key.includes('secret') ? 'password' : 'text'" 
                           :id="setting.key" 
                           v-model="settings[setting.key]" 
                           class="input-field mt-1 w-full"
                           :placeholder="setting.key.includes('secret') ? '********' : ''"
                           autocomplete="off">
                </div>
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
