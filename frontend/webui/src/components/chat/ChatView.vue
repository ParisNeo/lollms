<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';

// Component Imports
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';

// Asset & Icon Imports
import logoUrl from '../../assets/logo.png';
import IconDataZone from '../../assets/icons/IconDataZone.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';

// --- Store Initialization ---
const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

// --- Component State ---
const isDataZoneVisible = ref(false);
const knowledgeFileInput = ref(null);
const isExtractingText = ref(false);
const activeDataZoneTab = ref('discussion');
const userCodeMirrorEditor = ref(null);
const summaryPrompt = ref(''); // NEW: For guided summary

// --- Data Zone State ---
let discussionSaveDebounceTimer = null;
let userSaveDebounceTimer = null;
let memorySaveDebounceTimer = null;

// --- Computed Properties ---
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const showChatView = computed(() => activeDiscussion.value !== null);

const isSummarizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id] === 'summarize');
const isMemorizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id] === 'memorize');

// --- Reactive Data Zone Management with Computed Properties ---
const discussionDataZone = computed({
    get: () => activeDiscussion.value?.discussion_data_zone || '',
    set: (newVal) => {
        clearTimeout(discussionSaveDebounceTimer);
        discussionSaveDebounceTimer = setTimeout(() => {
            if (activeDiscussion.value) {
                discussionsStore.updateDataZone({ discussionId: activeDiscussion.value.id, content: newVal });
            }
        }, 750);
        // Optimistic update for immediate UI feedback in the store
        if (activeDiscussion.value) {
            discussionsStore.discussions[activeDiscussion.value.id].discussion_data_zone = newVal;
        }
    }
});

const userDataZone = computed({
    get: () => authStore.user?.data_zone || '',
    set: (newVal) => {
        clearTimeout(userSaveDebounceTimer);
        userSaveDebounceTimer = setTimeout(() => {
            authStore.updateDataZone(newVal);
        }, 750);
        // Optimistic update
        if (authStore.user) {
            authStore.user.data_zone = newVal;
        }
    }
});

const personalityDataZone = computed(() => activeDiscussion.value?.personality_data_zone || '');

const memory = computed({
    get: () => activeDiscussion.value?.memory || '',
    set: (newVal) => {
        clearTimeout(memorySaveDebounceTimer);
        memorySaveDebounceTimer = setTimeout(() => {
            authStore.updateMemoryZone(newVal);
        }, 750);
         // Optimistic update
        if (authStore.user) {
            authStore.user.memory = newVal;
        }
    }
});


const combinedDataZoneContent = computed(() => {
    return [
        userDataZone.value ? `### User Data\n${userDataZone.value}` : '',
        discussionDataZone.value ? `### Discussion Data\n${discussionDataZone.value}` : '',
        personalityDataZone.value ? `### Personality Data\n${personalityDataZone.value}` : '',
        memory.value ? `### Long-Term Memory\n${memory.value}` : ''
    ].filter(Boolean).join('\n\n');
});

watch(combinedDataZoneContent, (newCombinedText) => {
    discussionsStore.updateDataZonesTokenCount(newCombinedText);
}, { immediate: true });


// --- Methods ---
async function toggleDataZone() {
    isDataZoneVisible.value = !isDataZoneVisible.value;
    if (isDataZoneVisible.value) {
        uiStore.fetchKeywords();
    }
}

function triggerKnowledgeFileUpload() {
    knowledgeFileInput.value?.click();
}

async function handleKnowledgeFileUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    isExtractingText.value = true;
    const formData = new FormData();
    for (const file of files) { formData.append('files', file); }
    try {
        const response = await apiClient.post('/api/files/extract-text', formData);
        const extractedText = response.data.text;
        
        // This will trigger the computed property's setter
        discussionDataZone.value = discussionDataZone.value ? `${discussionDataZone.value}\n\n${extractedText}` : extractedText;
        
        uiStore.addNotification(`Extracted text from ${files.length} file(s) and added to discussion data zone.`, 'success');
    } finally {
        isExtractingText.value = false;
        if (knowledgeFileInput.value) knowledgeFileInput.value.value = '';
    }
}

function handleSummarize() {
    if (!activeDiscussion.value) return;
    discussionsStore.summarizeDiscussionDataZone(activeDiscussion.value.id, summaryPrompt.value);
}

function handleMemorize() {
    if (!activeDiscussion.value) return;
    discussionsStore.memorizeLTM(activeDiscussion.value.id);
}

function insertPlaceholder(keyword) {
    const view = userCodeMirrorEditor.value?.codeMirrorView;
    if (view) {
        const { from, to } = view.state.selection.main;
        view.dispatch({ changes: { from, to, insert: keyword } });
        view.focus();
    }
}
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-gray-50 dark:bg-gray-900 overflow-hidden">
    <input type="file" ref="knowledgeFileInput" @change="handleKnowledgeFileUpload" multiple class="hidden" accept=".txt,.md,.pdf,.docx,.pptx,.xlsx,.xls, .py, .js, .html, .css, .json, .xml, .c, .cpp, .java">
    <div class="flex-1 flex min-h-0">
        <div class="flex-1 flex flex-col min-w-0 relative">
            <MessageArea v-if="showChatView" class="flex-1 overflow-y-auto min-w-0" />
            <div v-else class="flex-1 flex items-center justify-center text-center p-4">
              <div class="max-w-md">
                <img :src="logoUrl" alt="LoLLMs Logo" class="w-24 h-24 mx-auto mb-4 opacity-50" />
                <h3 class="text-xl font-semibold text-gray-700 dark:text-gray-300">Welcome to LoLLMs Chat</h3>
                <p class="text-gray-500 dark:text-gray-400 mt-2">Start a new conversation or select an existing one to begin.</p>
              </div>
            </div>
            <ChatInput @toggle-data-zone="toggleDataZone" :data-zone-content="combinedDataZoneContent" />
        </div>
        <transition enter-active-class="transition ease-in-out duration-300" enter-from-class="transform translate-x-full" enter-to-class="transform translate-x-0" leave-active-class="transition ease-in-out duration-300" leave-from-class="transform translate-x-0" leave-to-class="transform translate-x-full">
            <aside v-if="isDataZoneVisible && activeDiscussion" class="w-1/3 max-w-md h-full flex flex-col bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700">
                <div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-700">
                    <nav class="-mb-px flex space-x-2 px-4" aria-label="Tabs">
                        <button @click="activeDataZoneTab = 'discussion'" :class="['tab-btn', {'active': activeDataZoneTab === 'discussion'}]" title="Discussion Data">Discussion</button>
                        <button @click="activeDataZoneTab = 'user'" :class="['tab-btn', {'active': activeDataZoneTab === 'user'}]" title="User Data">User</button>
                        <button @click="activeDataZoneTab = 'personality'" :class="['tab-btn', {'active': activeDataZoneTab === 'personality'}]" title="Personality Data">Personality</button>
                        <button @click="activeDataZoneTab = 'ltm'" :class="['tab-btn', {'active': activeDataZoneTab === 'ltm'}]" title="Long-Term Memory">LTM</button>
                    </nav>
                </div>
                <!-- Discussion Data Zone -->
                <div v-show="activeDataZoneTab === 'discussion'" class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                        <div class="flex justify-between items-center">
                            <div>
                                <h3 class="font-semibold flex items-center gap-2"><IconDataZone class="w-5 h-5" /> Discussion Data Zone</h3>
                                <p class="text-xs text-gray-500 mt-1">Context for this discussion only.</p>
                            </div>
                             <button @click="triggerKnowledgeFileUpload" class="btn btn-secondary btn-sm" title="Add text from files" :disabled="isExtractingText"><IconAnimateSpin v-if="isExtractingText" class="w-4 h-4" /><IconPlus v-else class="w-4 h-4" /></button>
                        </div>
                        <div class="mt-4">
                             <textarea v-model="summaryPrompt" rows="2" class="input-field text-sm" placeholder="Optional: Enter a specific prompt for the summary..."></textarea>
                             <div class="flex justify-end mt-2">
                                <button @click="handleSummarize" class="btn btn-secondary btn-sm" title="Summarize content" :disabled="isSummarizing || !discussionDataZone.trim()"><IconSparkles class="w-4 h-4 mr-1.5" :class="{'animate-pulse': isSummarizing}"/>Summarize</button>
                             </div>
                        </div>

                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor v-model="discussionDataZone" class="h-full" /></div>
                </div>
                <!-- User Data Zone -->
                <div v-show="activeDataZoneTab === 'user'" class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0 flex justify-between items-center">
                        <div>
                           <h3 class="font-semibold flex items-center gap-2"><IconUserCircle class="w-5 h-5" /> User Data Zone</h3>
                           <p class="text-xs text-gray-500 mt-1">Context for all of your discussions.</p>
                        </div>
                        <div class="relative group">
                            <button type="button" class="btn btn-secondary btn-sm flex items-center gap-1.5"><IconInfo class="w-4 h-4" /> Insert</button>
                            <div class="absolute bottom-full right-0 mb-2 w-72 p-3 bg-white dark:bg-gray-900 border dark:border-gray-700 rounded-md shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                                <h4 class="font-bold mb-2 text-sm">Dynamic Placeholders</h4>
                                <p class="mb-3 text-xs text-gray-600 dark:text-gray-400">Click to insert a placeholder. It will be replaced with live data when you send a message.</p>
                                <ul v-if="uiStore.keywords.length > 0" class="space-y-2">
                                    <li v-for="kw in uiStore.keywords" :key="kw.keyword">
                                        <button @click.prevent="insertPlaceholder(kw.keyword)" class="w-full text-left p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 pointer-events-auto">
                                            <code class="text-blue-600 dark:text-blue-400 font-semibold">{{ kw.keyword }}</code>
                                            <span class="text-xs text-gray-500 dark:text-gray-400 block">{{ kw.description }}</span>
                                        </button>
                                    </li>
                                </ul>
                                <p v-else class="text-xs text-gray-400 italic">Loading placeholders...</p>
                            </div>
                        </div>
                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor ref="userCodeMirrorEditor" v-model="userDataZone" class="h-full" /></div>
                </div>
                <!-- Personality Data Zone -->
                <div v-show="activeDataZoneTab === 'personality'" class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                        <h3 class="font-semibold flex items-center gap-2"><IconSparkles class="w-5 h-5" /> Personality Data Zone</h3>
                        <p class="text-xs text-gray-500 mt-1">Read-only context from the active personality.</p>
                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor :model-value="personalityDataZone" class="h-full" :options="{ readOnly: true }" /></div>
                </div>
                <!-- Long-Term Memory (LTM) -->
                <div v-show="activeDataZoneTab === 'ltm'" class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0 flex justify-between items-center">
                         <div>
                            <h3 class="font-semibold flex items-center gap-2"><IconThinking class="w-5 h-5" /> Long-Term Memory</h3>
                            <p class="text-xs text-gray-500 mt-1">Facts the AI has learned from conversations.</p>
                        </div>
                        <button @click="handleMemorize" class="btn btn-secondary btn-sm" title="Analyze discussion and memorize new facts" :disabled="isMemorizing"><IconSparkles class="w-4 h-4" :class="{'animate-pulse': isMemorizing}"/></button>
                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor :model-value="memory" class="h-full" :options="{ readOnly: true }" /></div>
                </div>
            </aside>
        </transition>
    </div>
  </div>
</template>

<style scoped>
.tab-btn {
    @apply px-3 py-2 text-sm font-medium border-b-2 transition-colors;
}
.tab-btn.active {
    @apply border-blue-500 text-blue-600 dark:text-blue-400;
}
.tab-btn:not(.active) {
    @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500;
}
</style>