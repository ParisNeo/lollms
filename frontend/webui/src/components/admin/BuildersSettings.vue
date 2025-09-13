<script setup>
import { ref, computed, onMounted } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const settings = ref({});

const builderSettings = computed(() => {
  return adminStore.globalSettings.filter(s => s.category === 'Builders');
});

onMounted(async () => {
  await adminStore.fetchGlobalSettings();
  const settingsObject = {};
  adminStore.globalSettings.forEach(setting => {
    settingsObject[setting.key] = setting.value;
  });
  settings.value = settingsObject;
});

async function saveSettings() {
    const settingsToSave = {};
    for (const key in settings.value) {
        if (builderSettings.value.some(s => s.key === key)) {
            settingsToSave[key] = settings.value[key];
        }
    }
  await adminStore.updateGlobalSettings(settingsToSave);
}
</script>
<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-semibold">Code Builders</h2>
      <p class="text-gray-500 mt-1">Configure executables for compiling code blocks within discussions.</p>
    </div>

    <div v-if="adminStore.isLoadingSettings" class="text-center">Loading settings...</div>
    
    <div v-else class="space-y-6 bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm">
      <div v-if="builderSettings.length === 0" class="text-center text-gray-500">
        No builder settings found. This might happen if the database migration hasn't run yet.
      </div>
      <div v-for="setting in builderSettings" :key="setting.key" class="border-b dark:border-gray-700 pb-4 last:border-b-0 last:pb-0">
        <label :for="setting.key" class="block text-md font-medium text-gray-800 dark:text-gray-100">{{ setting.key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) }}</label>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-2">{{ setting.description }}</p>
        <template v-if="setting.type === 'boolean'">
          <label class="relative inline-flex items-center cursor-pointer mt-1">
            <input type="checkbox" v-model="settings[setting.key]" class="sr-only peer">
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
          </label>
        </template>
        <template v-else-if="setting.type === 'string' || setting.type === 'integer' || setting.type === 'float'">
          <input :type="setting.type === 'string' ? 'text' : 'number'" :id="setting.key" v-model="settings[setting.key]" class="input-field w-full sm:max-w-md">
        </template>
      </div>
    </div>

    <div class="flex justify-end pt-4">
      <button @click="saveSettings" class="btn btn-primary">Save Changes</button>
    </div>
  </div>
</template>