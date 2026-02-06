<script setup>
import { computed, ref, watch, nextTick, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { storeToRefs } from 'pinia';
import LanguageSelector from '../ui/LanguageSelector.vue';

// --- Icons ---
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
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconClock from '../../assets/icons/IconClock.vue';
import IconSettings from '../../assets/icons/IconSettings.vue';
import IconObservation from '../../assets/icons/IconObservation.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();
const { user } = storeToRefs(authStore);
const { availableLollmsModels, allPersonalities } = storeToRefs(dataStore);

// --- Local state for all form fields ---
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

// Web Search
const googleApiKey = ref('');
const googleCseId = ref('');
const webSearchEnabled = ref(false);
const webSearchProviders = ref(['google']);
const webSearchDeepAnalysis = ref(false);
const streetViewEnabled = ref(false);

// Google Workspace & Scheduler
const googleDriveEnabled = ref(false);
const googleCalendarEnabled = ref(false);
const googleGmailEnabled = ref(false);
const googleClientSecret = ref('');
const schedulerEnabled = ref(false);

// Herd Mode
const herdModeEnabled = ref(false);
const herdRounds = ref(2);
const herdPrecodeParticipants = ref([]);
const herdPostcodeParticipants = ref([]);
const herdDynamicMode = ref(false);
const herdModelPool = ref([]);

// UI Helpers
const showSearchHelp = ref(false);
const showWorkspaceHelp = ref(false);
const isKeyVisible = ref(false);
const hasChanges = ref(false);
const isSaving = ref(false);

const availableEngines = [
    { id: 'google', name: 'Google Search' },
    { id: 'duckduckgo', name: 'DuckDuckGo' },
    { id: 'wikipedia', name: 'Wikipedia' },
    { id: 'reddit', name: 'Reddit' },
    { id: 'stackoverflow', name: 'StackOverflow' },
    { id: 'x', name: 'X / Twitter' },
    { id: 'github', name: 'GitHub' }
];

const staticInfo = [
  { label: 'Date', placeholder: '{{date}}' },
  { label: 'Time', placeholder: '{{time}}' },
  { label: 'Date & Time', placeholder: '{{datetime}}' },
  { label: 'Username', placeholder: '{{user_name}}' },
];

const isTtiConfigured = computed(() => !!user.value?.tti_binding_model_name);

/**
 * Maps the global user state from the store to our local form refs.
 */
function populateForm() {
  // CRITICAL: Do not overwrite local changes if we are currently in the middle of a save operation
  if (isSaving.value) return;

  if (user.value) {
    preferredName.value = user.value.preferred_name || '';
    generalInfo.value = user.value.data_zone || '';
    personalInfo.value = user.value.user_personal_info || '';
    codingStyle.value = user.value.coding_style_constraints || '';
    langPrefs.value = user.value.programming_language_preferences || '';
    tellOS.value = !!user.value.tell_llm_os;
    shareDynamicInfo.value = user.value.share_dynamic_info_with_llm ?? true;
    sharePersonalInfo.value = !!user.value.share_personal_info_with_llm;
    funMode.value = !!user.value.fun_mode;
    aiResponseLanguage.value = user.value.ai_response_language || 'auto';
    forceAiResponseLanguage.value = !!user.value.force_ai_response_language;
    imageGenerationEnabled.value = !!user.value.image_generation_enabled;
    imageGenerationSystemPrompt.value = user.value.image_generation_system_prompt || '';
    imageAnnotationEnabled.value = !!user.value.image_annotation_enabled;
    imageEditingEnabled.value = !!user.value.image_editing_enabled;
    slideMakerEnabled.value = !!user.value.slide_maker_enabled;
    activateGeneratedImages.value = !!user.value.activate_generated_images;
    noteGenerationEnabled.value = !!user.value.note_generation_enabled;
    memoryEnabled.value = !!user.value.memory_enabled;
    autoMemoryEnabled.value = !!user.value.auto_memory_enabled;
    reasoningActivation.value = !!user.value.reasoning_activation;
    reasoningEffort.value = user.value.reasoning_effort || 'medium';
    rlmEnabled.value = !!user.value.rlm_enabled;
    maxImageWidth.value = user.value.max_image_width ?? -1;
    maxImageHeight.value = user.value.max_image_height ?? -1;
    compressImages.value = !!user.value.compress_images;
    imageCompressionQuality.value = user.value.image_compression_quality ?? 85;
    
    googleApiKey.value = user.value.google_api_key || '';
    googleCseId.value = user.value.google_cse_id || '';
    webSearchEnabled.value = !!user.value.web_search_enabled;
    
    // Fix: Ensure we take a fresh copy of the array to break reactivity cycle with store
    if (Array.isArray(user.value.web_search_providers)) {
        webSearchProviders.value = [...user.value.web_search_providers];
    } else {
        webSearchProviders.value = ['google'];
    }

    webSearchDeepAnalysis.value = !!user.value.web_search_deep_analysis;
    streetViewEnabled.value = !!user.value.street_view_enabled;
    googleDriveEnabled.value = !!user.value.google_drive_enabled;
    googleCalendarEnabled.value = !!user.value.google_calendar_enabled;
    googleGmailEnabled.value = !!user.value.google_gmail_enabled;
    googleClientSecret.value = user.value.google_client_secret_json || '';
    schedulerEnabled.value = !!user.value.scheduler_enabled;

    herdModeEnabled.value = !!user.value.herd_mode_enabled;
    herdRounds.value = user.value.herd_rounds || 2;
    herdPrecodeParticipants.value = user.value.herd_precode_participants ? JSON.parse(JSON.stringify(user.value.herd_precode_participants)) : [];
    herdPostcodeParticipants.value = user.value.herd_postcode_participants ? JSON.parse(JSON.stringify(user.value.herd_postcode_participants)) : [];
    herdDynamicMode.value = !!user.value.herd_dynamic_mode;
    herdModelPool.value = user.value.herd_model_pool ? JSON.parse(JSON.stringify(user.value.herd_model_pool)) : [];
    
    nextTick(() => {
        hasChanges.value = false;
    });
  }
}

onMounted(() => {
    if (availableLollmsModels.value.length === 0) dataStore.fetchAvailableLollmsModels();
    if (allPersonalities.value.length === 0) dataStore.fetchPersonalities();
});

watch(user, populateForm, { immediate: true, deep: true });

// Listen for local changes
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
    // Only mark as changed if we aren't currently populating from the store
    hasChanges.value = true;
}, { deep: true });

// --- List Management (Using Immutable patterns to help Vue detection) ---
function toggleEngine(id) {
    const current = [...webSearchProviders.value];
    const idx = current.indexOf(id);
    if (idx > -1) current.splice(idx, 1);
    else current.push(id);
    webSearchProviders.value = current;
}
function addPrecodeParticipant() { herdPrecodeParticipants.value.push({ model: '', personality: '' }); }
function removePrecodeParticipant(index) { herdPrecodeParticipants.value.splice(index, 1); }
function addPostcodeParticipant() { herdPostcodeParticipants.value.push({ model: '', personality: '' }); }
function removePostcodeParticipant(index) { herdPostcodeParticipants.value.splice(index, 1); }
function addModelToPool() { herdModelPool.value.push({ model: '', description: '' }); }
function removeModelFromPool(index) { herdModelPool.value.splice(index, 1); }

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
            web_search_providers: [...webSearchProviders.value], // Send a fresh copy
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
        uiStore.addNotification('Global context settings saved successfully.', 'success');
    } catch (e) {
        console.error("Save failed:", e);
        uiStore.addNotification('Failed to save settings. Please check your connection.', 'error');
    } finally {
        isSaving.value = false;
    }
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg max-w-5xl mx-auto">
    <div class="px-4 py-5 sm:p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
        <div>
            <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Global User Context & Tools</h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Configure global behaviors, rules, and advanced AI features.</p>
        </div>
        <div class="flex items-center gap-3">
            <span v-if="hasChanges" class="text-xs font-bold text-amber-500 animate-pulse uppercase tracking-widest">Unsaved Changes</span>
            <button @click="handleSaveChanges" class="btn btn-primary shadow-lg" :disabled="!hasChanges || isSaving">
                <IconAnimateSpin v-if="isSaving" class="w-4 h-4 mr-2 animate-spin" />
                {{ isSaving ? 'Saving...' : 'Save All Changes' }}
            </button>
        </div>
    </div>
    
    <div class="p-4 sm:p-6 space-y-8">
        <!-- Preferred Name -->
        <div class="section-card">
            <label for="preferred-name" class="block text-sm font-semibold mb-1 text-gray-700 dark:text-gray-200">Preferred Name</label>
            <input type="text" id="preferred-name" v-model="preferredName" class="input-field w-full" :placeholder="user?.username || 'Address me as...'">
            <p class="text-xs text-gray-500 mt-1">Leave blank to use your username ({{ user?.username }}).</p>
        </div>
        
        <!-- Web Search -->
        <div class="p-5 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-xl space-y-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="p-2 bg-blue-500 text-white rounded-lg"><IconGlobeAlt class="w-5 h-5"/></div>
                    <div>
                        <h3 class="text-sm font-bold text-gray-800 dark:text-gray-100">Web Search Engine</h3>
                        <p class="text-xs text-gray-500">Allow AI to access live internet information.</p>
                    </div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" v-model="webSearchEnabled">
                    <span class="slider"></span>
                </label>
            </div>

            <div v-if="webSearchEnabled" class="space-y-5 pt-4 border-t border-blue-200 dark:border-blue-800 animate-in fade-in">
                <div>
                    <label class="block text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">Active Engines</label>
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <button v-for="engine in availableEngines" :key="engine.id" type="button" @click="toggleEngine(engine.id)"
                            class="flex items-center gap-2 p-2 rounded-lg border text-left transition-all"
                            :class="webSearchProviders.includes(engine.id) ? 'border-blue-500 bg-blue-500/10 text-blue-600 ring-2 ring-blue-500/20' : 'border-gray-200 dark:border-gray-700 opacity-50'">
                            <IconCheckCircle v-if="webSearchProviders.includes(engine.id)" class="w-4 h-4" />
                            <IconCircle v-else class="w-4 h-4" />
                            <span class="text-xs font-bold">{{ engine.name }}</span>
                        </button>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs font-bold mb-1">Google API Key</label>
                        <div class="relative">
                            <input :type="isKeyVisible ? 'text' : 'password'" v-model="googleApiKey" class="input-field w-full pr-10 text-xs" placeholder="AIza...">
                            <button type="button" @click="isKeyVisible = !isKeyVisible" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-400"><IconEyeOff v-if="isKeyVisible" class="w-4 h-4" /><IconEye v-else class="w-4 h-4" /></button>
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs font-bold mb-1">Google CSE ID</label>
                        <input type="text" v-model="googleCseId" class="input-field w-full text-xs" placeholder="cx...">
                    </div>
                </div>
                
                <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" v-model="webSearchDeepAnalysis" class="rounded text-blue-600">
                    <span class="text-xs font-medium">Enable Deep Analysis (visit top pages)</span>
                </label>

                <button @click="showSearchHelp = !showSearchHelp" class="text-xs text-blue-500 hover:underline">Setup Instructions</button>
                <div v-if="showSearchHelp" class="p-3 bg-white dark:bg-gray-800 rounded border border-blue-200 text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                    1. Enable <b>Custom Search API</b> in Google Cloud Console.<br>
                    2. Create an API Key in Credentials.<br>
                    3. Create a Search Engine at <b>programmablesearchengine.google.com</b> and copy the CX ID.
                </div>
            </div>
        </div>

        <!-- Google Workspace -->
        <div class="p-5 bg-white dark:bg-gray-700/30 border border-gray-200 dark:border-gray-600 rounded-xl space-y-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="p-2 bg-red-500 text-white rounded-lg"><IconGoogle class="w-5 h-5"/></div>
                    <h3 class="text-sm font-bold">Google Workspace Tools</h3>
                </div>
                <button @click="showWorkspaceHelp = !showWorkspaceHelp" class="text-xs text-blue-500 hover:underline">Setup Guide</button>
            </div>
            
            <div v-if="showWorkspaceHelp" class="p-3 bg-blue-50 dark:bg-gray-800 rounded border border-blue-100 text-xs mb-2">
                Download your <b>OAuth Desktop Client</b> JSON from Google Cloud Console and paste it below.
            </div>

            <div>
                <label class="block text-xs font-bold text-gray-400 uppercase mb-2">Client Secret JSON</label>
                <textarea v-model="googleClientSecret" class="input-field font-mono text-[10px] w-full" rows="3" placeholder='{"installed":{...}}'></textarea>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <label class="tool-toggle" :class="{'active': googleDriveEnabled}"><input type="checkbox" v-model="googleDriveEnabled"><IconGoogleDrive class="w-4 h-4"/><span>Drive</span></label>
                <label class="tool-toggle" :class="{'active': googleCalendarEnabled}"><input type="checkbox" v-model="googleCalendarEnabled"><IconCalendar class="w-4 h-4"/><span>Calendar</span></label>
                <label class="tool-toggle" :class="{'active': googleGmailEnabled}"><input type="checkbox" v-model="googleGmailEnabled"><IconGoogle class="w-4 h-4"/><span>Gmail</span></label>
            </div>
        </div>

        <!-- Proactive Scheduler -->
        <div class="p-5 bg-indigo-50 dark:bg-indigo-900/10 border border-indigo-200 dark:border-indigo-800 rounded-xl flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="p-2 bg-indigo-600 text-white rounded-lg"><IconClock class="w-5 h-5"/></div>
                <div>
                    <h3 class="text-sm font-bold">Task Scheduler</h3>
                    <p class="text-xs text-gray-500">Allow AI to create automated CRON tasks.</p>
                </div>
            </div>
            <label class="toggle-switch">
                <input type="checkbox" v-model="schedulerEnabled">
                <span class="slider"></span>
            </label>
        </div>

        <!-- Herd Mode -->
        <div class="p-5 bg-purple-50 dark:bg-purple-900/10 border border-purple-200 dark:border-purple-800 rounded-xl space-y-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="p-2 bg-purple-600 text-white rounded-lg"><IconUserGroup class="w-5 h-5"/></div>
                    <div>
                        <h3 class="text-sm font-bold">Herd Mode (Multi-Agent)</h3>
                        <p class="text-xs text-gray-500">4-Phase: Brainstorm, Draft, Critique, Final.</p>
                    </div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" v-model="herdModeEnabled">
                    <span class="slider"></span>
                </label>
            </div>

            <div v-if="herdModeEnabled" class="space-y-6 pt-4 border-t border-purple-200 dark:border-purple-800 animate-in slide-in-from-top-2">
                <div class="flex items-center gap-4">
                    <label class="text-xs font-bold uppercase text-gray-500">Critique Rounds</label>
                    <input type="number" v-model.number="herdRounds" min="1" max="5" class="input-field w-20 text-center">
                </div>
                
                <div class="bg-white dark:bg-gray-800 p-4 rounded-lg border dark:border-gray-700 shadow-inner">
                    <div class="flex items-center justify-between mb-4">
                        <span class="text-xs font-black uppercase text-purple-500">Dynamic AI-Selected Crews</span>
                        <label class="toggle-switch-sm"><input type="checkbox" v-model="herdDynamicMode"><span class="slider-sm"></span></label>
                    </div>
                    
                    <div v-if="herdDynamicMode" class="space-y-3">
                        <div class="flex justify-between items-center"><label class="text-xs font-bold">Model Pool</label><button @click="addModelToPool" class="btn btn-secondary btn-xs"><IconPlus class="w-3 h-3 mr-1"/> Add</button></div>
                        <div v-for="(item, index) in herdModelPool" :key="'pool-'+index" class="flex gap-2 items-start bg-gray-50 dark:bg-gray-900 p-3 rounded border dark:border-gray-700">
                            <div class="flex-grow grid grid-cols-2 gap-2">
                                <select v-model="item.model" class="input-field text-xs"><option v-for="m in availableLollmsModels" :key="m.id" :value="m.id">{{ m.name }}</option></select>
                                <input type="text" v-model="item.description" class="input-field text-xs" placeholder="e.g. Creative Expert">
                            </div>
                            <button @click="removeModelFromPool(index)" class="text-red-500 p-1"><IconTrash class="w-4 h-4"/></button>
                        </div>
                    </div>

                    <div v-else class="space-y-6">
                        <div>
                            <div class="flex justify-between items-center mb-2"><label class="text-xs font-bold text-blue-500">Phase 1: Pre-code Crew</label><button @click="addPrecodeParticipant" class="btn btn-secondary btn-xs">Add Agent</button></div>
                            <div v-for="(p, index) in herdPrecodeParticipants" :key="'pre-'+index" class="flex gap-2 mb-2">
                                <select v-model="p.model" class="input-field text-xs flex-1"><option v-for="m in availableLollmsModels" :key="m.id" :value="m.id">{{ m.name }}</option></select>
                                <select v-model="p.personality" class="input-field text-xs flex-1"><option v-for="pers in allPersonalities" :key="pers.name" :value="pers.name">{{ pers.name }}</option></select>
                                <button @click="removePrecodeParticipant(index)" class="text-red-500 p-1"><IconTrash class="w-4 h-4"/></button>
                            </div>
                        </div>
                        <div>
                            <div class="flex justify-between items-center mb-2"><label class="text-xs font-bold text-green-500">Phase 3: Post-code Crew</label><button @click="addPostcodeParticipant" class="btn btn-secondary btn-xs">Add Agent</button></div>
                            <div v-for="(p, index) in herdPostcodeParticipants" :key="'post-'+index" class="flex gap-2 mb-2">
                                <select v-model="p.model" class="input-field text-xs flex-1"><option v-for="m in availableLollmsModels" :key="m.id" :value="m.id">{{ m.name }}</option></select>
                                <select v-model="p.personality" class="input-field text-xs flex-1"><option v-for="pers in allPersonalities" :key="pers.name" :value="pers.name">{{ pers.name }}</option></select>
                                <button @click="removePostcodeParticipant(index)" class="text-red-500 p-1"><IconTrash class="w-4 h-4"/></button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- System & Intelligence Toggles -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="p-4 bg-teal-50 dark:bg-teal-900/10 border border-teal-200 dark:border-teal-800 rounded-xl flex items-center justify-between">
                <div><h3 class="text-sm font-bold">Long-Term Memory</h3><p class="text-xs text-gray-500">Allow AI to save and load facts about you.</p></div>
                <div class="flex items-center gap-3">
                    <label v-if="memoryEnabled" class="flex items-center gap-2 text-[10px] font-black uppercase text-teal-600"><input type="checkbox" v-model="autoMemoryEnabled"><span>Auto</span></label>
                    <label class="toggle-switch"><input type="checkbox" v-model="memoryEnabled"><span class="slider"></span></label>
                </div>
            </div>

            <div class="p-4 bg-indigo-50 dark:bg-indigo-900/10 border border-indigo-200 dark:border-indigo-800 rounded-xl space-y-3">
                <div class="flex items-center justify-between">
                    <div><h3 class="text-sm font-bold">Thinking Mode</h3><p class="text-xs text-gray-500">Enable deep reasoning processes.</p></div>
                    <label class="toggle-switch"><input type="checkbox" v-model="reasoningActivation"><span class="slider"></span></label>
                </div>
                <select v-if="reasoningActivation" v-model="reasoningEffort" class="input-field text-xs w-full"><option value="low">Low Effort</option><option value="medium">Medium Effort</option><option value="high">High Effort</option></select>
            </div>

            <div class="p-4 bg-gray-50 dark:bg-gray-700/20 border dark:border-gray-700 rounded-xl flex items-center justify-between">
                <div><h3 class="text-sm font-bold">Fun Mode 🎉</h3><p class="text-xs text-gray-500">Add humor and emojis to AI output.</p></div>
                <label class="toggle-switch"><input type="checkbox" v-model="funMode"><span class="slider"></span></label>
            </div>

            <div class="p-4 bg-gray-50 dark:bg-gray-700/20 border dark:border-gray-700 rounded-xl flex items-center justify-between">
                <div><h3 class="text-sm font-bold">Tell OS</h3><p class="text-xs text-gray-500">Share your operating system name.</p></div>
                <label class="toggle-switch"><input type="checkbox" v-model="tellOS"><span class="slider"></span></label>
            </div>

            <div class="p-4 bg-gray-50 dark:bg-gray-700/20 border dark:border-gray-700 rounded-xl flex items-center justify-between">
                <div><h3 class="text-sm font-bold">RLM Mode</h3><p class="text-xs text-gray-500">Recursive context processing.</p></div>
                <label class="toggle-switch"><input type="checkbox" v-model="rlmEnabled"><span class="slider"></span></label>
            </div>

            <div class="p-4 bg-gray-50 dark:bg-gray-700/20 border dark:border-gray-700 rounded-xl flex items-center justify-between">
                <div><h3 class="text-sm font-bold">Annotation</h3><p class="text-xs text-gray-500">Allow AI to draw bounding boxes on images.</p></div>
                <label class="toggle-switch"><input type="checkbox" v-model="imageAnnotationEnabled"><span class="slider"></span></label>
            </div>
            
            <div class="p-4 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-xl flex items-center justify-between">
                <div><h3 class="text-sm font-bold">Street View</h3><p class="text-xs text-gray-500">Allow AI to fetch street view images.</p></div>
                <label class="toggle-switch"><input type="checkbox" v-model="streetViewEnabled"><span class="slider"></span></label>
            </div>
        </div>

        <!-- Language and Dynamic Info -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div class="space-y-4">
                <div class="flex items-center justify-between">
                    <h3 class="text-sm font-bold">Force Response Language</h3>
                    <label class="toggle-switch-sm"><input type="checkbox" v-model="forceAiResponseLanguage"><span class="slider-sm"></span></label>
                </div>
                <LanguageSelector v-model="aiResponseLanguage" :include-auto="true" :disabled="!forceAiResponseLanguage" />
            </div>
            
            <div class="space-y-3">
                <div class="flex items-center justify-between">
                    <h3 class="text-sm font-bold">Dynamic Placeholders</h3>
                    <label class="toggle-switch-sm"><input type="checkbox" v-model="shareDynamicInfo"><span class="slider-sm"></span></label>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div v-for="info in staticInfo" :key="info.label" class="p-2 bg-gray-50 dark:bg-gray-900 rounded border dark:border-gray-700 text-[10px] flex justify-between items-center">
                        <span class="text-gray-500">{{ info.label }}</span>
                        <code class="text-blue-500 font-bold">{{ info.placeholder }}</code>
                    </div>
                </div>
            </div>
        </div>

        <!-- Personal Info & Credentials -->
        <div class="section-card bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-sm font-bold text-amber-800 dark:text-amber-200">Personal Info & Credentials</h3>
                <label class="toggle-switch-sm"><input type="checkbox" v-model="sharePersonalInfo"><span class="slider-sm"></span></label>
            </div>
            <textarea v-model="personalInfo" class="input-field w-full h-24" placeholder="Store keys or personal details here..."></textarea>
            <p class="text-[10px] text-amber-700 dark:text-amber-400 mt-2 italic">⚠️ Warning: Information here is sent in the context. Only use with trusted local models.</p>
        </div>

        <!-- Media Generation Features -->
        <div class="p-6 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-2xl space-y-6">
            <div class="flex items-center justify-between">
                <h3 class="font-black uppercase tracking-widest text-gray-400">Media & Document Creation</h3>
                <div class="flex gap-2">
                    <label class="feature-tag" :class="{'active': imageGenerationEnabled}"><input type="checkbox" v-model="imageGenerationEnabled"><span>ImgGen</span></label>
                    <label class="feature-tag" :class="{'active': imageEditingEnabled}"><input type="checkbox" v-model="imageEditingEnabled"><span>ImgEdit</span></label>
                    <label class="feature-tag" :class="{'active': slideMakerEnabled}"><input type="checkbox" v-model="slideMakerEnabled"><span>Slides</span></label>
                    <label class="feature-tag" :class="{'active': noteGenerationEnabled}"><input type="checkbox" v-model="noteGenerationEnabled"><span>Notes</span></label>
                </div>
            </div>

            <div v-if="imageGenerationEnabled" class="space-y-4 animate-in zoom-in-95">
                <div>
                    <label class="text-xs font-bold mb-2 block">Generation System Prompt</label>
                    <textarea v-model="imageGenerationSystemPrompt" class="input-field w-full h-20" placeholder="e.g. High quality, 4k, cinematic..."></textarea>
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium">Auto-activate generated images in context</span>
                    <label class="toggle-switch-sm"><input type="checkbox" v-model="activateGeneratedImages"><span class="slider-sm"></span></label>
                </div>
                
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div><label class="text-[10px] font-bold uppercase text-gray-500">Max Width (px)</label><input type="number" v-model.number="maxImageWidth" class="input-field w-full"></div>
                    <div><label class="text-[10px] font-bold uppercase text-gray-500">Max Height (px)</label><input type="number" v-model.number="maxImageHeight" class="input-field w-full"></div>
                </div>

                <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                    <div class="flex items-center gap-3">
                        <label class="flex items-center gap-2 text-xs font-bold"><input type="checkbox" v-model="compressImages"><span>Compress Uploads (JPEG)</span></label>
                    </div>
                    <div v-if="compressImages" class="flex items-center gap-2">
                        <span class="text-[10px] font-bold text-gray-400">Quality: {{ imageCompressionQuality }}</span>
                        <input type="range" v-model.number="imageCompressionQuality" min="10" max="100" class="w-24">
                    </div>
                </div>
            </div>
        </div>

        <!-- Formatting & Preferences -->
        <div class="space-y-4">
            <div><label class="block text-sm font-bold mb-2">Coding Style Constraints</label><textarea v-model="codingStyle" class="input-field w-full h-24" placeholder="e.g. Use PEP8 for Python, Functional style for JS..."></textarea></div>
            <div><label class="block text-sm font-bold mb-2">Language & Library Preferences</label><textarea v-model="langPrefs" class="input-field w-full h-24" placeholder="e.g. I prefer Tailwind CSS over Bootstrap..."></textarea></div>
            <div><label class="block text-sm font-bold mb-2">General Info / Extra Rules</label><textarea v-model="generalInfo" class="input-field w-full h-32" placeholder="Shared rules for all your conversations..."></textarea></div>
        </div>
    </div>
    
    <div class="px-4 py-4 bg-gray-50 dark:bg-gray-700/30 text-right rounded-b-lg border-t dark:border-gray-700">
        <button @click="handleSaveChanges" class="btn btn-primary" :disabled="!hasChanges || isSaving">
            <IconAnimateSpin v-if="isSaving" class="w-4 h-4 mr-2 animate-spin" />
            {{ isSaving ? 'Saving Changes...' : 'Save Context Settings' }}
        </button>
    </div>
  </div>
</template>

<style scoped>
.section-card { @apply p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm; }
.toggle-switch { @apply relative inline-flex items-center cursor-pointer; }
.toggle-switch input { @apply sr-only; }
.toggle-switch .slider { @apply w-11 h-6 bg-gray-200 dark:bg-gray-700 rounded-full transition-colors; }
.toggle-switch input:checked + .slider { @apply bg-blue-600; }
.toggle-switch .slider:after { @apply content-[''] absolute top-[2px] left-[2px] bg-white border-gray-300 border rounded-full h-5 w-5 transition-all; }
.toggle-switch input:checked + .slider:after { @apply translate-x-full; }

.toggle-switch-sm { @apply relative inline-flex items-center cursor-pointer; }
.toggle-switch-sm input { @apply sr-only; }
.toggle-switch-sm .slider-sm { @apply w-8 h-4 bg-gray-200 dark:bg-gray-700 rounded-full transition-colors; }
.toggle-switch-sm input:checked + .slider-sm { @apply bg-blue-600; }
.toggle-switch-sm .slider-sm:after { @apply content-[''] absolute top-[2px] left-[2px] bg-white rounded-full h-3 w-3 transition-all; }
.toggle-switch-sm input:checked + .slider-sm:after { @apply translate-x-4; }

.tool-toggle { @apply flex items-center gap-2 p-2 border rounded-lg cursor-pointer transition-all border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800; }
.tool-toggle.active { @apply border-blue-500 bg-blue-500/10 text-blue-600; }
.tool-toggle input { @apply sr-only; }

.feature-tag { @apply flex items-center gap-2 px-3 py-1.5 border rounded-full text-[10px] font-black uppercase tracking-widest cursor-pointer transition-all opacity-40 border-gray-300 dark:border-gray-600; }
.feature-tag.active { @apply opacity-100 border-blue-500 text-blue-600 bg-blue-500/5; }
.feature-tag input { @apply sr-only; }

.menu-item { @apply flex items-center w-full px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left; }
.menu-divider { @apply my-1 border-t border-gray-100 dark:border-gray-700; }

.no-scrollbar::-webkit-scrollbar { display: none; }
</style>
