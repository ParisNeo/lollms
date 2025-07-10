<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';

const adminStore = useAdminStore();

const form = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const renderedSettingsByCategory = computed(() => {
    const allSettings = adminStore.globalSettings;
    const settingsToRender = allSettings.filter(setting => 
        setting.category !== 'Email Settings' && setting.key !== 'password_recovery_mode'
    );
    
    return settingsToRender.reduce((acc, setting) => {
        const category = setting.category || 'General';
        if (!acc[category]) {
            acc[category] = [];
        }
        acc[category].push(setting);
        return acc;
    }, {});
});

onMounted(() => {
    if (adminStore.globalSettings.length === 0) {
        adminStore.fetchGlobalSettings();
    } else {
        populateForm();
    }
});

watch(() => adminStore.globalSettings, populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

function populateForm() {
    const newFormState = {};
    if (adminStore.globalSettings.length > 0) {
        adminStore.globalSettings.forEach(setting => {
            newFormState[setting.key] = setting.value;
        });
        form.value = newFormState;
        pristineState = JSON.parse(JSON.stringify(newFormState));
        hasChanges.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        const settingsInThisComponent = Object.values(renderedSettingsByCategory.value).flat().map(s => s.key);
        const payload = {};
        for(const key of settingsInThisComponent) {
            if(form.value.hasOwnProperty(key)) {
                payload[key] = form.value[key];
            }
        }
        await adminStore.updateGlobalSettings(payload);
    } catch (error) {
        // Error is handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                Global System Settings
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Manage application-wide settings. Changes may require users to log out and back in.
            </p>
        </div>
        <form v-if="Object.keys(renderedSettingsByCategory).length" @submit.prevent="handleSave" class="p-6">
            <div class="space-y-10">
                <div v-for="(settings, category) in renderedSettingsByCategory" :key="category">
                    <h4 class="text-lg font-medium text-gray-800 dark:text-gray-200 border-b border-gray-200 dark:border-gray-600 pb-2 mb-4">{{ category }}</h4>
                    <div class="space-y-6">
                        <div v-for="setting in settings" :key="setting.key">
                            <label :for="setting.key" class="block text-sm font-medium text-gray-700 dark:text-gray-300">{{ setting.description }}</label>
                            
                            <input v-if="['string', 'integer'].includes(setting.type)"
                                :type="setting.type === 'integer' ? 'number' : 'text'"
                                :id="setting.key"
                                v-model="form[setting.key]"
                                class="input-field mt-1">

                            <div v-if="setting.type === 'boolean'" class="mt-2">
                                <button @click="form[setting.key] = !form[setting.key]" type="button" :class="[form[setting.key] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                                    <span :class="[form[setting.key] ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                            
                            <textarea v-if="setting.type === 'json'"
                                :id="setting.key"
                                v-model="form[setting.key]"
                                rows="4"
                                class="input-field mt-1 font-mono text-xs"></textarea>
                        </div>
                    </div>
                </div>
            </div>

            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                        {{ isLoading ? 'Saving...' : 'Save Global Settings' }}
                    </button>
                </div>
            </div>
        </form>
        <div v-else-if="adminStore.isLoadingSettings" class="p-6 text-center">
            <p class="text-gray-500">Loading settings...</p>
        </div>
        <div v-else class="p-6 text-center">
            <p class="text-gray-500">Could not load global settings.</p>
        </div>
    </div>
</template>