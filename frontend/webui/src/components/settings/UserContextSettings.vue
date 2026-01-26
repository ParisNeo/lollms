<script setup>
import { computed, ref, watch, nextTick, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data'; // Import data store for lists
import { storeToRefs } from 'pinia';
import LanguageSelector from '../ui/LanguageSelector.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconCircle from '../../assets/icons/IconCircle.vue';
import IconMap from '../../assets/icons/IconMap.vue';
import IconGoogle from '../../assets/icons/IconGoogle.vue';
import IconGoogleDrive from '../../assets/icons/IconGoogleDrive.vue';
import IconCalendar from '../../assets/icons/IconCalendar.vue';

const authStore = useAuthStore();
const dataStore = useDataStore(); // Use data store
const { user } = storeToRefs(authStore);
const { availableLollmsModels, allPersonalities } = storeToRefs(dataStore);

// Local state for form fields
const preferredName = ref('');
const generalInfo = ref('');
const personalInfo = ref('');
const codingStyle = ref('');
const langPrefs = ref('');
const tellOS = ref(false);
const shareDynamicInfo = ref(true);
const sharePersonalInfo = ref(false);
const funMode = ref(false);
const aiResponseLanguage = ref('auto');
const forceAiResponseLanguage = ref(false);
const imageGenerationEnabled = ref(false);
const imageGenerationSystemPrompt = ref('');
const imageAnnotationEnabled = ref(false);
const imageEditingEnabled = ref(false); 
const slideMakerEnabled = ref(false); 
const activateGeneratedImages = ref(false);
const noteGenerationEnabled = ref(false);
const memoryEnabled = ref(false);
const autoMemoryEnabled = ref(false);
const reasoningActivation = ref(false);
const reasoningEffort = ref('medium');
const rlmEnabled = ref(false);
const maxImageWidth = ref(-1);
const maxImageHeight = ref(-1);
const compressImages = ref(false);
const imageCompressionQuality = ref(85);
const streetViewEnabled = ref(false);
const googleDriveEnabled = ref(false);
const googleCalendarEnabled = ref(false);
const googleGmailEnabled = ref(false);
const schedulerEnabled = ref(false);

const googleClientSecret = ref('');

// Internal Web Search States
const googleApiKey = ref('');
const googleCseId = ref('');
const webSearchEnabled = ref(false);
const webSearchProviders = ref(['google']); // Multi-engine support
const webSearchDeepAnalysis = ref(false);
const showSearchHelp = ref(false);
const showWorkspaceHelp = ref(false);
const isKeyVisible = ref(false);

const availableEngines = [
    { id: 'google', name: 'Google Search' },
    { id: 'duckduckgo', name: 'DuckDuckGo' },
    { id: 'wikipedia', name: 'Wikipedia' },
    { id: 'reddit', name: 'Reddit' },
    { id: 'stackoverflow', name: 'StackOverflow' },
    { id: 'x', name: 'X / Twitter' },
    { id: 'github', name: 'GitHub' }
];

function toggleEngine(id) {
    const idx = webSearchProviders.value.indexOf(id);
    if (idx > -1) {
        // Allow removing, but user should ideally have one if enabled
        webSearchProviders.value.splice(idx, 1);
    } else {
        webSearchProviders.value.push(id);
    }
}

// Herd Mode States
const herdModeEnabled = ref(false);
const herdRounds = ref(2);
const herdPrecodeParticipants = ref([]);
const herdPostcodeParticipants = ref([]);

// Dynamic Herd States
const herdDynamicMode = ref(false);
const herdModelPool = ref([]); // List of {model: '', description: ''}


const hasChanges = ref(false);
const isSaving = ref(false);

const isTtiConfigured = computed(() => !!user.value?.tti_binding_model_name);

// Function to update local state from the store
function populateForm() {
  if (user.value) {
    preferredName.value = user.value.preferred_name || '';
    generalInfo.value = user.value.data_zone || '';
    personalInfo.value = user.value.user_personal_info || '';
    codingStyle.value = user.value.coding_style_constraints || '';
    langPrefs.value = user.value.programming_language_preferences || '';
    tellOS.value = user.value.tell_llm_os || false;
    shareDynamicInfo.value = user.value.share_dynamic_info_with_llm ?? true;
    sharePersonalInfo.value = user.value.share_personal_info_with_llm || false;
    funMode.value = user.value.fun_mode || false;
    aiResponseLanguage.value = user.value.ai_response_language || 'auto';
    forceAiResponseLanguage.value = user.value.force_ai_response_language || false;
    imageGenerationEnabled.value = user.value.image_generation_enabled || false;
    imageGenerationSystemPrompt.value = user.value.image_generation_system_prompt || '';
    imageAnnotationEnabled.value = user.value.image_annotation_enabled || false;
    imageEditingEnabled.value = user.value.image_editing_enabled || false;
    slideMakerEnabled.value = user.value.slide_maker_enabled || false;
    activateGeneratedImages.value = user.value.activate_generated_images || false;
    noteGenerationEnabled.value = user.value.note_generation_enabled || false;
    memoryEnabled.value = user.value.memory_enabled || false;
    autoMemoryEnabled.value = user.value.auto_memory_enabled || false;
    reasoningActivation.value = user.value.reasoning_activation || false;
    reasoningEffort.value = user.value.reasoning_effort || 'medium';
    rlmEnabled.value = user.value.rlm_enabled || false;
    maxImageWidth.value = user.value.max_image_width ?? -1;
    maxImageHeight.value = user.value.max_image_height ?? -1;
    compressImages.value = user.value.compress_images || false;
    imageCompressionQuality.value = user.value.image_compression_quality ?? 85;
    
    // Web Search
    googleApiKey.value = user.value.google_api_key || '';
    googleCseId.value = user.value.google_cse_id || '';
    webSearchEnabled.value = user.value.web_search_enabled || false;
    webSearchProviders.value = Array.isArray(user.value.web_search_providers) ? [...user.value.web_search_providers] : ['google'];
    webSearchDeepAnalysis.value = user.value.web_search_deep_analysis || false;
    streetViewEnabled.value = user.value.street_view_enabled || false;
    googleDriveEnabled.value = user.value.google_drive_enabled || false;
    googleCalendarEnabled.value = user.value.google_calendar_enabled || false;
    googleGmailEnabled.value = user.value.google_gmail_enabled || false;
    googleClientSecret.value = user.value.google_client_secret_json || '';
    schedulerEnabled.value = user.value.scheduler_enabled || false;

    // Herd Mode
    herdModeEnabled.value = user.value.herd_mode_enabled || false;
    herdRounds.value = user.value.herd_rounds || 2;
    herdPrecodeParticipants.value = user.value.herd_precode_participants ? JSON.parse(JSON.stringify(user.value.herd_precode_participants)) : [];
    herdPostcodeParticipants.value = user.value.herd_postcode_participants ? JSON.parse(JSON.stringify(user.value.herd_postcode_participants)) : [];
    
    // Dynamic Herd
    herdDynamicMode.value = user.value.herd_dynamic_mode || false;
    herdModelPool.value = user.value.herd_model_pool ? JSON.parse(JSON.stringify(user.value.herd_model_pool)) : [];
    
    // Reset change tracker
    nextTick(() => {
        hasChanges.value = false;
    });
  }
}

// Ensure data for selectors is loaded
onMounted(() => {
    if (availableLollmsModels.value.length === 0) dataStore.fetchAvailableLollmsModels();
    if (allPersonalities.value.length === 0) dataStore.fetchPersonalities();
});

// Watch for changes in the user object (e.g., after login or refresh)
watch(user, populateForm, { immediate: true, deep: true });

// Watch for changes in local form fields to enable the save button
watch([
    preferredName, generalInfo, personalInfo, codingStyle, langPrefs, tellOS, shareDynamicInfo, sharePersonalInfo,
    funMode, aiResponseLanguage, forceAiResponseLanguage, 
    imageGenerationEnabled, imageGenerationSystemPrompt, imageAnnotationEnabled, imageEditingEnabled, slideMakerEnabled, activateGeneratedImages, noteGenerationEnabled,
    memoryEnabled, autoMemoryEnabled, reasoningActivation, reasoningEffort, rlmEnabled, maxImageWidth, maxImageHeight, compressImages, imageCompressionQuality,
    googleApiKey, googleCseId, webSearchEnabled, webSearchDeepAnalysis, webSearchProviders,
    herdModeEnabled, herdRounds, herdPrecodeParticipants, herdPostcodeParticipants, 
    streetViewEnabled, googleDriveEnabled, googleCalendarEnabled, googleGmailEnabled, googleClientSecret, schedulerEnabled,
    herdDynamicMode, herdModelPool
], () => {
  hasChanges.value = true;
}, { deep: true }); // Need deep watch for array

const staticInfo = [
  { label: 'Date', placeholder: '{{date}}' },
  { label: 'Time', placeholder: '{{time}}' },
  { label: 'Date & Time', placeholder: '{{datetime}}' },
  { label: 'Username', placeholder: '{{user_name}}' },
];

// --- HERD PARTICIPANT MANAGEMENT ---

function addPrecodeParticipant() {
    herdPrecodeParticipants.value.push({ model: '', personality: '' });
}
function removePrecodeParticipant(index) {
    herdPrecodeParticipants.value.splice(index, 1);
}

function addPostcodeParticipant() {
    herdPostcodeParticipants.value.push({ model: '', personality: '' });
}
function removePostcodeParticipant(index) {
    herdPostcodeParticipants.value.splice(index, 1);
}

// --- DYNAMIC HERD MODEL POOL MANAGEMENT ---
function addModelToPool() {
    herdModelPool.value.push({ model: '', description: '' });
}

function removeModelFromPool(index) {
    herdModelPool.value.splice(index, 1);
}

async function handleSaveChanges() {
    if (!hasChanges.value) return;
    isSaving.value = true;
    try {
        await authStore.updateUserPreferences({
            preferred_name: preferredName.value,
            data_zone: generalInfo.value,
            user_personal_info: personalInfo.value,
            coding_style_constraints: codingStyle.value,
            programming_language_preferences: langPrefs.value,
            tell_llm_os: tellOS.value,
            share_dynamic_info_with_llm: shareDynamicInfo.value,
            share_personal_info_with_llm: sharePersonalInfo.value,
            fun_mode: funMode.value,
            ai_response_language: aiResponseLanguage.value,
            force_ai_response_language: forceAiResponseLanguage.value,
            image_generation_enabled: imageGenerationEnabled.value,
            image_generation_system_prompt: imageGenerationSystemPrompt.value,
            image_annotation_enabled: imageAnnotationEnabled.value,
            image_editing_enabled: imageEditingEnabled.value,
            slide_maker_enabled: slideMakerEnabled.value,
            activate_generated_images: activateGeneratedImages.value,
            note_generation_enabled: noteGenerationEnabled.value,
            memory_enabled: memoryEnabled.value,
            auto_memory_enabled: autoMemoryEnabled.value,
            reasoning_activation: reasoningActivation.value,
            reasoning_effort: reasoningEffort.value,
            rlm_enabled: rlmEnabled.value,
            max_image_width: maxImageWidth.value,
            max_image_height: maxImageHeight.value,
            compress_images: compressImages.value,
            image_compression_quality: imageCompressionQuality.value,
            google_api_key: googleApiKey.value,
            google_cse_id: googleCseId.value,
            web_search_enabled: webSearchEnabled.value,
            web_search_providers: webSearchProviders.value,
            web_search_deep_analysis: webSearchDeepAnalysis.value,
            herd_mode_enabled: herdModeEnabled.value,
            herd_rounds: herdRounds.value,
            herd_precode_participants: herdPrecodeParticipants.value,
            herd_postcode_participants: herdPostcodeParticipants.value,
            herd_dynamic_mode: herdDynamicMode.value,
            herd_model_pool: herdModelPool.value,
            street_view_enabled: streetViewEnabled.value,
            google_drive_enabled: googleDriveEnabled.value,
            google_calendar_enabled: googleCalendarEnabled.value,
            google_gmail_enabled: googleGmailEnabled.value,
            google_client_secret_json: googleClientSecret.value,
            scheduler_enabled: schedulerEnabled.value
        });
        hasChanges.value = false;
    } finally {
        isSaving.value = false;
    }
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
    <div class="px-4 py-5 sm:p-6 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Global User Context & Tools</h3>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Manage information and internal tools shared with the AI across all discussions.
        </p>
    </div>
    
    <div class="p-4 sm:p-6 space-y-6">
        <!-- Preferred Name -->
        <div>
            <label for="preferred-name" class="block text-sm font-semibold mb-1 text-gray-700 dark:text-gray-200">Preferred Name</label>
            <input 
                type="text" 
                id="preferred-name" 
                v-model="preferredName" 
                class="input-field w-full" 
                :placeholder="user?.username || 'How should the AI address you?'"
            >
            <p class="text-xs text-gray-500 mt-1">If left blank, the AI will use your username: <strong>{{ user?.username }}</strong></p>
        </div>
        
        <!-- Web Search Settings -->
        <div class="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50 rounded-lg space-y-4">
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Internal Web Search</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Allow the AI to search the internet for real-time information.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="webSearchEnabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600 peer-disabled:opacity-50"></div>
                </label>
            </div>
            <div class="flex justify-end">
                <button @click="showSearchHelp = !showSearchHelp" class="text-xs text-blue-500 hover:underline">How to get keys?</button>
            </div>

            <div v-if="webSearchEnabled" class="space-y-4 animate-in fade-in">
                <!-- Multi-Engine Grid -->
                <div>
                    <label class="block text-xs font-semibold mb-2 text-gray-600 dark:text-gray-300 uppercase tracking-wider">Active Search Engines</label>
                    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                        <button 
                            v-for="engine in availableEngines" 
                            :key="engine.id"
                            type="button"
                            @click="toggleEngine(engine.id)"
                            class="flex items-center gap-2 p-2 rounded-lg border text-left transition-all group"
                            :class="webSearchProviders.includes(engine.id) 
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 ring-2 ring-blue-500/20' 
                                : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-500 opacity-60 hover:opacity-100 hover:border-gray-300'"
                        >
                            <IconCheckCircle v-if="webSearchProviders.includes(engine.id)" class="w-4 h-4 flex-shrink-0" />
                            <IconCircle v-else class="w-4 h-4 flex-shrink-0 opacity-30 group-hover:opacity-60" />
                            <span class="text-xs font-bold truncate">{{ engine.name }}</span>
                        </button>
                    </div>
                    <p class="text-[10px] text-gray-500 mt-2 italic">Select multiple engines to allow the AI to aggregate information from various sources in parallel.</p>
                </div>

                <div class="flex items-center justify-between pl-4 border-l-2 border-blue-300 dark:border-blue-600">
                    <div>
                        <h4 class="text-xs font-semibold text-gray-700 dark:text-gray-300">Deep Content Analysis</h4>
                        <p class="text-[10px] text-gray-500 dark:text-gray-400">If enabled, the AI will visit top search result pages to read detailed content instead of just snippets.</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" v-model="webSearchDeepAnalysis" class="sr-only peer">
                        <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                    </label>
                </div>

                <!-- Conditional Google Credentials -->
                <div v-if="webSearchProviders.includes('google')" class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-blue-100 dark:border-blue-900/40">
                    <div>
                        <label class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Google API Key</label>
                        <div class="relative">
                            <input :type="isKeyVisible ? 'text' : 'password'" v-model="googleApiKey" class="input-field w-full pr-10 text-xs" placeholder="AIza...">
                            <button type="button" @click="isKeyVisible = !isKeyVisible" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-500">
                                <IconEyeOff v-if="isKeyVisible" class="w-4 h-4" /><IconEye v-else class="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Google CSE ID</label>
                        <input type="text" v-model="googleCseId" class="input-field w-full text-xs" placeholder="cx...">
                    </div>
                    <p v-if="!googleApiKey || !googleCseId" class="text-[10px] text-red-500 italic md:col-span-2">Google API Key and CSE ID are required since Google is an active engine.</p>
                </div>
            </div>

            <!-- HELP SECTION -->
            <div v-if="showSearchHelp" class="mt-4 p-4 bg-white dark:bg-gray-800 rounded border border-blue-200 dark:border-gray-600 text-xs space-y-3 animate-in slide-in-from-top-2">
                <h4 class="font-bold text-gray-800 dark:text-gray-200">How to configure Google Search</h4>
                <ol class="list-decimal pl-4 space-y-1 text-gray-600 dark:text-gray-400">
                    <li>Go to the <a href="https://console.cloud.google.com/" target="_blank" class="text-blue-500 hover:underline">Google Cloud Console</a>.</li>
                    <li>Create a new Project (or select existing).</li>
                    <li>Navigate to <strong>APIs & Services > Library</strong> and enable:
                        <ul class="list-disc pl-4 mt-1">
                            <li><strong>Custom Search API</strong> (for Web Search)</li>
                            <li><strong>Maps Static API</strong> (if using Street View)</li>
                        </ul>
                    </li>
                    <li>Go to <strong>APIs & Services > Credentials</strong> and create an <strong>API Key</strong>. Copy it to the "Google API Key" field above.</li>
                    <li>Go to <a href="https://programmablesearchengine.google.com/" target="_blank" class="text-blue-500 hover:underline">Programmable Search Engine</a>.</li>
                    <li>Create a new search engine.
                        <ul class="list-disc pl-4">
                            <li>"Search the entire web": Yes</li>
                        </ul>
                    </li>
                    <li>Copy the <strong>Search Engine ID (cx)</strong> to the "Google CSE ID" field above.</li>
                </ol>
            </div>

        </div>
        
        <!-- Google Workspace Settings -->
        <div class="p-4 bg-white dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-lg space-y-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <IconGoogle class="w-5 h-5 text-gray-600 dark:text-gray-300"/>
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Google Workspace Tools</h3>
                </div>
                <button @click="showWorkspaceHelp = !showWorkspaceHelp" class="text-xs text-blue-500 hover:underline">How to set up?</button>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-400">Enable deep integration with Drive, Calendar, and Gmail. Requires OAuth credentials.</p>

            <div v-if="showWorkspaceHelp" class="p-4 bg-blue-50 dark:bg-gray-800 rounded border border-blue-200 dark:border-gray-600 text-xs space-y-3 animate-in slide-in-from-top-2">
                <h4 class="font-bold text-gray-800 dark:text-gray-200">How to configure Google Workspace (OAuth)</h4>
                <ol class="list-decimal pl-4 space-y-1 text-gray-600 dark:text-gray-400">
                    <li>Go to <a href="https://console.cloud.google.com/" target="_blank" class="text-blue-500 hover:underline">Google Cloud Console</a>.</li>
                    <li>Navigate to <strong>APIs & Services > Library</strong> and enable:
                        <ul class="list-disc pl-4 mt-1">
                            <li><strong>Google Drive API</strong></li>
                            <li><strong>Google Calendar API</strong></li>
                            <li><strong>Gmail API</strong></li>
                        </ul>
                    </li>
                    <li>Go to <strong>OAuth consent screen</strong>:
                        <ul class="list-disc pl-4">
                            <li>User Type: <strong>External</strong></li>
                            <li>Add your email as a <strong>Test User</strong>.</li>
                        </ul>
                    </li>
                    <li>Go to <strong>Credentials</strong> > Create Credentials > <strong>OAuth Client ID</strong>.</li>
                    <li>Application type: <strong>Desktop App</strong>.</li>
                    <li>Download the JSON file (rename it to <code>client_secret.json</code> if you want, or just open it).</li>
                    <li>Paste the <strong>entire content</strong> of that JSON file into the box below.</li>
                </ol>
            </div>

            <div>
                <label class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Client Secret JSON</label>
                <textarea v-model="googleClientSecret" class="styled-textarea font-mono text-[10px]" rows="4" placeholder='{"installed":{"client_id":"...","project_id":"...","auth_uri":"...","token_uri":"..."}}'></textarea>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <label class="flex items-center gap-2 p-2 border rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors" :class="googleDriveEnabled ? 'border-green-500 bg-green-50 dark:bg-green-900/10' : 'dark:border-gray-600'">
                    <input type="checkbox" v-model="googleDriveEnabled" class="rounded text-green-600 focus:ring-green-500">
                    <IconGoogleDrive class="w-4 h-4 text-gray-600 dark:text-gray-300" />
                    <span class="text-xs font-bold">Drive</span>
                </label>
                
                <label class="flex items-center gap-2 p-2 border rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors" :class="googleCalendarEnabled ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/10' : 'dark:border-gray-600'">
                    <input type="checkbox" v-model="googleCalendarEnabled" class="rounded text-blue-600 focus:ring-blue-500">
                    <IconCalendar class="w-4 h-4 text-gray-600 dark:text-gray-300" />
                    <span class="text-xs font-bold">Calendar</span>
                </label>
                
                <label class="flex items-center gap-2 p-2 border rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors" :class="googleGmailEnabled ? 'border-red-500 bg-red-50 dark:bg-red-900/10' : 'dark:border-gray-600'">
                    <input type="checkbox" v-model="googleGmailEnabled" class="rounded text-red-600 focus:ring-red-500">
                    <!-- Use generic mail icon if Gmail icon missing, reusing generic google icon for now or text -->
                    <span class="text-xs font-bold">Gmail</span>
                </label>
            </div>
        </div>

        <!-- Proactive Scheduler -->
        <div class="p-4 bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800/50 rounded-lg flex items-center justify-between">
            <div class="flex-grow">
                <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Proactive Task Scheduler</h3>
                <p class="text-xs text-gray-500 dark:text-gray-400">Allow the AI to schedule tasks (CRON) like checking feeds or sending reminders.</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="schedulerEnabled" class="sr-only peer">
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-indigo-300 dark:peer-focus:ring-indigo-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-500"></div>
            </label>
        </div>

        <!-- Herd Mode Settings -->
        <div class="p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800/50 rounded-lg space-y-4">
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Herd Mode</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Advanced 4-phase workflow: Brainstorm > Draft > Critique > Final.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="herdModeEnabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-purple-300 dark:peer-focus:ring-purple-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-purple-600"></div>
                </label>
            </div>
            
            <div v-if="herdModeEnabled" class="space-y-6 pl-2 border-l-2 border-purple-200 dark:border-purple-800">
                
                <div class="flex items-center gap-4">
                    <label class="text-sm font-medium whitespace-nowrap">Iterations</label>
                    <input type="number" v-model.number="herdRounds" min="1" max="5" class="input-field w-20 text-center">
                    <span class="text-xs text-gray-500">Number of critique rounds.</span>
                </div>
                
                <!-- Dynamic Herd Mode Toggle -->
                <div class="p-3 bg-white dark:bg-gray-800 rounded-lg border border-purple-100 dark:border-purple-900">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-bold uppercase text-purple-600 dark:text-purple-400">Auto-Build Crews</span>
                            <span class="text-[10px] text-gray-400 bg-gray-100 dark:bg-gray-700 px-1.5 rounded">AI Driven</span>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" v-model="herdDynamicMode" class="sr-only peer">
                            <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-purple-500"></div>
                        </label>
                    </div>
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                        If enabled, the AI will dynamically create specific personalities for the Pre-code and Post-code crews based on your prompt, assigning roles to the models in your pool below.
                    </p>
                    
                    <!-- Dynamic Model Pool Section -->
                    <div v-if="herdDynamicMode" class="mt-4 animate-in fade-in slide-in-from-top-2">
                        <div class="flex justify-between items-center mb-2">
                            <label class="text-xs font-bold text-gray-700 dark:text-gray-300">Model Pool</label>
                            <button type="button" @click.prevent="addModelToPool" class="btn btn-secondary btn-xs flex items-center">
                                <IconPlus class="w-3 h-3 mr-1"/> Add Model
                            </button>
                        </div>
                        
                        <div v-if="herdModelPool.length === 0" class="text-center p-4 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-lg text-xs text-gray-500 italic">
                            No models in pool. Add models for the AI to use.
                        </div>
                        
                        <div v-else class="space-y-3">
                            <div v-for="(item, index) in herdModelPool" :key="'pool-'+index" class="flex items-start gap-2 bg-gray-50 dark:bg-gray-700/50 p-3 rounded border dark:border-gray-600">
                                <div class="flex-grow grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div>
                                        <label class="text-[10px] text-gray-500 block mb-1">Model Binding</label>
                                        <select v-model="item.model" class="input-field text-xs w-full">
                                            <option value="" disabled>Select Model</option>
                                            <option v-for="model in availableLollmsModels" :key="model.id" :value="model.id">{{ model.name }}</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="text-[10px] text-gray-500 block mb-1">Role/Strength Description</label>
                                        <input type="text" v-model="item.description" class="input-field text-xs w-full" placeholder="e.g. Fast, Logic, Creative...">
                                    </div>
                                </div>
                                <button type="button" @click.prevent="removeModelFromPool(index)" class="text-red-500 hover:text-red-700 p-1.5 mt-4 rounded hover:bg-red-50 dark:hover:bg-red-900/20">
                                    <IconTrash class="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    </div>                    
                </div>

                <!-- Static Crews (Only visible if Dynamic Mode is OFF) -->
                <div v-if="!herdDynamicMode" class="space-y-6">
                    <!-- Pre-code Crew -->
                    <div>
                        <div class="flex justify-between items-center mb-2">
                            <label class="text-sm font-bold text-blue-600 dark:text-blue-400">Phase 1: Pre-code Crew (Idea Generation)</label>
                            <button @click="addPrecodeParticipant" class="btn btn-secondary btn-sm flex items-center gap-1">
                                <IconPlus class="w-4 h-4"/> Add Agent
                            </button>
                        </div>
                        <div v-if="herdPrecodeParticipants.length === 0" class="text-center p-2 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-lg text-xs text-gray-500 italic">
                            No agents selected.
                        </div>
                        <div v-else class="space-y-2">
                            <div v-for="(participant, index) in herdPrecodeParticipants" :key="'pre-'+index" class="flex items-center gap-2 bg-white dark:bg-gray-800 p-2 rounded border dark:border-gray-700">
                                 <div class="flex-grow grid grid-cols-1 sm:grid-cols-2 gap-2">
                                    <select v-model="participant.model" class="input-field text-xs">
                                        <option value="" disabled>Select Model</option>
                                        <option v-for="model in availableLollmsModels" :key="model.id" :value="model.id">{{ model.name }}</option>
                                    </select>
                                    <select v-model="participant.personality" class="input-field text-xs">
                                        <option value="">Default Personality</option>
                                        <option v-for="p in allPersonalities" :key="p.name" :value="p.name">{{ p.name }}</option>
                                    </select>
                                 </div>
                                 <button @click="removePrecodeParticipant(index)" class="text-red-500 hover:text-red-700 p-1">
                                     <IconTrash class="w-4 h-4" />
                                 </button>
                            </div>
                        </div>
                    </div>

                    <!-- Post-code Crew -->
                    <div>
                        <div class="flex justify-between items-center mb-2">
                            <label class="text-sm font-bold text-green-600 dark:text-green-400">Phase 3: Post-code Crew (Critique & Review)</label>
                            <button @click="addPostcodeParticipant" class="btn btn-secondary btn-sm flex items-center gap-1">
                                <IconPlus class="w-4 h-4"/> Add Agent
                            </button>
                        </div>
                        <div v-if="herdPostcodeParticipants.length === 0" class="text-center p-2 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-lg text-xs text-gray-500 italic">
                            No agents selected.
                        </div>
                        <div v-else class="space-y-2">
                            <div v-for="(participant, index) in herdPostcodeParticipants" :key="'post-'+index" class="flex items-center gap-2 bg-white dark:bg-gray-800 p-2 rounded border dark:border-gray-700">
                                 <div class="flex-grow grid grid-cols-1 sm:grid-cols-2 gap-2">
                                    <select v-model="participant.model" class="input-field text-xs">
                                        <option value="" disabled>Select Model</option>
                                        <option v-for="model in availableLollmsModels" :key="model.id" :value="model.id">{{ model.name }}</option>
                                    </select>
                                    <select v-model="participant.personality" class="input-field text-xs">
                                        <option value="">Default Personality</option>
                                        <option v-for="p in allPersonalities" :key="p.name" :value="p.name">{{ p.name }}</option>
                                    </select>
                                 </div>
                                 <button @click="removePostcodeParticipant(index)" class="text-red-500 hover:text-red-700 p-1">
                                     <IconTrash class="w-4 h-4" />
                                 </button>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="text-[10px] text-gray-500 italic">
                    Note: Phase 2 (Draft) and Phase 4 (Final) are handled by the currently active "Leader" model/personality selected in the header.
                </div>
            </div>
        </div>

        <!-- Memory Settings -->
        <div class="p-4 bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-800/50 rounded-lg space-y-3">
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Long-Term Memory</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Allow the AI to access and manage your memory bank.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="memoryEnabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-teal-600"></div>
                </label>
            </div>
            
            <div v-if="memoryEnabled" class="flex items-center justify-between pl-4 border-l-2 border-teal-300 dark:border-teal-600">
                <div>
                    <h4 class="text-xs font-semibold text-gray-700 dark:text-gray-300">Auto Memory Decision</h4>
                    <p class="text-[10px] text-gray-500 dark:text-gray-400">Let the AI automatically decide when to save new memories during conversation.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="autoMemoryEnabled" class="sr-only peer">
                    <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-teal-600"></div>
                </label>
            </div>
        </div>

        <!-- Static Info Section -->
        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Dynamic Information</h3>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="shareDynamicInfo" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            <p v-if="shareDynamicInfo" class="text-xs text-gray-500 dark:text-gray-400 mb-3">The AI will automatically know the following information. You can use these placeholders in your prompts.</p>
            <p v-else class="text-xs text-gray-500 dark:text-gray-400 mb-3">Dynamic information is currently disabled and will not be sent to the AI.</p>
            <div v-if="shareDynamicInfo" class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <div v-for="info in staticInfo" :key="info.label" class="flex justify-between items-center">
                    <span class="text-gray-800 dark:text-gray-200">{{ info.label }}:</span>
                    <code class="px-2 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">{{ info.placeholder }}</code>
                </div>
            </div>
        </div>

        <!-- Personal Info Section -->
        <div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 rounded-lg">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Personal Information / Credentials</h3>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="sharePersonalInfo" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            <p class="text-xs text-gray-600 dark:text-gray-300 mb-2">
                You can add sensitive information here (e.g., API keys, passwords, personal details) that the AI might need for specific tasks.
            </p>
            <div class="p-2 mb-3 bg-white dark:bg-gray-900 border border-red-200 dark:border-red-800 rounded text-xs text-red-600 dark:text-red-400 font-medium">
                Warning: Do NOT enter passwords or sensitive credentials unless you are running a local, secure model that you trust. Information entered here will be sent to the AI model in the context.
            </div>
            <textarea v-model="personalInfo" class="styled-textarea" placeholder="e.g., My email password is..., API Key for Service X is..."></textarea>
        </div>
        
        <!-- Toggle Sections -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
             <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex flex-col gap-3">
                <div class="flex items-center justify-between">
                    <div class="flex-grow">
                        <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Thinking Mode</h3>
                        <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI reasoning/thinking process (if supported).</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" v-model="reasoningActivation" class="sr-only peer">
                        <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                    </label>
                </div>

                <div v-if="reasoningActivation" class="pl-4 border-l-2 border-gray-300 dark:border-gray-600 animate-in slide-in-from-top-2 fade-in">
                    <label class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Reasoning Effort</label>
                    <select v-model="reasoningEffort" class="input-field text-xs w-full sm:w-1/2">
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                    </select>
                    <p class="text-[10px] text-gray-500 mt-1">Controls the depth of thought for reasoning models.</p>
                </div>
            </div>

            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Recursive Language Model (RLM)</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable recursive context processing for large text.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="rlmEnabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>

            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Fun Mode 🎉</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Ask the AI to be more humorous and witty.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="funMode" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Image Annotation</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI to annotate images with bounding boxes.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="imageAnnotationEnabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Note Generation</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI to generate and format notes during conversation.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="noteGenerationEnabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>

            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Operating System</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Inform the AI about your current operating system.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="tellOS" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Image Editing</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI to edit existing images using tags like &lt;edit_image&gt;.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="imageEditingEnabled" class="sr-only peer" :disabled="!isTtiConfigured">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600 peer-disabled:opacity-50"></div>
                </label>
            </div>
            
            <!-- Slide Maker Toggle -->
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Slide Maker</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI to generate slide presentations with images.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="slideMakerEnabled" class="sr-only peer" :disabled="!isTtiConfigured">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600 peer-disabled:opacity-50"></div>
                </label>
            </div>

            <!-- Street View Toggle -->
            <div class="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/50 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Google Street View</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI to fetch street view images. Requires 'Maps Static API' enabled on your Google API Key.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="streetViewEnabled" class="sr-only peer" :disabled="!googleApiKey">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-amber-300 dark:peer-focus:ring-amber-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-amber-500 peer-disabled:opacity-50"></div>
                </label>
            </div>

        </div>
        
        <!-- Image Generation Settings -->
        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg">
            <div class="flex items-center justify-between mb-3">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold" :class="isTtiConfigured ? 'text-gray-700 dark:text-gray-200' : 'text-gray-400 dark:text-gray-500'">Image Generation</h3>
                    <p class="text-xs" :class="isTtiConfigured ? 'text-gray-500 dark:text-gray-400' : 'text-gray-400 dark:text-gray-500'">
                        {{ isTtiConfigured ? 'Enable AI to generate images using code blocks.' : 'Select a TTI model in settings to enable.' }}
                    </p>
                </div>
                <label class="relative inline-flex items-center" :class="isTtiConfigured ? 'cursor-pointer' : 'cursor-not-allowed'">
                    <input type="checkbox" v-model="imageGenerationEnabled" class="sr-only peer" :disabled="!isTtiConfigured">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600 peer-disabled:opacity-50"></div>
                </label>
            </div>

            <div v-if="imageGenerationEnabled && isTtiConfigured" class="space-y-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                <!-- System Prompt -->
                <div>
                    <label for="image-gen-prompt" class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">Image Generation System Prompt</label>
                    <textarea id="image-gen-prompt" v-model="imageGenerationSystemPrompt" class="styled-textarea" placeholder="e.g., All images should be in a photorealistic style, 4k, detailed."></textarea>
                    <p class="text-xs text-gray-500 mt-1">This prompt will be added to every image generation request made from within a chat message.</p>
                </div>

                <!-- Auto Activate Setting -->
                <div class="flex items-center justify-between">
                    <div class="flex-grow pr-4">
                        <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Auto-Activate Generated Images</h4>
                        <p class="text-xs text-gray-500 dark:text-gray-400">If enabled, images generated by the AI will be automatically added to the conversation context for future turns.</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" v-model="activateGeneratedImages" class="sr-only peer">
                        <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                    </label>
                </div>
            </div>
        </div>

        <!-- Image Resizing Settings -->
        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg">
            <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">Image Upload Resizing</h3>
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Automatically resize images sent to the AI if they exceed these dimensions. Set to -1 to disable resizing.
            </p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                    <label for="max-image-width" class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Max Width (px)</label>
                    <input type="number" id="max-image-width" v-model.number="maxImageWidth" class="input-field w-full" placeholder="-1">
                </div>
                <div>
                    <label for="max-image-height" class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Max Height (px)</label>
                    <input type="number" id="max-image-height" v-model.number="maxImageHeight" class="input-field w-full" placeholder="-1">
                </div>
            </div>

             <!-- Compression Settings -->
             <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex-grow pr-4">
                        <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Compress Images</h4>
                        <p class="text-xs text-gray-500 dark:text-gray-400">Convert uploads to JPEG to reduce size (helps avoid API limits). Defaults to PNG if disabled.</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" v-model="compressImages" class="sr-only peer">
                        <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                    </label>
                </div>
                
                <div v-if="compressImages">
                    <label for="compression-quality" class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Quality ({{ imageCompressionQuality }})</label>
                    <input type="range" id="compression-quality" v-model.number="imageCompressionQuality" min="10" max="100" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700">
                </div>
            </div>
        </div>

        <!-- AI Language Setting -->
        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg">
            <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">AI Response Language</h3>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="forceAiResponseLanguage" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            <LanguageSelector v-model="aiResponseLanguage" id="aiResponseLanguage" :include-auto="true" :disabled="!forceAiResponseLanguage" />
            <p v-if="forceAiResponseLanguage" class="mt-2 text-xs text-gray-500 dark:text-gray-400">Force the AI to respond in a specific language. 'Auto' will match the user's prompt language.</p>
            <p v-else class="mt-2 text-xs text-gray-500 dark:text-gray-400">Language enforcement is disabled. The AI will respond based on its training and personality.</p>
        </div>

        <!-- Text Areas for Preferences -->
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">Coding Style Constraints</label>
                <textarea v-model="codingStyle" class="styled-textarea" placeholder="e.g., Always follow PEP8 for Python code. Use pathlib instead of os.path."></textarea>
            </div>
            <div>
                <label class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">Programming Language & Library Preferences</label>
                <textarea v-model="langPrefs" class="styled-textarea" placeholder="e.g., I prefer solutions in Python 3.10+. For web development, use Vue.js with Tailwind CSS."></textarea>
            </div>
            <div>
                <label class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">General Info / Notes</label>
                <textarea v-model="generalInfo" class="styled-textarea" placeholder="Add any other information about yourself or general instructions for the AI."></textarea>
            </div>
        </div>
    </div>
    
    <div class="px-4 py-3 bg-gray-50 dark:bg-gray-700/50 text-right sm:px-6 rounded-b-lg border-t border-gray-200 dark:border-gray-700">
        <button @click="handleSaveChanges" class="btn btn-primary" :disabled="!hasChanges || isSaving">
            {{ isSaving ? 'Saving...' : 'Save Context Settings' }}
        </button>
    </div>
  </div>
</template>

<style scoped>
.styled-textarea {
    @apply w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 focus:ring-blue-500 focus:border-blue-500 transition text-sm min-h-[100px] resize-y;
}
</style>
