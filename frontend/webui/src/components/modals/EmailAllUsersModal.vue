<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { storeToRefs } from 'pinia';
import WysiwygEditor from '../ui/WysiwygEditor.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const { allUsers, isEnhancingEmail } = storeToRefs(adminStore);

const subject = ref('');
const body = ref('');
const backgroundColor = ref('#f4f4f8');
const customPrompt = ref('');
const showCustomPrompt = ref(false);
const sendAsText = ref(false);

const history = ref([]);
const historyIndex = ref(-1);

const isLoading = ref(false);
const selectedUserIds = ref([]);
const selectAll = ref(true);

const canUndo = computed(() => historyIndex.value > 0);
const canRedo = computed(() => historyIndex.value < history.value.length - 1);

const eligibleUsers = computed(() => {
    return allUsers.value.filter(u => u.is_active && u.receive_notification_emails && u.email);
});

onMounted(() => {
    if (allUsers.value.length === 0) {
        adminStore.fetchAllUsers();
    }
    selectedUserIds.value = eligibleUsers.value.map(u => u.id);
    recordHistory(); 
});

watch(selectAll, (newValue) => {
    if (newValue) {
        selectedUserIds.value = eligibleUsers.value.map(u => u.id);
    } else {
        selectedUserIds.value = [];
    }
});

watch([subject, body, backgroundColor], () => {
    recordHistory();
});

function recordHistory() {
    const currentContent = {
        subject: subject.value,
        body: body.value,
        backgroundColor: backgroundColor.value
    };
    if (history.value.length > 0 && JSON.stringify(currentContent) === JSON.stringify(history.value[historyIndex.value])) {
        return;
    }
    history.value.splice(historyIndex.value + 1);
    history.value.push(currentContent);
    historyIndex.value = history.value.length - 1;
}

function applyHistoryState(state) {
    subject.value = state.subject;
    body.value = state.body;
    backgroundColor.value = state.backgroundColor;
}

function undo() {
    if (canUndo.value) {
        historyIndex.value--;
        applyHistoryState(history.value[historyIndex.value]);
    }
}

function redo() {
    if (canRedo.value) {
        historyIndex.value++;
        applyHistoryState(history.value[historyIndex.value]);
    }
}

async function handleEnhance() {
    if (!subject.value && !body.value) {
        uiStore.addNotification('Please provide a subject or body to enhance.', 'warning');
        return;
    }
    try {
        const enhanced = await adminStore.enhanceEmail(subject.value, body.value, backgroundColor.value, customPrompt.value);
        if (enhanced) {
            subject.value = enhanced.subject;
            body.value = enhanced.body;
            backgroundColor.value = enhanced.background_color || backgroundColor.value;
            recordHistory();
        }
    } catch (error) {
    }
}

async function handleSubmit() {
    if (!subject.value || !body.value) {
        uiStore.addNotification('Subject and body are required.', 'error');
        return;
    }
    if (selectedUserIds.value.length === 0) {
        uiStore.addNotification('Please select at least one user to email.', 'error');
        return;
    }

    isLoading.value = true;
    try {
        await adminStore.sendEmailToUsers(subject.value, body.value, selectedUserIds.value, backgroundColor.value, sendAsText.value);
        uiStore.closeModal('emailAllUsers');
    } catch (error) {
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="emailAllUsers"
        title="Email Users"
        @close="uiStore.closeModal('emailAllUsers')"
        maxWidthClass="max-w-6xl"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="p-6 space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="space-y-6 md:col-span-2">
                        <div class="flex items-center gap-4">
                            <div class="flex-grow">
                                <label for="email-subject" class="block text-sm font-medium">Subject</label>
                                <input id="email-subject" v-model="subject" type="text" class="input-field mt-1" required />
                            </div>
                            <div>
                                <label for="email-bg-color" class="block text-sm font-medium" :class="{'text-gray-400 dark:text-gray-500': sendAsText}">BG Color</label>
                                <input id="email-bg-color" v-model="backgroundColor" type="color" class="w-20 h-10 mt-1 p-1 border border-gray-300 dark:border-gray-600 rounded-md" :disabled="sendAsText" />
                            </div>
                        </div>
                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <label class="block text-sm font-medium">Body</label>
                                <div class="flex items-center gap-2">
                                    <button @click="undo" :disabled="!canUndo" type="button" class="toolbar-btn" title="Undo"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l4-4m-4 4l4 4" /></svg></button>
                                    <button @click="redo" :disabled="!canRedo" type="button" class="toolbar-btn" title="Redo"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 10h-10a8 8 0 00-8 8v2m18-10l-4-4m4 4l-4 4" /></svg></button>
                                </div>
                            </div>
                            <WysiwygEditor v-model="body" />
                        </div>
                        <div class="space-y-4">
                            <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                                <label for="send-as-text" class="text-sm font-medium text-gray-900 dark:text-gray-100">Send as plain text</label>
                                <button @click="sendAsText = !sendAsText" type="button" class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800" :class="sendAsText ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600'">
                                    <span class="sr-only">Use plain text</span>
                                    <span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out" :class="sendAsText ? 'translate-x-5' : 'translate-x-0'"></span>
                                </button>
                            </div>
                             <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                                <label for="show-custom-prompt" class="text-sm font-medium text-gray-900 dark:text-gray-100">Use Custom AI Prompt</label>
                                <button @click="showCustomPrompt = !showCustomPrompt" type="button" class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800" :class="showCustomPrompt ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600'">
                                    <span class="sr-only">Use Custom AI Prompt</span>
                                    <span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out" :class="showCustomPrompt ? 'translate-x-5' : 'translate-x-0'"></span>
                                </button>
                            </div>
                        </div>
                        <textarea v-if="showCustomPrompt" v-model="customPrompt" rows="3" class="input-field mt-2" placeholder="e.g., Rewrite this to be more casual and exciting..."></textarea>
                    </div>

                    <div class="space-y-4">
                        <h4 class="text-sm font-medium">Recipients ({{ selectedUserIds.length }}/{{ eligibleUsers.length }})</h4>
                        <div class="relative">
                            <div class="flex items-center p-2 border-b dark:border-gray-600">
                                <input id="select-all-users" type="checkbox" v-model="selectAll" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                                <label for="select-all-users" class="ml-3 block text-sm font-medium">Select All</label>
                            </div>
                            <div class="max-h-96 overflow-y-auto border dark:border-gray-600 rounded-b-md">
                                <div v-if="eligibleUsers.length > 0" class="divide-y dark:divide-gray-600">
                                    <div v-for="user in eligibleUsers" :key="user.id" class="p-2 flex items-center">
                                        <input :id="`user-${user.id}`" type="checkbox" :value="user.id" v-model="selectedUserIds" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                                        <label :for="`user-${user.id}`" class="ml-3 text-sm">
                                            <span class="font-medium">{{ user.username }}</span> ({{ user.email }})
                                        </label>
                                    </div>
                                </div>
                                <div v-else class="p-4 text-center text-sm text-gray-500">
                                    No eligible users found.
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-between items-center w-full">
                <button type="button" @click="handleEnhance" class="btn btn-secondary flex items-center gap-2" :disabled="isEnhancingEmail || sendAsText">
                     <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" :class="{'animate-spin': isEnhancingEmail}" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.898 20.572L16.5 21.75l-.398-1.178a3.375 3.375 0 00-2.3-2.3L12.75 18l1.178-.398a3.375 3.375 0 002.3-2.3L16.5 14.25l.398 1.178a3.375 3.375 0 002.3 2.3l1.178.398-1.178.398a3.375 3.375 0 00-2.3 2.3z" /></svg>
                    <span>{{ isEnhancingEmail ? 'Enhancing...' : 'Enhance with AI' }}</span>
                </button>
                <div class="flex justify-end space-x-3">
                    <button type="button" class="btn btn-secondary" @click="uiStore.closeModal('emailAllUsers')">Cancel</button>
                    <button type="button" @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">
                        {{ isLoading ? 'Sending...' : 'Send Email' }}
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>