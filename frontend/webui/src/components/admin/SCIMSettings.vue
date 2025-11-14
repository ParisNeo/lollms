<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import IconCopy from '../../assets/icons/IconCopy.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const settings = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const scimBaseUrl = computed(() => {
    const origin = window.location.origin;
    return `${origin}/api/scim/v2`;
});

const scimSettings = computed(() => {
  return adminStore.globalSettings
    .filter(s => s.category === 'SCIM Provisioning')
    .sort((a, b) => a.key.localeCompare(b.key));
});

function populateForm() {
    if (scimSettings.value.length > 0) {
        const settingsObject = {};
        scimSettings.value.forEach(setting => {
            settingsObject[setting.key] = setting.value;
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
    try {
        await adminStore.updateGlobalSettings({ ...settings.value });
    } finally {
        isLoading.value = false;
    }
}
</script>
<template>
  <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
    <div class="p-6 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
            SCIM Provisioning
        </h3>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Configure automated user and group provisioning from an external Identity Provider (IdP).
        </p>
    </div>
    
    <div v-if="adminStore.isLoadingSettings" class="p-6 text-center">Loading settings...</div>
    
    <form v-else @submit.prevent="saveSettings" class="p-6 space-y-6">
      <div v-if="scimSettings.length === 0" class="text-center text-gray-500">
        Could not load SCIM settings.
      </div>
      <div v-else class="space-y-6">
        <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <span class="flex-grow flex flex-col pr-4">
                <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Enable SCIM</span>
                <span class="text-xs text-gray-500 dark:text-gray-400">Allow an external IdP to manage users and groups in lollms.</span>
            </span>
            <button @click="settings.scim_enabled = !settings.scim_enabled" type="button" 
                    :class="[parseAsBoolean(settings.scim_enabled) ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                <span :class="[parseAsBoolean(settings.scim_enabled) ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
            </button>
        </div>
        
        <div v-if="settings.scim_enabled" class="space-y-4">
            <div>
                <label class="block text-sm font-medium">SCIM Tenant URL</label>
                <div class="mt-1 flex rounded-md shadow-sm">
                    <input type="text" :value="scimBaseUrl" readonly class="input-field rounded-r-none flex-grow">
                    <button @click.prevent="uiStore.copyToClipboard(scimBaseUrl)" type="button" class="relative -ml-px inline-flex items-center space-x-2 rounded-r-md border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600">
                        <IconCopy class="h-5 w-5" />
                        <span>Copy</span>
                    </button>
                </div>
            </div>
            <div>
                <label class="block text-sm font-medium">SCIM Secret Token</label>
                <div class="mt-1 flex rounded-md shadow-sm">
                    <input type="password" :value="settings.scim_token || 'A token will be generated on save'" readonly class="input-field rounded-r-none flex-grow">
                     <button @click.prevent="uiStore.copyToClipboard(settings.scim_token)" type="button" class="relative -ml-px inline-flex items-center space-x-2 rounded-r-md border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600" :disabled="!settings.scim_token">
                        <IconCopy class="h-5 w-5" />
                        <span>Copy</span>
                    </button>
                </div>
                <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    If this field is empty, a secure token will be generated when you click save. Provide this token to your IdP.
                </p>
            </div>
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
