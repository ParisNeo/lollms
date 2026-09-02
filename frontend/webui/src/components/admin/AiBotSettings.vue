<!-- frontend/webui/src/components/admin/AiBotSettings.vue -->
<script setup>
import { ref, watch, onMounted, computed, nextTick } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import { storeToRefs } from 'pinia';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const adminStore = useAdminStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

const { aiBotSettings, isLoadingAiBotSettings } = storeToRefs(adminStore);
const { publicPersonalities, ownedDataStores, availableLLMModelsGrouped, isLoadingLollmsModels } = storeToRefs(dataStore);

const form = ref({
    ai_bot_enabled: false,
    ai_bot_system_prompt: '',
    lollms_model_name: '',
    active_personality_id: '',
    // Auto-posting settings
    ai_bot_auto_post: false,
    ai_bot_post_interval: 24,
    ai_bot_content_mode: 'static_text',
    ai_bot_static_content: '',
    ai_bot_file_path: '',
    ai_bot_generation_prompt: 'Generate an interesting and engaging social media post based on the provided context. Keep it under 500 characters.',
    ai_bot_rag_datastore_ids: [],
    // Scheduled Tasks & Platforms
    ai_bot_scheduled_tasks: [],
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
    ai_bot_tool_rss_enabled: false,
    //what's app
    ai_bot_whatsapp_enabled: false,
    ai_bot_whatsapp_token: '',
    ai_bot_whatsapp_phone_number_id: '',
});

const isLoading = ref(false);
const isTriggering = ref(false);
const isModerating = ref(false); 
const isFullRemoderating = ref(false); 
const showGoogleSearchHelp = ref(false);
const hasChanges = ref(false);
let isPopulating = false;
let pristineState = '{}';

const availablePersonalitiesForSelect = computed(() => {
    return (publicPersonalities.value || []).map(p => ({
        id: p.id,
        name: `${p.name} (by ${p.author || 'System'})`
    }));
});

function getTaskScheduleType(cron) {
    const parts = (cron || '').split(' ');
    if (parts.length !== 5) return 'custom';
    const [min, hour, dom, mon, dow] = parts;
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
        return `${parts[1].padStart(2, '0')}:${parts[0].padStart(2, '0')}`;
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
        const [h, m] = (task.ui_time || '09:00').split(':');
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

function populateForm() {
    if (!aiBotSettings.value) return;

    isPopulating = true;
    const s = aiBotSettings.value;
    
    const tasksMapped = (s.ai_bot_scheduled_tasks || []).map(t => ({
        ...t,
        ui_type: getTaskScheduleType(t.cron),
        ui_time: getTaskTime(t.cron),
        ui_minute: getTaskMinute(t.cron),
        ui_day: getTaskDay(t.cron)
    }));

    form.value = {
        lollms_model_name: s.lollms_model_name || '',
        active_personality_id: s.active_personality_id || '',
        ai_bot_enabled: Boolean(s.ai_bot_enabled),
        ai_bot_system_prompt: s.ai_bot_system_prompt || '',
        ai_bot_auto_post: Boolean(s.ai_bot_auto_post),
        ai_bot_post_interval: s.ai_bot_post_interval || 24,
        ai_bot_content_mode: s.ai_bot_content_mode || 'static_text',
        ai_bot_static_content: s.ai_bot_static_content || '',
        ai_bot_file_path: s.ai_bot_file_path || '',
        ai_bot_generation_prompt: s.ai_bot_generation_prompt || 'Generate an engaging post.',
        ai_bot_rag_datastore_ids: s.ai_bot_rag_datastore_ids || [],
        ai_bot_moderation_enabled: Boolean(s.ai_bot_moderation_enabled),
        ai_bot_moderation_criteria: s.ai_bot_moderation_criteria || 'Be polite and respectful.',
        ai_bot_scheduled_tasks: tasksMapped,
        ai_bot_telegram_enabled: Boolean(s.ai_bot_telegram_enabled),
        ai_bot_telegram_token: s.ai_bot_telegram_token || '',
        ai_bot_discord_enabled: Boolean(s.ai_bot_discord_enabled),
        ai_bot_discord_token: s.ai_bot_discord_token || '',
        ai_bot_slack_enabled: Boolean(s.ai_bot_slack_enabled),
        ai_bot_slack_app_token: s.ai_bot_slack_app_token || '',
        ai_bot_slack_bot_token: s.ai_bot_slack_bot_token || '',
        ai_bot_tool_ddg_enabled: Boolean(s.ai_bot_tool_ddg_enabled),
        ai_bot_whatsapp_token: s.ai_bot_whatsapp_token || '',
        ai_bot_whatsapp_phone_number_id: s.ai_bot_whatsapp_phone_number_id || '',
        ai_bot_tool_ddg_enabled: Boolean(s.ai_bot_tool_ddg_enabled),
        ai_bot_tool_google_enabled: Boolean(s.ai_bot_tool_google_enabled),
        ai_bot_tool_google_api_key: s.ai_bot_tool_google_api_key || '',
        ai_bot_tool_google_cse_id: s.ai_bot_tool_google_cse_id || '',
        ai_bot_tool_arxiv_enabled: Boolean(s.ai_bot_tool_arxiv_enabled),
        ai_bot_tool_scraper_enabled: Boolean(s.ai_bot_tool_scraper_enabled),
        ai_bot_tool_rss_enabled: Boolean(s.ai_bot_tool_rss_enabled)
    };
    
    pristineState = JSON.stringify(form.value);
    nextTick(() => {
        hasChanges.value = false;
        isPopulating = false;
    });
}

onMounted(async () => {
    await Promise.allSettled([
        adminStore.fetchAiBotSettings(true),
        dataStore.fetchAvailableLollmsModels(),
        dataStore.fetchPersonalities(),
        dataStore.fetchDataStores()
    ]);
});

watch(aiBotSettings, populateForm, { deep: true });

watch(form, (newValue) => {
    if (!isPopulating) {
        hasChanges.value = JSON.stringify(newValue) !== pristineState;
    }
}, { deep: true });

async function handleSave() {
    isLoading.value = true;
    try {
        const payload = { ...form.value };
        payload.ai_bot_scheduled_tasks = payload.ai_bot_scheduled_tasks.map(t => {
            const { ui_type, ui_time, ui_minute, ui_day, ...rest } = t;
            return rest;
        });

        await adminStore.updateAiBotSettings(payload);
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
        uiStore.addNotification('AI Bot settings saved successfully.', 'success');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to save AI Bot settings.', 'error');
    } finally {
        isLoading.value = false;
    }
}

async function triggerPostNow() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Force AI Bot Post?',
        message: 'This will force @lollms to generate and publish a social feed post immediately.',
        confirmText: 'Post Now'
    });
    if (!confirmed.confirmed) return;

    isTriggering.value = true;
    try {
        await apiClient.post('/api/admin/trigger-post');
        uiStore.addNotification('Post generation task started!', 'success');
    } catch (e) {
        uiStore.addNotification('Failed to trigger post.', 'error');
    } finally {
        isTriggering.value = false;
    }
}

async function triggerModerationNow() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Moderate Pending Content?',
        message: 'This will scan all unmoderated posts and comments against the criteria.',
        confirmText: 'Run Moderation'
    });
    if (!confirmed.confirmed) return;

    isModerating.value = true;
    try {
        await adminStore.triggerBatchModeration();
        uiStore.addNotification('Batch moderation task started.', 'success');
    } catch (e) {
        uiStore.addNotification('Failed to trigger moderation.', 'error');
    } finally {
        isModerating.value = false;
    }
}

async function triggerFullRemoderation() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Full System Remoderation?',
        message: 'This will re-evaluate ALL historical posts and comments against the current criteria.',
        confirmText: 'Remoderate All',
        danger: true
    });
    if (!confirmed.confirmed) return;

    isFullRemoderating.value = true;
    try {
        await adminStore.triggerFullRemoderation();
        uiStore.addNotification('Full remoderation task started.', 'success');
    } catch (e) {
        uiStore.addNotification('Failed to trigger full remoderation.', 'error');
    } finally {
        isFullRemoderating.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl border border-gray-100 dark:border-gray-700">
        <div class="p-6 border-b border-gray-100 dark:border-gray-700/80 flex justify-between items-center flex-wrap gap-4">
            <div>
                <h3 class="text-xl font-bold text-gray-900 dark:text-white">AI Bot Configuration</h3>
                <p class="mt-0.5 text-xs text-gray-500 dark:text-gray-400">Configure @lollms automated replies, model profile, scheduled feeds, and content moderation.</p>
            </div>
            <div class="flex items-center gap-2">
                <button type="button" @click="triggerPostNow" :disabled="isTriggering" class="btn btn-secondary btn-sm text-xs font-bold">
                    <IconAnimateSpin v-if="isTriggering" class="w-3.5 h-3.5 mr-1 animate-spin" />
                    <span>Post to Feed Now</span>
                </button>
            </div>
        </div>
        
        <form @submit.prevent="handleSave" class="p-6 space-y-8">
            <!-- Master Toggle -->
            <div class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900/40 rounded-2xl border border-gray-100 dark:border-gray-700">
                <div class="flex flex-col">
                    <span class="text-sm font-bold text-gray-900 dark:text-white">Enable AI Bot Responses</span>
                    <span class="text-xs text-gray-500">Allow @lollms to automatically respond to mentions in the community feed.</span>
                </div>
                <button @click="form.ai_bot_enabled = !form.ai_bot_enabled" type="button" :class="[form.ai_bot_enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                    <span :class="[form.ai_bot_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                </button>
            </div>

            <!-- Model Profile & Personality Selection -->
            <div class="space-y-4 pt-2">
                <h4 class="text-xs font-black uppercase text-gray-400 tracking-wider">Universal Model Profile & Behavior</h4>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div>
                        <label for="bot-model" class="block text-xs font-bold uppercase text-gray-500 mb-1">Bot Universal Model Profile</label>
                        <select id="bot-model" v-model="form.lollms_model_name" class="input-field text-xs font-medium" :disabled="isLoadingLollmsModels">
                            <option value="">-- Use System Default Model Profile --</option>
                            <optgroup v-for="group in availableLLMModelsGrouped" :key="group.label" :label="group.label">
                                <option v-for="model in group.items" :key="model.id" :value="model.id">
                                    {{ model.name }} {{ (model.vision_enabled || model.has_vision) ? '👁️' : '' }} ({{ model.id }})
                                </option>
                            </optgroup>
                        </select>
                        <p class="mt-1 text-[10px] text-gray-400">Assigned execution model for all @lollms auto-replies and scheduled tasks.</p>
                    </div>

                    <div>
                        <label for="bot-personality" class="block text-xs font-bold uppercase text-gray-500 mb-1">Bot Persona</label>
                        <select id="bot-personality" v-model="form.active_personality_id" class="input-field text-xs font-medium">
                            <option value="">-- Use Default System Prompt --</option>
                            <option v-for="p in availablePersonalitiesForSelect" :key="p.id" :value="p.id">{{ p.name }}</option>
                        </select>
                        <p class="mt-1 text-[10px] text-gray-400">Persona conditioning defining tone and style.</p>
                    </div>
                </div>

                <div v-if="!form.active_personality_id">
                    <label for="bot-prompt" class="block text-xs font-bold uppercase text-gray-500 mb-1">Default System Prompt</label>
                    <textarea id="bot-prompt" v-model="form.ai_bot_system_prompt" rows="3" class="input-field text-xs" placeholder="You are @lollms, an AI assistant..."></textarea>
                </div>
            </div>

            <!-- Activable Tools -->
            <div class="space-y-4 pt-4 border-t dark:border-gray-700/60">
                <h4 class="text-xs font-black uppercase text-gray-400 tracking-wider">Activable Research Tools</h4>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900/40 rounded-xl border dark:border-gray-700">
                        <span class="text-xs font-bold">DuckDuckGo Search</span>
                        <button @click="form.ai_bot_tool_ddg_enabled = !form.ai_bot_tool_ddg_enabled" type="button" :class="[form.ai_bot_tool_ddg_enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200']">
                            <span :class="[form.ai_bot_tool_ddg_enabled ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition']"></span>
                        </button>
                    </div>

                    <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900/40 rounded-xl border dark:border-gray-700">
                        <span class="text-xs font-bold">ArXiv Research Papers</span>
                        <button @click="form.ai_bot_tool_arxiv_enabled = !form.ai_bot_tool_arxiv_enabled" type="button" :class="[form.ai_bot_tool_arxiv_enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200']">
                            <span :class="[form.ai_bot_tool_arxiv_enabled ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition']"></span>
                        </button>
                    </div>

                    <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900/40 rounded-xl border dark:border-gray-700">
                        <span class="text-xs font-bold">Web Scraper</span>
                        <button @click="form.ai_bot_tool_scraper_enabled = !form.ai_bot_tool_scraper_enabled" type="button" :class="[form.ai_bot_tool_scraper_enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200']">
                            <span :class="[form.ai_bot_tool_scraper_enabled ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition']"></span>
                        </button>
                    </div>

                    <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900/40 rounded-xl border dark:border-gray-700">
                        <span class="text-xs font-bold">RSS Feed Knowledge</span>
                        <button @click="form.ai_bot_tool_rss_enabled = !form.ai_bot_tool_rss_enabled" type="button" :class="[form.ai_bot_tool_rss_enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200']">
                            <span :class="[form.ai_bot_tool_rss_enabled ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition']"></span>
                        </button>
                    </div>
                </div>

                <!-- Google Search (Special Handling for Credentials & Setup Help) -->
                <div class="p-4 bg-gray-50 dark:bg-gray-900/40 rounded-xl border dark:border-gray-700 space-y-3">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-bold">Google Custom Search Engine (CSE)</span>
                            <button type="button" @click="showGoogleSearchHelp = !showGoogleSearchHelp" class="text-[10px] text-blue-500 hover:underline font-semibold">
                                {{ showGoogleSearchHelp ? 'Hide Help' : 'Setup Guide & Links ↗' }}
                            </button>
                        </div>
                        <button @click="form.ai_bot_tool_google_enabled = !form.ai_bot_tool_google_enabled" type="button" :class="[form.ai_bot_tool_google_enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200']">
                            <span :class="[form.ai_bot_tool_google_enabled ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition']"></span>
                        </button>
                    </div>

                    <!-- Expandable Step-by-Step Tutorial & Links -->
                    <div v-if="showGoogleSearchHelp" class="p-3.5 bg-blue-50/60 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-xl text-xs space-y-2 text-gray-700 dark:text-gray-300 animate-in fade-in">
                        <div class="font-bold text-blue-900 dark:text-blue-200 text-xs">How to get your Google API Key & Search Engine ID (CX ID):</div>
                        <ol class="list-decimal list-inside space-y-1 text-[11px] leading-relaxed">
                            <li>Open the <a href="https://console.cloud.google.com/" target="_blank" class="text-blue-600 font-bold hover:underline">Google Cloud Console</a>, create/select a project, and enable the <strong>Custom Search API</strong>.</li>
                            <li>Navigate to <strong>APIs & Services &rarr; Credentials</strong>, click <strong>Create Credentials &rarr; API Key</strong>, and paste it into <strong>Google API Key</strong> below.</li>
                            <li>Go to the <a href="https://programmablesearchengine.google.com/controlpanel/all" target="_blank" class="text-blue-600 font-bold hover:underline">Google Programmable Search Engine Panel</a>.</li>
                            <li>Click <strong>Add</strong>, give it a name, select <strong>Search the entire web</strong>, and create it.</li>
                            <li>Under <strong>Overview</strong>, copy your <strong>Search Engine ID (CX ID)</strong> and paste it into the field below.</li>
                        </ol>
                    </div>

                    <div v-if="form.ai_bot_tool_google_enabled" class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                        <div>
                            <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Google API Key</label>
                            <input type="password" v-model="form.ai_bot_tool_google_api_key" placeholder="AIzaSy..." class="input-field text-xs">
                        </div>
                        <div>
                            <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Search Engine ID (CX ID)</label>
                            <input type="text" v-model="form.ai_bot_tool_google_cse_id" placeholder="0123456789abcdef..." class="input-field text-xs">
                        </div>
                    </div>
                </div>
            </div>

            <!-- Content Moderation -->
            <div class="space-y-4 pt-4 border-t dark:border-gray-700/60">
                <div class="flex items-center justify-between">
                    <h4 class="text-xs font-black uppercase text-gray-400 tracking-wider">Automated Content Moderation</h4>
                    <div class="flex gap-2">
                        <button v-if="form.ai_bot_moderation_enabled" type="button" @click="triggerModerationNow" :disabled="isModerating" class="btn btn-secondary btn-xs text-[10px]">
                            <IconAnimateSpin v-if="isModerating" class="w-3 h-3 mr-1 animate-spin" />
                            <span>Moderate Pending</span>
                        </button>
                        <button v-if="form.ai_bot_moderation_enabled" type="button" @click="triggerFullRemoderation" :disabled="isFullRemoderating" class="btn btn-warning btn-xs text-[10px]">
                            <IconAnimateSpin v-if="isFullRemoderating" class="w-3 h-3 mr-1 animate-spin" />
                            <span>Remoderate All</span>
                        </button>
                    </div>
                </div>

                <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900/40 rounded-xl border dark:border-gray-700">
                    <div class="flex flex-col">
                        <span class="text-xs font-bold">Enable Moderation Guard</span>
                        <span class="text-[10px] text-gray-500">Scan community posts and comments against moderation criteria.</span>
                    </div>
                    <button @click="form.ai_bot_moderation_enabled = !form.ai_bot_moderation_enabled" type="button" :class="[form.ai_bot_moderation_enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200']">
                        <span :class="[form.ai_bot_moderation_enabled ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition']"></span>
                    </button>
                </div>

                <div v-if="form.ai_bot_moderation_enabled">
                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Moderation Criteria</label>
                    <textarea v-model="form.ai_bot_moderation_criteria" rows="3" class="input-field text-xs" placeholder="e.g. Reject hate speech, harassment, spam, and explicit content."></textarea>
                </div>
            </div>

            <!-- Scheduled Tasks -->
            <div class="space-y-4 pt-4 border-t dark:border-gray-700/60">
                <div class="flex items-center justify-between">
                    <div>
                        <h4 class="text-xs font-black uppercase text-gray-400 tracking-wider">Scheduled Tasks (CRON)</h4>
                        <p class="text-[11px] text-gray-500">Autonomous routine tasks run by @lollms in the background.</p>
                    </div>
                    <button type="button" @click="addScheduledTask" class="btn btn-secondary btn-xs flex items-center gap-1">
                        <IconPlus class="w-3 h-3" /> Add Task
                    </button>
                </div>

                <div v-if="form.ai_bot_scheduled_tasks.length === 0" class="text-xs text-gray-400 italic p-4 bg-gray-50 dark:bg-gray-900/30 rounded-xl text-center border border-dashed dark:border-gray-700">
                    No scheduled routine tasks configured.
                </div>

                <div v-for="(task, index) in form.ai_bot_scheduled_tasks" :key="index" class="p-4 bg-gray-50 dark:bg-gray-900/40 rounded-xl border dark:border-gray-700 space-y-3">
                    <div class="flex items-center justify-between gap-3">
                        <input v-model="task.name" type="text" class="input-field text-xs font-bold grow" placeholder="Task Name (e.g. Daily Tech Digest)">
                        <div class="flex items-center gap-2">
                            <label class="flex items-center gap-1 text-xs font-bold cursor-pointer">
                                <input type="checkbox" v-model="task.active" class="rounded text-blue-600">
                                <span>Active</span>
                            </label>
                            <button type="button" @click="removeScheduledTask(index)" class="p-1 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg">
                                <IconTrash class="w-4 h-4" />
                            </button>
                        </div>
                    </div>

                    <div class="flex flex-wrap items-center gap-2 bg-white dark:bg-gray-800 p-2 rounded-xl border dark:border-gray-700 text-xs">
                        <span class="font-bold text-gray-400 text-[10px] uppercase">Frequency:</span>
                        <select v-model="task.ui_type" @change="updateCron(task)" class="input-field !py-1 !px-2 text-xs">
                            <option value="hourly">Hourly</option>
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="custom">Custom (CRON)</option>
                        </select>
                        <template v-if="task.ui_type === 'daily'">
                            <span class="text-gray-400">at</span>
                            <input type="time" v-model="task.ui_time" @change="updateCron(task)" class="input-field !py-1 !px-2 text-xs">
                        </template>
                        <template v-if="task.ui_type === 'custom'">
                            <input v-model="task.cron" type="text" class="input-field !py-1 !px-2 text-xs font-mono text-center" placeholder="0 9 * * *">
                        </template>
                        <span class="ml-auto font-mono text-[10px] text-gray-400">{{ task.cron }}</span>
                    </div>

                    <div>
                        <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Instruction Prompt</label>
                        <textarea v-model="task.prompt" rows="2" class="input-field text-xs" placeholder="Summarize news and post an update to the community feed..."></textarea>
                    </div>
                </div>
            </div>

            <!-- Save Bar -->
            <div class="flex justify-end pt-4 border-t dark:border-gray-700">
                <button type="submit" class="btn btn-primary px-8" :disabled="isLoading || !hasChanges">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isLoading ? 'Saving Settings...' : 'Save AI Bot Settings' }}
                </button>
            </div>
        </form>
    </div>
</template>