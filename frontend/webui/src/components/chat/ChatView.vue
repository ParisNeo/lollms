<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';

// Component Imports
import ChatHeader from './ChatHeader.vue';
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


// --- Store Initialization ---
const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

// --- Component State ---
const isDataZoneVisible = ref(false);
const knowledgeFileInput = ref(null);
const isExtractingText = ref(false);

// --- Data Zone State ---
const discussionDataZone = ref('');
const userDataZone = ref('');
let discussionSaveDebounceTimer = null;
let userSaveDebounceTimer = null;

// --- Keyword Help State ---
const keywords = ref([]);
const isLoadingKeywords = ref(false);

// --- Computed Properties ---
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const generationInProgress = computed(() => discussionsStore.generationInProgress);
const showChatView = computed(() => activeDiscussion.value !== null);

// Concatenates both data zones to be passed to ChatInput for token counting.
const combinedDataZoneContent = computed(() => {
    const userContent = userDataZone.value || '';
    const discussionContent = discussionDataZone.value || '';
    if (!userContent && !discussionContent) return '';
    return `### User Data\n${userContent}\n\n### Discussion Data\n${discussionContent}`.trim();
});

// --- Watchers for State Synchronization ---

/**
 * The primary watcher that reacts to changes in the active discussion.
 * This ensures the Data Zone panels are always in sync with the selected chat.
 */
watch(() => activeDiscussion.value?.id, (newId, oldId) => {
    // This watcher now only triggers when the discussion ID changes.
    if (newId !== oldId) {
        discussionDataZone.value = activeDiscussion.value?.data_zone || '';
        userDataZone.value = authStore.user?.data_zone || '';
    }
}, { immediate: true });


/**
 * Watches the local `discussionDataZone` ref for user input and saves it
 * back to the store after a delay (debouncing) to prevent excessive API calls.
 */
watch(discussionDataZone, (newVal) => {
    clearTimeout(discussionSaveDebounceTimer);
    discussionSaveDebounceTimer = setTimeout(() => {
        if (activeDiscussion.value && newVal !== activeDiscussion.value.data_zone) {
            discussionsStore.updateDataZone({
                discussionId: activeDiscussion.value.id,
                content: newVal,
            });
        }
    }, 750); // 750ms delay
});

/**
 * Watches the local `userDataZone` ref and saves it to the backend via the auth store,
 * also using debouncing.
 */
watch(userDataZone, (newVal) => {
    clearTimeout(userSaveDebounceTimer);
    userSaveDebounceTimer = setTimeout(() => {
        if (authStore.user && newVal !== authStore.user.data_zone) {
            authStore.updateDataZone(newVal);
        }
    }, 750); // 750ms delay
});


// --- Methods ---

/**
 * Toggles the visibility of the Data Zone side panel.
 * Fetches initial user data and keywords if the panel is being opened for the first time.
 */
async function toggleDataZone() {
    isDataZoneVisible.value = !isDataZoneVisible.value;
    if (isDataZoneVisible.value) {
        if (authStore.user.data_zone === null) {
            await authStore.fetchDataZone();
            userDataZone.value = authStore.user.data_zone || '';
        }
        await fetchKeywords();
    }
}

/**
 * Fetches the list of available dynamic keywords for the help tooltip.
 */
async function fetchKeywords() {
    if (keywords.value.length > 0 || isLoadingKeywords.value) return;
    isLoadingKeywords.value = true;
    try {
        const response = await apiClient.get('/api/help/keywords');
        keywords.value = response.data;
    } catch (error) {
        console.error("Failed to fetch keywords:", error);
    } finally {
        isLoadingKeywords.value = false;
    }
}

/**
 * Programmatically clicks the hidden file input to open the file selection dialog.
 */
function triggerKnowledgeFileUpload() {
    knowledgeFileInput.value?.click();
}

/**
 * Handles the file upload process, sending files to the backend for text extraction
 * and appending the result to the discussion's data zone.
 */
async function handleKnowledgeFileUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    isExtractingText.value = true;
    const formData = new FormData();
    for (const file of files) {
        formData.append('files', file);
    }

    try {
        const response = await apiClient.post('/api/files/extract-text', formData);
        const extractedText = response.data.text;
        
        discussionDataZone.value = discussionDataZone.value
            ? `${discussionDataZone.value}\n\n${extractedText}`
            : extractedText;
        
        uiStore.addNotification(`Extracted text from ${files.length} file(s) and added to data zone.`, 'success');
    } catch (error) {
        // Error is handled by the global API interceptor
    } finally {
        isExtractingText.value = false;
        if (knowledgeFileInput.value) knowledgeFileInput.value.value = ''; // Reset file input
    }
}
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-gray-50 dark:bg-gray-900 overflow-hidden">
    <!-- Hidden file input for document text extraction -->
    <input 
        type="file" 
        ref="knowledgeFileInput" 
        @change="handleKnowledgeFileUpload" 
        multiple 
        class="hidden"
        accept=".txt,.md,.markdown,.rst,.py,.js,.ts,.java,.c,.cpp,.h,.hpp,.cs,.go,.rs,.php,.rb,.swift,.kt,.html,.css,.scss,.json,.xml,.yaml,.yml,.ini,.toml,.cfg,.log,.sh,.bat,.ps1,.sql,.pdf,.docx,.pptx,.xlsx,.xls"
    >

    <ChatHeader v-if="activeDiscussion" />

    <div class="flex-1 flex min-h-0">
        <!-- Main Chat Area: Shows MessageArea or a welcome screen -->
        <div class="flex-1 flex flex-col min-w-0 relative">
            <MessageArea v-if="showChatView" class="flex-1 overflow-y-auto min-w-0" />
            
            <div v-else class="flex-1 flex items-center justify-center text-center p-4">
              <div class="max-w-md">
                <img :src="logoUrl" alt="LoLLMs Logo" class="w-24 h-24 mx-auto mb-4 opacity-50" />
                <h3 class="text-xl font-semibold text-gray-700 dark:text-gray-300">Welcome to LoLLMs Chat</h3>
                <p class="text-gray-500 dark:text-gray-400 mt-2">
                  Start a new conversation or select an existing one to begin.
                </p>
              </div>
            </div>
            
            <ChatInput @toggle-data-zone="toggleDataZone" :data-zone-content="combinedDataZoneContent" />
        </div>

        <!-- Data Zone Side Panel (collapsible) -->
        <transition
            enter-active-class="transition ease-in-out duration-300"
            enter-from-class="transform translate-x-full"
            enter-to-class="transform translate-x-0"
            leave-active-class="transition ease-in-out duration-300"
            leave-from-class="transform translate-x-0"
            leave-to-class="transform translate-x-full"
        >
            <aside v-if="isDataZoneVisible && activeDiscussion" class="w-1/3 max-w-md h-full flex flex-col bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700">
                
                <!-- User Data Zone Section -->
                <div class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                        <h3 class="font-semibold flex items-center gap-2"><IconUserCircle class="w-5 h-5" /> User Data Zone</h3>
                        <p class="text-xs text-gray-500 mt-1">This content is available in <strong class="text-gray-600 dark:text-gray-300">all</strong> of your discussions.</p>
                        
                    </div>
                    
                    <div class="flex-grow min-h-0 p-2">
                        <CodeMirrorEditor v-model="userDataZone" class="h-full" />
                    </div>
                    <div class="relative group">
                        <IconInfo class="w-5 h-5 text-gray-400 cursor-help" />
                        <div class="absolute bottom-full right-0 mb-2 w-64 p-2 bg-black/80 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                            <h4 class="font-bold mb-1">Dynamic Keywords</h4>
                            <p class="mb-2">These keywords will be replaced with live data when you send a message.</p>
                            <ul v-if="keywords.length > 0" class="space-y-1">
                                <li v-for="kw in keywords" :key="kw.keyword">
                                    <code class="text-yellow-300">{{ kw.keyword }}</code> - <span class="text-gray-300">{{ kw.description }}</span>
                                </li>
                            </ul>
                            <p v-else class="text-gray-300">Loading keywords...</p>
                        </div>
                    </div>
                </div>
                
                <!-- Discussion Data Zone Section -->
                <div class="flex-1 flex flex-col min-h-0 border-t-2 border-gray-300 dark:border-gray-700">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0 flex justify-between items-center">
                        <div>
                            <h3 class="font-semibold flex items-center gap-2"><IconDataZone class="w-5 h-5" /> Discussion Data Zone</h3>
                            <p class="text-xs text-gray-500 mt-1">This content is only available in this discussion.</p>
                        </div>
                        <div class="flex items-center gap-2">
                            <button @click="triggerKnowledgeFileUpload" class="btn btn-secondary btn-sm !p-2" title="Add text from files" :disabled="isExtractingText">
                                <IconAnimateSpin v-if="isExtractingText" class="w-4 h-4" />
                                <IconPlus v-else class="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                    <div class="flex-grow min-h-0 p-2">
                        <CodeMirrorEditor v-model="discussionDataZone" class="h-full" />
                    </div>
                </div>
            </aside>
        </transition>
    </div>
  </div>
</template>