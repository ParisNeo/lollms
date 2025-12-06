<!-- [UPDATE] frontend/webui/src/components/admin/AiBotSettings.vue -->
<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import { storeToRefs } from 'pinia';
import MultiSelectMenu from '../ui/MultiSelectMenu.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const adminStore = useAdminStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

const { globalSettings, aiBotSettings, isLoadingAiBotSettings, adminAvailableLollmsModels, isLoadingLollmsModels } = storeToRefs(adminStore);
const { publicPersonalities, userDataStores } = storeToRefs(dataStore);

const form = ref({
    ai_bot_enabled: false,
    ai_bot_system_prompt: '',
    lollms_model_name: '',
    active_personality_id: '',
    // Auto-posting settings
    ai_bot_auto_post: false,
    ai_bot_post_interval: 24, // hours
    ai_bot_content_mode: 'static_text', // static_text, file, rag
    ai_bot_static_content: '',
    ai_bot_file_path: '',
    ai_bot_generation_prompt: 'Generate an interesting and engaging social media post based on the provided context. Keep it under 500 characters.',
    ai_bot_rag_datastore_ids: [],
    // Moderation
    ai_bot_moderation_enabled: false,
    ai_bot_moderation_criteria: ''
});

const isLoading = ref(false);
const isTriggering = ref(false);
const isModerating = ref(false); 
const isFullRemoderating = ref(false); 
const hasChanges = ref(false);
let pristineState = '{}';

const availablePersonalitiesForSelect = computed(() => {
    // FIX: Added defensive check (publicPersonalities.value || [])
    return (publicPersonalities.value || []).map(p => ({
        id: p.id,
        name: `${p.name} (by ${p.author})`
    }));
});

const availableDataStores = computed(() => {
    // FIX: Added defensive check (userDataStores.value || []) to prevent map on undefined
    return (userDataStores.value || []).map(ds => ({
        id: ds.id,
        name: ds.name
    }));
});

// Group models by binding name for better display
const groupedModels = computed(() => {
    const groups = {};
    if (!adminAvailableLollmsModels.value) return {};
    
    adminAvailableLollmsModels.value.forEach(model => {
        let binding = 'Aliases'; 
        let name = model.name;
        
        if (model.binding) {
            binding = model.binding;
        } 
        else if (model.name && model.name.includes('/')) {
            const parts = model.name.split('/');
            binding = parts[0];
            name = parts.slice(1).join('/');
        }
        
        binding = binding.charAt(0).toUpperCase() + binding.slice(1);

        if (!groups[binding]) groups[binding] = [];
        groups[binding].push({ ...model, displayName: name });
    });
    
    return Object.keys(groups).sort().reduce((acc, key) => {
        acc[key] = groups[key].sort((a, b) => a.displayName.localeCompare(b.displayName));
        return acc;
    }, {});
});

onMounted(() => {
    if (!aiBotSettings.value) adminStore.fetchAiBotSettings();
    if (adminAvailableLollmsModels.value.length === 0) adminStore.fetchAdminAvailableLollmsModels();
    // Use optional chaining or checks to safely call fetch if array is empty or undefined
    if (!publicPersonalities.value || publicPersonalities.value.length === 0) dataStore.fetchPersonalities();
    dataStore.fetchDataStores(); 
});

watch(aiBotSettings, populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

function populateForm() {
    if (!aiBotSettings.value) return;

    const s = aiBotSettings.value;
    const newFormState = {
        lollms_model_name: s.lollms_model_name || '',
        active_personality_id: s.active_personality_id || '',
        ai_bot_enabled: s.ai_bot_enabled ?? false,
        ai_bot_system_prompt: s.ai_bot_system_prompt || '',
        ai_bot_auto_post: s.ai_bot_auto_post ?? false,
        ai_bot_post_interval: s.ai_bot_post_interval || 24,
        ai_bot_content_mode: s.ai_bot_content_mode || 'static_text',
        ai_bot_static_content: s.ai_bot_static_content || '',
        ai_bot_file_path: s.ai_bot_file_path || '',
        ai_bot_generation_prompt: s.ai_bot_generation_prompt || '',
        ai_bot_rag_datastore_ids: s.ai_bot_rag_datastore_ids || [],
        ai_bot_moderation_enabled: s.ai_bot_moderation_enabled ?? false,
        ai_bot_moderation_criteria: s.ai_bot_moderation_criteria || 'Be polite and respectful.'
    };
    
    form.value = newFormState;
    pristineState = JSON.stringify(form.value);
    hasChanges.value = false;
}

async function handleSave() {
    isLoading.value = true;
    try {
        const payload = { ...form.value };
        await adminStore.updateAiBotSettings(payload);
        uiStore.addNotification('Settings saved successfully', 'success');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to save settings', 'error');
    } finally {
        isLoading.value = false;
    }
}

async function triggerPostNow() {
    if(!confirm("This will force the bot to generate and publish a post immediately using the current settings. Continue?")) return;
    
    isTriggering.value = true;
    try {
        await apiClient.post('/api/admin/trigger-post');
        uiStore.addNotification('Post generation task started!', 'success');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to trigger post.', 'error');
    } finally {
        isTriggering.value = false;
    }
}

async function triggerModerationNow() {
    if(!confirm("This will scan all old posts and comments that haven't been validated yet. Content violating the criteria will be flagged. Continue?")) return;
    
    isModerating.value = true;
    try {
        await adminStore.triggerBatchModeration();
        uiStore.addNotification('Batch moderation task started! Check Tasks for progress.', 'success');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to trigger moderation.', 'error');
    } finally {
        isModerating.value = false;
    }
}

async function triggerFullRemoderation() {
    if(!confirm("WARNING: This will re-evaluate ALL posts and comments in the system against the current criteria, potentially flagging previously safe content or vice versa. This may take a significant amount of time and LLM resources. Continue?")) return;

    isFullRemoderating.value = true;
    try {
        await adminStore.triggerFullRemoderation();
        uiStore.addNotification('Full Remoderation task started! Check Tasks for progress.', 'success');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to trigger full remoderation.', 'error');
    } finally {
        isFullRemoderating.value = false;
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
                Configure the automated AI assistant for @lollms replies, auto-posting, and moderation.
            </p>
        </div>
        
        <form @submit.prevent="handleSave" class="p-6">
            <div class="space-y-8">
                <!-- General Settings -->
                <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <span class="flex-grow flex flex-col">
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Enable AI Bot Responses</span>
                        <span class="text-sm text-gray-500 dark:text-gray-400">Allow the bot to reply to @lollms mentions.</span>
                    </span>
                    <button @click="form.ai_bot_enabled = !form.ai_bot_enabled" type="button" :class="[form.ai_bot_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.ai_bot_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                    </button>
                </div>

                <div class="space-y-6 pt-6 border-t dark:border-gray-600">
                    <div>
                        <div class="flex items-center gap-2 mb-1">
                            <label for="bot-model" class="block text-sm font-medium">Bot Model</label>
                            <IconAnimateSpin v-if="isLoadingLollmsModels" class="w-4 h-4 text-blue-500 animate-spin" />
                        </div>
                        <select id="bot-model" v-model="form.lollms_model_name" class="input-field mt-1" :disabled="isLoadingLollmsModels && adminAvailableLollmsModels.length === 0">
                            <option value="">-- Select a Model --</option>
                            <optgroup v-for="(models, binding) in groupedModels" :key="binding" :label="binding">
                                <option v-for="model in models" :key="model.id" :value="model.id">{{ model.displayName }}</option>
                            </optgroup>
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
                        <textarea id="bot-prompt" v-model="form.ai_bot_system_prompt" rows="3" class="input-field mt-1"></textarea>
                    </div>
                </div>

                <!-- Moderation Settings -->
                <div class="space-y-6 pt-6 border-t dark:border-gray-600">
                    <div class="flex items-center justify-between">
                        <h4 class="text-lg font-medium text-gray-900 dark:text-white">Moderation</h4>
                        
                        <div class="flex gap-2">
                            <!-- Moderate Pending Button -->
                            <button 
                                v-if="form.ai_bot_moderation_enabled"
                                type="button" 
                                @click="triggerModerationNow" 
                                :disabled="isModerating || isFullRemoderating"
                                class="btn btn-secondary btn-sm flex items-center gap-2"
                            >
                                <span v-if="isModerating" class="animate-spin">⌛</span>
                                {{ isModerating ? 'Starting...' : 'Moderate Pending' }}
                            </button>
                            
                            <!-- Full Remoderation Button -->
                            <button 
                                v-if="form.ai_bot_moderation_enabled"
                                type="button" 
                                @click="triggerFullRemoderation" 
                                :disabled="isModerating || isFullRemoderating"
                                class="btn btn-warning btn-sm flex items-center gap-2"
                            >
                                <span v-if="isFullRemoderating" class="animate-spin">⌛</span>
                                {{ isFullRemoderating ? 'Starting...' : 'Remoderate All' }}
                            </button>
                        </div>
                    </div>

                    <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <span class="flex-grow flex flex-col">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Enable Moderation</span>
                            <span class="text-sm text-gray-500 dark:text-gray-400">Bot will scan new posts/comments and remove violations.</span>
                        </span>
                        <button @click="form.ai_bot_moderation_enabled = !form.ai_bot_moderation_enabled" type="button" :class="[form.ai_bot_moderation_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                            <span :class="[form.ai_bot_moderation_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                    <div v-if="form.ai_bot_moderation_enabled">
                        <label class="block text-sm font-medium">Moderation Criteria</label>
                        <textarea v-model="form.ai_bot_moderation_criteria" rows="3" class="input-field mt-1" placeholder="e.g. No hate speech, be polite..."></textarea>
                        <p class="mt-1 text-xs text-gray-500">The rules the AI will use to judge content.</p>
                    </div>
                </div>

                <!-- Auto-Posting Settings -->
                <div class="space-y-6 pt-6 border-t dark:border-gray-600">
                    <div class="flex items-center justify-between">
                        <h4 class="text-lg font-medium text-gray-900 dark:text-white">Auto-Posting Feed</h4>
                        
                        <button 
                            v-if="form.ai_bot_auto_post"
                            type="button" 
                            @click="triggerPostNow" 
                            :disabled="isTriggering"
                            class="btn btn-secondary btn-sm flex items-center gap-2"
                        >
                            <span v-if="isTriggering" class="animate-spin">⌛</span>
                            {{ isTriggering ? 'Generating...' : 'Trigger Post Now' }}
                        </button>
                    </div>
                    
                    <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <span class="flex-grow flex flex-col">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Enable Auto-Posting</span>
                            <span class="text-sm text-gray-500 dark:text-gray-400">The bot will post to the main feed periodically based on provided material.</span>
                        </span>
                        <button @click="form.ai_bot_auto_post = !form.ai_bot_auto_post" type="button" :class="[form.ai_bot_auto_post ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                            <span :class="[form.ai_bot_auto_post ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>

                    <div v-if="form.ai_bot_auto_post" class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium">Posting Interval (Hours)</label>
                            <input type="number" v-model="form.ai_bot_post_interval" min="1" step="0.5" class="input-field mt-1">
                        </div>

                        <div>
                            <label class="block text-sm font-medium">Content Source</label>
                            <select v-model="form.ai_bot_content_mode" class="input-field mt-1">
                                <option value="static_text">Manual Text (Knowledge Base)</option>
                                <option value="rag">RAG Datastores</option>
                                <option value="file">File Path (Server Side)</option>
                            </select>
                        </div>

                        <div v-if="form.ai_bot_content_mode === 'static_text'">
                            <label class="block text-sm font-medium">Knowledge Base Material</label>
                            <textarea v-model="form.ai_bot_static_content" rows="6" class="input-field mt-1" placeholder="Paste interesting facts, news, or context here..."></textarea>
                        </div>

                        <div v-if="form.ai_bot_content_mode === 'rag'">
                            <label class="block text-sm font-medium mb-1">Select Datastores</label>
                            <!-- FIX: Added fallback for availableDataStores to ensure it's always an array before map -->
                            <MultiSelectMenu 
                                :options="(availableDataStores || []).map(ds => ({ label: ds.name, value: ds.id }))" 
                                v-model="form.ai_bot_rag_datastore_ids" 
                                placeholder="Choose datastores..." 
                            />
                            <p class="mt-1 text-xs text-gray-500">The bot will query these stores for content relevant to the generation prompt.</p>
                        </div>

                        <div v-if="form.ai_bot_content_mode === 'file'">
                            <label class="block text-sm font-medium">Absolute File Path</label>
                            <input type="text" v-model="form.ai_bot_file_path" class="input-field mt-1" placeholder="/path/to/interesting_content.txt">
                        </div>

                        <div>
                            <label class="block text-sm font-medium">Generation Prompt</label>
                            <textarea v-model="form.ai_bot_generation_prompt" rows="3" class="input-field mt-1"></textarea>
                            <p class="mt-1 text-xs text-gray-500">Instructions for the AI on how to use the material to create a post.</p>
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
    </div>
</template>
