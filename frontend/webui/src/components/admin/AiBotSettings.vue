<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useDataStore } from '../../stores/data';
import { storeToRefs } from 'pinia';

const adminStore = useAdminStore();
const dataStore = useDataStore();

const { globalSettings, aiBotSettings, isLoadingAiBotSettings } = storeToRefs(adminStore);
const { availableLollmsModels, publicPersonalities } = storeToRefs(dataStore);

const form = ref({
    ai_bot_enabled: false,
    ai_bot_system_prompt: '',
    lollms_model_name: '',
    active_personality_id: ''
});

const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const botGlobalSettings = computed(() => {
    return globalSettings.value.filter(s => s.category === 'AI Bot');
});

const availablePersonalitiesForSelect = computed(() => {
    return publicPersonalities.value.map(p => ({
        id: p.id,
        name: `${p.name} (by ${p.author})`
    }));
});

onMounted(() => {
    if (globalSettings.value.length === 0) adminStore.fetchGlobalSettings();
    if (!aiBotSettings.value) adminStore.fetchAiBotSettings();
    if (availableLollmsModels.value.length === 0) dataStore.fetchAdminAvailableLollmsModels();
    if (publicPersonalities.value.length === 0) dataStore.fetchPersonalities();
});

watch([globalSettings, aiBotSettings], populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

function populateForm() {
    const newFormState = { ...form.value };
    
    if (botGlobalSettings.value.length > 0) {
        botGlobalSettings.value.forEach(setting => {
            newFormState[setting.key] = setting.value;
        });
    }

    if (aiBotSettings.value) {
        newFormState.lollms_model_name = aiBotSettings.value.lollms_model_name;
        newFormState.active_personality_id = aiBotSettings.value.active_personality_id;
    }
    
    form.value = newFormState;
    pristineState = JSON.stringify(form.value);
    hasChanges.value = false;
}

async function handleSave() {
    isLoading.value = true;
    try {
        const globalPayload = {
            ai_bot_enabled: form.value.ai_bot_enabled,
            ai_bot_system_prompt: form.value.ai_bot_system_prompt,
        };
        
        const botUserPayload = {
            lollms_model_name: form.value.lollms_model_name,
            active_personality_id: form.value.active_personality_id
        };

        await Promise.all([
            adminStore.updateGlobalSettings(globalPayload),
            adminStore.updateAiBotSettings(botUserPayload)
        ]);

    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                AI Bot Settings
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Configure the automated AI assistant that responds to @lollms mentions and performs system tasks like RSS processing.
            </p>
        </div>
        <div v-if="isLoadingAiBotSettings" class="p-6 text-center">Loading settings...</div>
        <form v-else-if="Object.keys(form).length" @submit.prevent="handleSave" class="p-6">
            <div class="space-y-8">
                <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <span class="flex-grow flex flex-col">
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Enable AI Bot</span>
                        <span class="text-sm text-gray-500 dark:text-gray-400">Allow the bot to reply to @lollms mentions.</span>
                    </span>
                    <button @click="form.ai_bot_enabled = !form.ai_bot_enabled" type="button" :class="[form.ai_bot_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.ai_bot_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                    </button>
                </div>

                <div class="space-y-6 pt-6 border-t dark:border-gray-600">
                    <div>
                        <label for="bot-model" class="block text-sm font-medium">Bot Model</label>
                        <select id="bot-model" v-model="form.lollms_model_name" class="input-field mt-1">
                            <option value="">-- Select a Model --</option>
                            <option v-for="model in availableLollmsModels" :key="model.id" :value="model.id">{{ model.name }}</option>
                        </select>
                        <p class="mt-1 text-xs text-gray-500">The model the bot will use for all system-level generations.</p>
                    </div>
                    <div>
                        <label for="bot-personality" class="block text-sm font-medium">Bot Personality</label>
                        <select id="bot-personality" v-model="form.active_personality_id" class="input-field mt-1">
                            <option value="">-- Use Default System Prompt --</option>
                            <option v-for="p in availablePersonalitiesForSelect" :key="p.id" :value="p.id">{{ p.name }}</option>
                        </select>
                         <p class="mt-1 text-xs text-gray-500">Select a personality to define the bot's behavior.</p>
                    </div>
                    <div v-if="!form.active_personality_id">
                        <label for="bot-prompt" class="block text-sm font-medium">Default System Prompt</label>
                        <textarea id="bot-prompt" v-model="form.ai_bot_system_prompt" rows="6" class="input-field mt-1"></textarea>
                        <p class="mt-1 text-xs text-gray-500">The system prompt used if no personality is selected.</p>
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
         <div v-else class="p-6 text-center">
            <p class="text-gray-500">
                {{ adminStore.isLoadingSettings ? 'Loading settings...' : 'Could not load AI Bot settings.' }}
            </p>
        </div>
    </div>
</template>