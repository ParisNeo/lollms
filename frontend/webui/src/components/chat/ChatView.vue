<script setup>
import { ref, computed, watch } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import ChatHeader from './ChatHeader.vue';
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import logoUrl from '../../assets/logo.png';
import IconScratchpad from '../../assets/icons/IconScratchpad.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';


const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const isDataZoneVisible = ref(false);
const activeScratchpadTab = ref('discussion'); // 'discussion' or 'user'
const knowledgeFileInput = ref(null);
const isExtractingText = ref(false);

// --- Discussion Scratchpad ---
const discussionDataZone = ref('');
let discussionSaveDebounceTimer = null;

// --- User Scratchpad ---
const userDataZone = ref('');
let userSaveDebounceTimer = null;

const showChatView = computed(() => activeDiscussion.value !== null);

// Watch for discussion changes to update the discussion scratchpad
watch(() => activeDiscussion.value?.data_zone, (newVal) => {
    if (newVal !== discussionDataZone.value) {
        discussionDataZone.value = newVal || '';
    }
}, { immediate: true });

// Watch for changes in the discussion scratchpad editor to save them
watch(discussionDataZone, (newVal) => {
    clearTimeout(discussionSaveDebounceTimer);
    discussionSaveDebounceTimer = setTimeout(() => {
        if (activeDiscussion.value && newVal !== activeDiscussion.value.data_zone) {
            discussionsStore.updateDataZone({
                discussionId: activeDiscussion.value.id,
                content: newVal,
            });
        }
    }, 750);
});

// Watch for user scratchpad changes from the auth store
watch(() => authStore.user?.scratchpad, (newVal) => {
    if (newVal !== userDataZone.value) {
        userDataZone.value = newVal || '';
    }
}, { immediate: true, deep: true });

// Watch for changes in the user scratchpad editor to save them
watch(userDataZone, (newVal) => {
    clearTimeout(userSaveDebounceTimer);
    userSaveDebounceTimer = setTimeout(() => {
        if (authStore.user && newVal !== authStore.user.scratchpad) {
            authStore.updateScratchpad(newVal);
        }
    }, 750);
});


function toggleDataZone() {
    isDataZoneVisible.value = !isDataZoneVisible.value;
    if (isDataZoneVisible.value && authStore.user.scratchpad === null) { // Fetch only if not yet fetched
        authStore.fetchScratchpad();
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
    for (const file of files) {
        formData.append('files', file);
    }

    try {
        const response = await apiClient.post('/api/files/extract-text', formData);
        const extractedText = response.data.text;
        
        discussionDataZone.value = discussionDataZone.value
            ? `${discussionDataZone.value}\n\n${extractedText}`
            : extractedText;
        
        uiStore.addNotification(`Extracted text from ${files.length} file(s) and added to scratchpad.`, 'success');
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
    <!-- Hidden file input for knowledge upload -->
    <input 
        type="file" 
        ref="knowledgeFileInput" 
        @change="handleKnowledgeFileUpload" 
        multiple 
        class="hidden"
        accept=".txt,.md,.markdown,.rst,.py,.js,.ts,.java,.c,.cpp,.h,.hpp,.cs,.go,.rs,.php,.rb,.swift,.kt,.html,.css,.scss,.json,.xml,.yaml,.yml,.ini,.toml,.cfg,.log,.sh,.bat,.ps1,.sql,.pdf,.docx,.pptx,.xlsx,.xls"
    >

    <!-- Chat Header -->
    <ChatHeader v-if="activeDiscussion" :discussion="activeDiscussion" />

    <!-- Main Content Area -->
    <div class="flex-1 flex min-h-0">
        <!-- Main Chat Area -->
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
            
            <ChatInput @toggle-data-zone="toggleDataZone" />
        </div>

        <!-- Data Zone Side Panel -->
        <transition
            enter-active-class="transition ease-in-out duration-300"
            enter-from-class="transform translate-x-full"
            enter-to-class="transform translate-x-0"
            leave-active-class="transition ease-in-out duration-300"
            leave-from-class="transform translate-x-0"
            leave-to-class="transform translate-x-full"
        >
            <div v-if="isDataZoneVisible && activeDiscussion" class="w-1/3 max-w-md h-full flex flex-col bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700">
                <!-- User Scratchpad -->
                <div class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                        <h3 class="font-semibold flex items-center gap-2"><IconUserCircle class="w-5 h-5" /> User Scratchpad</h3>
                        <p class="text-xs text-gray-500 mt-1">This content is available in <strong class="text-gray-600 dark:text-gray-300">all</strong> of your discussions.</p>
                    </div>
                    <div class="flex-grow min-h-0 p-2">
                        <CodeMirrorEditor v-model="userDataZone" class="h-full" />
                    </div>
                </div>
                
                <!-- Discussion Scratchpad -->
                <div class="flex-1 flex flex-col min-h-0 border-t-2 border-gray-300 dark:border-gray-700">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0 flex justify-between items-center">
                        <div>
                            <h3 class="font-semibold flex items-center gap-2"><IconScratchpad class="w-5 h-5" /> Discussion Scratchpad</h3>
                            <p class="text-xs text-gray-500 mt-1">This content is only available in this discussion.</p>
                        </div>
                        <button @click="triggerKnowledgeFileUpload" class="btn btn-secondary btn-sm !p-2" title="Add text from files" :disabled="isExtractingText">
                            <IconAnimateSpin v-if="isExtractingText" class="w-4 h-4" />
                            <IconPlus v-else class="w-4 h-4" />
                        </button>
                    </div>
                    <div class="flex-grow min-h-0 p-2">
                        <CodeMirrorEditor v-model="discussionDataZone" class="h-full" />
                    </div>
                </div>
            </div>
        </transition>
    </div>
  </div>
</template>