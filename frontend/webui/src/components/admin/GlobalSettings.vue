<!-- [UPDATE] frontend/webui/src/components/admin/GlobalSettings.vue -->
<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import JsonRenderer from '../ui/JsonRenderer.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const form = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

// State to track which JSON fields are in edit mode
const jsonEditStates = ref({});

const renderedSettingsByCategory = computed(() => {
    const allSettings = adminStore.globalSettings;
    const settingsToRender = allSettings.filter(setting => 
        setting.category !== 'Email Settings' && 
        setting.category !== 'Server' &&
        setting.category !== 'Registration' &&
        setting.category !== 'Defaults' &&
        setting.key !== 'password_recovery_mode'
    );
    
    const categoryOrder = [
        'Authentication',
        'Global LLM Overrides'
    ];

    const grouped = settingsToRender.reduce((acc, setting) => {
        const category = setting.category || 'General';
        if (!acc[category]) {
            acc[category] = [];
        }
        acc[category].push(setting);
        return acc;
    }, {});

    // Sort categories according to the defined order
    const sortedGrouped = {};
    categoryOrder.forEach(cat => {
        if (grouped[cat]) {
            sortedGrouped[cat] = grouped[cat];
        }
    });
    // Add any other categories not in the order list at the end
    Object.keys(grouped).forEach(cat => {
        if (!categoryOrder.includes(cat)) {
            sortedGrouped[cat] = grouped[cat];
        }
    });

    return sortedGrouped;
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
            if (setting.type === 'json') {
                try {
                    // Make it pretty for the textarea
                    newFormState[setting.key] = JSON.stringify(setting.value, null, 2);
                } catch {
                    newFormState[setting.key] = setting.value;
                }
                 // Initialize edit state to false (view mode)
                jsonEditStates.value[setting.key] = false;
            } else {
                newFormState[setting.key] = setting.value;
            }
        });
        form.value = newFormState;
        pristineState = JSON.parse(JSON.stringify(newFormState));
        hasChanges.value = false;
    }
}

// Method to safely parse JSON from the form string for the renderer
function getParsedJson(key) {
    try {
        return JSON.parse(form.value[key]);
    } catch (e) {
        return { "error": "Invalid JSON format in text editor", "details": e.message };
    }
}

// Toggle edit mode for a specific JSON setting
function toggleJsonEdit(key) {
    jsonEditStates.value[key] = !jsonEditStates.value[key];
}

async function handleSave() {
    isLoading.value = true;
    const settingsInThisComponent = Object.values(renderedSettingsByCategory.value).flat();
    const payload = {};
    let hasJsonError = false;

    for(const setting of settingsInThisComponent) {
        const key = setting.key;
        if(form.value.hasOwnProperty(key)) {
            if (setting.type === 'json') {
                try {
                    // Validate and add to payload
                    payload[key] = JSON.parse(form.value[key]);
                } catch (e) {
                    uiStore.addNotification(`Invalid JSON format for '${setting.description}'. Please fix it before saving.`, 'error');
                    hasJsonError = true;
                }
            } else {
                payload[key] = form.value[key];
            }
        }
    }
    
    if(hasJsonError) {
        isLoading.value = false;
        return; // Stop the save process if any JSON is invalid
    }

    try {
        await adminStore.updateGlobalSettings(payload);
        // Turn off edit mode for all JSON fields after successful save
        Object.keys(jsonEditStates.value).forEach(key => jsonEditStates.value[key] = false);
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
                Application Settings
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Manage miscellaneous application-wide settings.
            </p>
        </div>
        <form v-if="Object.keys(renderedSettingsByCategory).length" @submit.prevent="handleSave" class="p-6">
            <div class="space-y-10">
                <div v-for="(settings, category) in renderedSettingsByCategory" :key="category">
                    <h4 class="text-lg font-medium text-gray-800 dark:text-gray-200 border-b border-gray-200 dark:border-gray-600 pb-2 mb-6">{{ category }}</h4>
                    <div class="space-y-8">
                        <div v-for="setting in settings" :key="setting.key">
                            
                            <!-- Special Case: force_model_mode -->
                            <div v-if="setting.key.includes('force_') && setting.key.includes('_mode')">
                                <label :for="setting.key" class="block text-sm font-medium text-gray-700 dark:text-gray-300">{{ setting.description }}</label>
                                <select :id="setting.key" v-model="form[setting.key]" class="input-field mt-1">
                                    <option value="disabled">Disabled</option>
                                    <option value="force_once">Force Once (set user preference)</option>
                                    <option value="force_always">Force Always (override session)</option>
                                </select>
                            </div>

                            <!-- Generic Input for string, integer, and float -->
                            <div v-else-if="['string', 'integer', 'float'].includes(setting.type)">
                                <label :for="setting.key" class="block text-sm font-medium text-gray-700 dark:text-gray-300">{{ setting.description }}</label>
                                <input
                                    :type="setting.type === 'string' ? 'text' : 'number'"
                                    :step="setting.type === 'float' ? '0.1' : '1'"
                                    :id="setting.key"
                                    v-model="form[setting.key]"
                                    class="input-field mt-1">
                            </div>

                            <!-- Boolean Toggle -->
                            <div v-else-if="setting.type === 'boolean'">
                                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">{{ setting.description }}</label>
                                <div class="mt-2">
                                    <button @click="form[setting.key] = !form[setting.key]" type="button" :class="[form[setting.key] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                                        <span :class="[form[setting.key] ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                    </button>
                                </div>
                            </div>
                            
                            <!-- JSON Renderer/Editor -->
                            <div v-else-if="setting.type === 'json'">
                                <div class="flex justify-between items-center mb-1">
                                    <label :for="setting.key" class="block text-sm font-medium text-gray-700 dark:text-gray-300">{{ setting.description }}</label>
                                    <button @click="toggleJsonEdit(setting.key)" type="button" class="btn btn-secondary btn-xs">
                                        {{ jsonEditStates[setting.key] ? 'View Rendered' : 'Edit Raw' }}
                                    </button>
                                </div>
                                
                                <div v-if="jsonEditStates[setting.key]">
                                    <textarea
                                        :id="setting.key"
                                        v-model="form[setting.key]"
                                        rows="8"
                                        class="input-field w-full font-mono text-xs !leading-relaxed"
                                        placeholder="Enter valid JSON here..."></textarea>
                                </div>
                                <div v-else class="mt-2 p-4 rounded-md bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700">
                                    <JsonRenderer :json="getParsedJson(setting.key)" />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                        {{ isLoading ? 'Saving...' : 'Save Settings' }}
                    </button>
                </div>
            </div>
        </form>
        <div v-else-if="adminStore.isLoadingSettings" class="p-6 text-center">
            <p class="text-gray-500">Loading settings...</p>
        </div>
        <div v-else class="p-6 text-center">
            <p class="text-gray-500">No application settings available.</p>
        </div>
    </div>
</template>