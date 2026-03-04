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
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

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
    // Scheduled Tasks & Platforms
    ai_bot_scheduled_tasks:[],
    ai_bot_telegram_enabled: false,
    ai_bot_telegram_token: '',
    ai_bot_discord_enabled: false,
    ai_bot_discord_token: '',
    ai_bot_slack_enabled: false,
    ai_bot_slack_app_token: '',
    ai_bot_slack_bot_token: '',
    // Moderation
    ai_bot_moderation_enabled: false,
    ai_bot_moderation_criteria: '',
    // Tools
    ai_bot_tool_ddg_enabled: false,
    ai_bot_tool_google_enabled: false,
    ai_bot_tool_google_api_key: '',
    ai_bot_tool_google_cse_id: '',
    ai_bot_tool_arxiv_enabled: false,
    ai_bot_tool_scraper_enabled: false,
    ai_bot_tool_rss_enabled: false
});

const isLoading = ref(false);
const isTriggering = ref(false);
const isModerating = ref(false); 
const isFullRemoderating = ref(false); 
const hasChanges = ref(false);
let pristineState = '{}';

const availablePersonalitiesForSelect = computed(() => {
    return (publicPersonalities.value || []).map(p => ({
        id: p.id,
        name: `${p.name} (by ${p.author})`
    }));
});

const availableDataStores = computed(() => {
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
        ai_bot_moderation_criteria: s.ai_bot_moderation_criteria || 'Be polite and respectful.',
        
        // Scheduled Tasks & Platforms
        ai_bot_scheduled_tasks: s.ai_bot_scheduled_tasks ? JSON.parse(JSON.stringify(s.ai_bot_scheduled_tasks)).map(t => ({
            ...t,
            ui_type: getTaskScheduleType(t.cron),
            ui_time: getTaskTime(t.cron),
            ui_minute: getTaskMinute(t.cron),
            ui_day: getTaskDay(t.cron)
        })) :[],
        ai_bot_telegram_enabled: s.ai_bot_telegram_enabled ?? false,
        ai_bot_telegram_token: s.ai_bot_telegram_token || '',
        ai_bot_discord_enabled: s.ai_bot_discord_enabled ?? false,
        ai_bot_discord_token: s.ai_bot_discord_token || '',
        ai_bot_slack_enabled: s.ai_bot_slack_enabled ?? false,
        ai_bot_slack_app_token: s.ai_bot_slack_app_token || '',
        ai_bot_slack_bot_token: s.ai_bot_slack_bot_token || '',

        ai_bot_moderation_enabled: s.ai_bot_moderation_enabled ?? false,
        ai_bot_scheduled_tasks: s.ai_bot_scheduled_tasks ? JSON.parse(JSON.stringify(s.ai_bot_scheduled_tasks)) :[],

        // Tools
        ai_bot_tool_ddg_enabled: s.ai_bot_tool_ddg_enabled ?? false,
        ai_bot_tool_google_enabled: s.ai_bot_tool_google_enabled ?? false,
        ai_bot_tool_google_api_key: s.ai_bot_tool_google_api_key || '',
        ai_bot_tool_google_cse_id: s.ai_bot_tool_google_cse_id || '',
        ai_bot_tool_arxiv_enabled: s.ai_bot_tool_arxiv_enabled ?? false,
        ai_bot_tool_scraper_enabled: s.ai_bot_tool_scraper_enabled ?? false,
        ai_bot_tool_rss_enabled: s.ai_bot_tool_rss_enabled ?? false,
    };
    
    form.value = newFormState;
    pristineState = JSON.stringify(form.value);
    hasChanges.value = false;
}

async function handleSave() {
    isLoading.value = true;
    try {
        const payload = { ...form.value };
        
        // Strip UI helper properties from tasks before saving
        payload.ai_bot_scheduled_tasks = payload.ai_bot_scheduled_tasks.map(t => {
            const { ui_type, ui_time, ui_minute, ui_day, ...rest } = t;
            return rest;
        });

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

function getTaskScheduleType(cron) {
    const parts = (cron || '').split(' ');
    if (parts.length !== 5) return 'custom';
    const[min, hour, dom, mon, dow] = parts;
    if (dom === '*' && mon === '*') {
        if (hour === '*' && dow === '*' && !isNaN(min)) return 'hourly';
        if (dow === '*' && !isNaN(hour) && !isNaN(min)) return 'daily';
        if (!isNaN(dow) && !isNaN(hour) && !isNaN(min)) return 'weekly';
    }
    return 'custom';
}

function getTaskTime(cron) {
    const parts = (cron || '').split(' ');
    if (parts.length === 5 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        return `${parts[1].padStart(2,'0')}:${parts[0].padStart(2,'0')}`;
    }
    return '09:00';
}

function getTaskMinute(cron) {
    const parts = (cron || '').split(' ');
    if (parts.length === 5 && !isNaN(parts[0])) return parts[0];
    return '0';
}

function getTaskDay(cron) {
    const parts = (cron || '').split(' ');
    if (parts.length === 5 && !isNaN(parts[4])) return parts[4];
    return '1';
}

function updateCron(task) {
    if (task.ui_type === 'hourly') {
        task.cron = `${parseInt(task.ui_minute) || 0} * * * *`;
    } else if (task.ui_type === 'daily') {
        const[h, m] = (task.ui_time || '09:00').split(':');
        task.cron = `${parseInt(m) || 0} ${parseInt(h) || 0} * * *`;
    } else if (task.ui_type === 'weekly') {
        const [h, m] = (task.ui_time || '09:00').split(':');
        task.cron = `${parseInt(m) || 0} ${parseInt(h) || 0} * * ${task.ui_day || 1}`;
    }
}

function addScheduledTask() {
    form.value.ai_bot_scheduled_tasks.push({
        name: '',
        cron: '0 9 * * *',
        prompt: '',
        active: true,
        ui_type: 'daily',
        ui_time: '09:00',
        ui_minute: '0',
        ui_day: '1'
    });
}

function removeScheduledTask(index) {
    form.value.ai_bot_scheduled_tasks.splice(index, 1);
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
<style scoped>
.toggle-switch-sm { @apply relative inline-flex items-center cursor-pointer; }
.toggle-switch-sm input { @apply sr-only; }
.toggle-switch-sm .slider-sm { @apply w-8 h-4 bg-gray-300 dark:bg-gray-600 rounded-full transition-colors; }
.toggle-switch-sm input:checked + .slider-sm { @apply bg-blue-600; }
.toggle-switch-sm .slider-sm:after { @apply content-[''] absolute top-[2px] left-[2px] bg-white rounded-full h-3 w-3 transition-all; }
.toggle-switch-sm input:checked + .slider-sm:after { @apply translate-x-4; }
</style>
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

                <!-- Activable Tools -->
                <div class="space-y-6 pt-6 border-t dark:border-gray-600">
                    <h4 class="text-lg font-medium text-gray-900 dark:text-white">Activable Tools</h4>
                    <p class="text-sm text-gray-500 dark:text-gray-400">Enable tools the bot can use to research or generate content.</p>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <!-- DuckDuckGo -->
                        <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                            <span class="flex-grow flex flex-col">
                                <span class="text-sm font-medium">DuckDuckGo Search</span>
                            </span>
                            <button @click="form.ai_bot_tool_ddg_enabled = !form.ai_bot_tool_ddg_enabled" type="button" :class="[form.ai_bot_tool_ddg_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form.ai_bot_tool_ddg_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>

                        <!-- ArXiv -->
                        <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                            <span class="flex-grow flex flex-col">
                                <span class="text-sm font-medium">ArXiv Research</span>
                            </span>
                            <button @click="form.ai_bot_tool_arxiv_enabled = !form.ai_bot_tool_arxiv_enabled" type="button" :class="[form.ai_bot_tool_arxiv_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form.ai_bot_tool_arxiv_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>

                        <!-- Web Scraper -->
                        <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                            <span class="flex-grow flex flex-col">
                                <span class="text-sm font-medium">Web Scraper</span>
                            </span>
                            <button @click="form.ai_bot_tool_scraper_enabled = !form.ai_bot_tool_scraper_enabled" type="button" :class="[form.ai_bot_tool_scraper_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form.ai_bot_tool_scraper_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>

                        <!-- RSS Feeds -->
                        <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                            <span class="flex-grow flex flex-col">
                                <span class="text-sm font-medium">RSS Feeds Knowledge</span>
                            </span>
                            <button @click="form.ai_bot_tool_rss_enabled = !form.ai_bot_tool_rss_enabled" type="button" :class="[form.ai_bot_tool_rss_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form.ai_bot_tool_rss_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>
                    </div>

                    <!-- Google Search (Special Handling for Credentials) -->
                    <div class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border dark:border-gray-600">
                        <div class="flex items-center justify-between mb-4">
                            <span class="text-sm font-medium">Google Custom Search</span>
                            <button @click="form.ai_bot_tool_google_enabled = !form.ai_bot_tool_google_enabled" type="button" :class="[form.ai_bot_tool_google_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form.ai_bot_tool_google_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>
                        <div v-if="form.ai_bot_tool_google_enabled" class="space-y-3">
                            <div>
                                <label class="block text-xs font-medium">API Key</label>
                                <input type="password" v-model="form.ai_bot_tool_google_api_key" class="input-field-sm w-full mt-1">
                            </div>
                            <div>
                                <label class="block text-xs font-medium">Search Engine ID (CSE ID)</label>
                                <input type="text" v-model="form.ai_bot_tool_google_cse_id" class="input-field-sm w-full mt-1">
                            </div>
                        </div>
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

                <!-- Scheduled Tasks -->
                <div class="space-y-6 pt-6 border-t dark:border-gray-600">
                    <div class="flex items-center justify-between">
                        <div>
                            <h4 class="text-lg font-medium text-gray-900 dark:text-white">Scheduled Tasks (CRON)</h4>
                            <p class="text-sm text-gray-500 dark:text-gray-400">Set up tasks for the bot to run at specific times (e.g. RSS feed checking, log reports).</p>
                        </div>
                        <button type="button" @click="addScheduledTask" class="btn btn-secondary btn-sm flex items-center gap-2 flex-shrink-0">
                            <IconPlus class="w-4 h-4" /> Add Task
                        </button>
                    </div>

                    <div v-if="form.ai_bot_scheduled_tasks.length === 0" class="text-sm text-gray-500 italic p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg text-center border border-dashed dark:border-gray-700">
                        No scheduled tasks configured.
                    </div>

                    <div v-for="(task, index) in form.ai_bot_scheduled_tasks" :key="index" class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border dark:border-gray-600 space-y-4 shadow-sm">
                        <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                            <div class="flex flex-col items-start gap-4 flex-1">
                                <input v-model="task.name" type="text" class="input-field text-sm w-full font-semibold" placeholder="Task Name (e.g. Daily Security Report)">
                                
                                <div class="flex flex-wrap items-center gap-2 w-full bg-white dark:bg-gray-800 p-2 rounded border dark:border-gray-700">
                                    <label class="text-xs font-bold text-gray-500 mr-2">Schedule:</label>
                                    <select v-model="task.ui_type" @change="updateCron(task)" class="input-field text-sm py-1 h-8">
                                        <option value="hourly">Hourly</option>
                                        <option value="daily">Daily</option>
                                        <option value="weekly">Weekly</option>
                                        <option value="custom">Custom (CRON)</option>
                                    </select>
                                    
                                    <template v-if="task.ui_type === 'hourly'">
                                        <span class="text-xs text-gray-500">at minute</span>
                                        <input type="number" v-model="task.ui_minute" @change="updateCron(task)" class="input-field text-sm py-1 h-8 w-16 text-center" min="0" max="59" placeholder="00">
                                    </template>
                                    
                                    <template v-if="task.ui_type === 'daily'">
                                        <span class="text-xs text-gray-500">at</span>
                                        <input type="time" v-model="task.ui_time" @change="updateCron(task)" class="input-field text-sm py-1 h-8">
                                    </template>
                                    
                                    <template v-if="task.ui_type === 'weekly'">
                                        <span class="text-xs text-gray-500">on</span>
                                        <select v-model="task.ui_day" @change="updateCron(task)" class="input-field text-sm py-1 h-8">
                                            <option value="1">Mon</option>
                                            <option value="2">Tue</option>
                                            <option value="3">Wed</option>
                                            <option value="4">Thu</option>
                                            <option value="5">Fri</option>
                                            <option value="6">Sat</option>
                                            <option value="0">Sun</option>
                                        </select>
                                        <span class="text-xs text-gray-500">at</span>
                                        <input type="time" v-model="task.ui_time" @change="updateCron(task)" class="input-field text-sm py-1 h-8">
                                    </template>

                                    <template v-if="task.ui_type === 'custom'">
                                        <input v-model="task.cron" type="text" class="input-field text-sm w-32 py-1 h-8 font-mono text-center tracking-widest" placeholder="0 2 * * *">
                                    </template>
                                    
                                    <div class="ml-auto text-[10px] text-gray-400 font-mono hidden sm:block bg-gray-100 dark:bg-gray-900 px-2 py-1 rounded" v-if="task.ui_type !== 'custom'">
                                        {{ task.cron }}
                                    </div>
                                </div>
                            </div>

                            <div class="flex items-center justify-end gap-3 sm:pt-1">
                                <label class="toggle-switch-sm" title="Toggle active status"><input type="checkbox" v-model="task.active"><span class="slider-sm"></span></label>
                                <button type="button" @click="removeScheduledTask(index)" class="btn btn-danger-outline btn-sm !p-1.5" title="Remove Task"><IconTrash class="w-4 h-4" /></button>
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs font-medium mb-1">Instruction / Prompt</label>
                            <textarea v-model="task.prompt" rows="2" class="input-field w-full text-sm" placeholder="e.g. Do a RSS feed search then make a post on the feeds..."></textarea>
                        </div>
                    </div>
                </div>

                <!-- External Platforms -->
                <div class="space-y-6 pt-6 border-t dark:border-gray-600">
                    <h4 class="text-lg font-medium text-gray-900 dark:text-white">External Platforms Integration</h4>
                    <p class="text-sm text-gray-500 dark:text-gray-400">Summon the AI Agent from other platforms using these bot tokens.</p>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <!-- Telegram -->
                        <div class="p-4 bg-blue-50 dark:bg-blue-900/10 rounded-lg border border-blue-200 dark:border-blue-800 transition-all">
                            <div class="flex items-center justify-between mb-3">
                                <h5 class="text-sm font-bold text-blue-700 dark:text-blue-300">Telegram Bot</h5>
                                <label class="toggle-switch-sm" title="Enable Telegram Bot"><input type="checkbox" v-model="form.ai_bot_telegram_enabled"><span class="slider-sm"></span></label>
                            </div>
                            <div v-if="form.ai_bot_telegram_enabled" class="animate-in fade-in slide-in-from-top-1">
                                <label class="block text-xs font-medium mb-1">Bot Token</label>
                                <input type="password" v-model="form.ai_bot_telegram_token" class="input-field w-full text-sm font-mono" placeholder="123456789:ABCDefghIJKLmnopQRSTuvwxYZ">
                            </div>
                        </div>

                        <!-- Discord -->
                        <div class="p-4 bg-indigo-50 dark:bg-indigo-900/10 rounded-lg border border-indigo-200 dark:border-indigo-800 transition-all">
                            <div class="flex items-center justify-between mb-3">
                                <h5 class="text-sm font-bold text-indigo-700 dark:text-indigo-300">Discord Bot</h5>
                                <label class="toggle-switch-sm" title="Enable Discord Bot"><input type="checkbox" v-model="form.ai_bot_discord_enabled"><span class="slider-sm"></span></label>
                            </div>
                            <div v-if="form.ai_bot_discord_enabled" class="animate-in fade-in slide-in-from-top-1">
                                <label class="block text-xs font-medium mb-1">Bot Token</label>
                                <input type="password" v-model="form.ai_bot_discord_token" class="input-field w-full text-sm font-mono" placeholder="MTAxMjM0NTY3ODkw.Gq..._ABCDefgh">
                            </div>
                        </div>

                        <!-- Slack -->
                        <div class="p-4 bg-green-50 dark:bg-green-900/10 rounded-lg border border-green-200 dark:border-green-800 md:col-span-2 transition-all">
                            <div class="flex items-center justify-between mb-3">
                                <h5 class="text-sm font-bold text-green-700 dark:text-green-300">Slack Bot</h5>
                                <label class="toggle-switch-sm" title="Enable Slack Bot"><input type="checkbox" v-model="form.ai_bot_slack_enabled"><span class="slider-sm"></span></label>
                            </div>
                            <div v-if="form.ai_bot_slack_enabled" class="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in slide-in-from-top-1">
                                <div>
                                    <label class="block text-xs font-medium mb-1">Bot User OAuth Token</label>
                                    <input type="password" v-model="form.ai_bot_slack_bot_token" class="input-field w-full text-sm font-mono" placeholder="xoxb-...">
                                </div>
                                <div>
                                    <label class="block text-xs font-medium mb-1">App-Level Token</label>
                                    <input type="password" v-model="form.ai_bot_slack_app_token" class="input-field w-full text-sm font-mono" placeholder="xapp-...">
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
    </div>
</template>
