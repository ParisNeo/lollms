<script setup>
import { ref, computed, watch } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { storeToRefs } from 'pinia';
import WysiwygEditor from '../ui/WysiwygEditor.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const MODAL_NAME = 'adminUserEmail';

const { isEnhancingEmail } = storeToRefs(adminStore);
const props = computed(() => uiStore.modalProps);
const user = computed(() => props.value?.user || {});

const subject = ref('');
const body = ref('');
const backgroundColor = ref('#f4f4f8');
const customPrompt = ref('');
const showCustomPrompt = ref(false);

const history = ref([]);
const historyIndex = ref(-1);

const isLoading = ref(false);

const canUndo = computed(() => historyIndex.value > 0);
const canRedo = computed(() => historyIndex.value < history.value.length - 1);

watch(() => user.value.id, (newId) => {
    if (newId) {
        subject.value = '';
        body.value = '';
        backgroundColor.value = '#f4f4f8';
        isLoading.value = false;
        history.value = [];
        historyIndex.value = -1;
        recordHistory(); // Record initial empty state
    }
}, { immediate: true });

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

const isUserEligible = computed(() => {
    return user.value.is_active && user.value.receive_notification_emails && user.value.email;
});

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
        // Error already handled
    }
}

async function handleSubmit() {
    if (!subject.value || !body.value) {
        uiStore.addNotification('Subject and body are required.', 'error');
        return;
    }
    if (!user.value?.id) {
        uiStore.addNotification('No user selected.', 'error');
        return;
    }

    isLoading.value = true;
    try {
        await adminStore.sendEmailToUsers(subject.value, body.value, [user.value.id], backgroundColor.value);
        uiStore.closeModal(MODAL_NAME);
    } catch (error) {
        // Handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        :modal-name="MODAL_NAME"
        :title="`Email User: ${user.username || '...'}`"
        @close="uiStore.closeModal(MODAL_NAME)"
        maxWidthClass="max-w-4xl"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="p-6 space-y-6">
                 <div class="p-3 rounded-md bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600">
                    <p class="text-sm">
                        <span class="font-medium">To:</span> {{ user.username }}
                        <span class="text-gray-500 dark:text-gray-400"><{{ user.email || 'No Email' }}></span>
                    </p>
                    <p v-if="!isUserEligible" class="mt-1 text-xs text-yellow-600 dark:text-yellow-400">
                        Warning: This user may not receive the email.
                    </p>
                </div>
                <div class="flex items-center gap-4">
                    <div class="flex-grow">
                        <label for="email-subject-single" class="block text-sm font-medium">Subject</label>
                        <input id="email-subject-single" v-model="subject" type="text" class="input-field mt-1" required />
                    </div>
                    <div>
                        <label for="email-bg-color-single" class="block text-sm font-medium">BG Color</label>
                        <input id="email-bg-color-single" v-model="backgroundColor" type="color" class="w-20 h-10 mt-1 p-1 border rounded-md" />
                    </div>
                </div>
                <div>
                    <div class="flex items-center justify-between mb-1">
                        <label for="email-body-single" class="block text-sm font-medium">Body</label>
                        <div class="flex items-center gap-2">
                            <button @click="undo" :disabled="!canUndo" type="button" class="toolbar-btn" title="Undo"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l4-4m-4 4l4 4" /></svg></button>
                            <button @click="redo" :disabled="!canRedo" type="button" class="toolbar-btn" title="Redo"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 10h-10a8 8 0 00-8 8v2m18-10l-4-4m4 4l-4 4" /></svg></button>
                        </div>
                    </div>
                    <div class="max-h-[50vh] overflow-y-auto">
                        <WysiwygEditor v-model="body" />
                    </div>
                </div>
                <div>
                    <div class="flex items-center">
                        <input id="show-custom-prompt-single" type="checkbox" v-model="showCustomPrompt" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                        <label for="show-custom-prompt-single" class="ml-2 block text-sm font-medium">Use Custom AI Prompt</label>
                    </div>
                    <textarea v-if="showCustomPrompt" v-model="customPrompt" rows="3" class="input-field mt-2" placeholder="e.g., Rewrite this to be more casual and exciting..."></textarea>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-between items-center w-full">
                <button type="button" @click="handleEnhance" class="btn btn-secondary flex items-center gap-2" :disabled="isEnhancingEmail">
                     <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" :class="{'animate-spin': isEnhancingEmail}" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.898 20.572L16.5 21.75l-.398-1.178a3.375 3.375 0 00-2.3-2.3L12.75 18l1.178-.398a3.375 3.375 0 002.3-2.3L16.5 14.25l.398 1.178a3.375 3.375 0 002.3 2.3l1.178.398-1.178.398a3.375 3.375 0 00-2.3 2.3z" /></svg>
                    <span>{{ isEnhancingEmail ? 'Enhancing...' : 'Enhance with AI' }}</span>
                </button>
                <div class="flex justify-end space-x-3">
                    <button type="button" class="btn btn-secondary" @click="uiStore.closeModal(MODAL_NAME)">Cancel</button>
                    <button type="button" @click="handleSubmit" class="btn btn-primary" :disabled="isLoading || !user.id">
                        {{ isLoading ? 'Sending...' : 'Send Email' }}
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>