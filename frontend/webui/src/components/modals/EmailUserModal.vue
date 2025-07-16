<script setup>
import { ref, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import WysiwygEditor from '../ui/WysiwygEditor.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const { isEnhancingEmail } = storeToRefs(adminStore);

const modalProps = computed(() => uiStore.modalData('adminUserEmail'));
const user = computed(() => modalProps.value?.user);
const onSend = computed(() => modalProps.value?.onSend);

const subject = ref('');
const body = ref('');
const backgroundColor = ref('#f4f4f8');
const sendAsText = ref(false);
const customPrompt = ref('');
const showCustomPrompt = ref(false);
const isLoading = ref(false);

watch(user, (newUser) => {
    if (newUser) {
        subject.value = '';
        body.value = '';
        backgroundColor.value = '#f4f4f8';
        sendAsText.value = false;
        customPrompt.value = '';
        showCustomPrompt.value = false;
    }
}, { immediate: true });

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
        }
    } catch (error) {
        // Error handled globally
    }
}

async function handleSubmit() {
    if (!subject.value || !body.value) {
        uiStore.addNotification('Subject and body are required.', 'error');
        return;
    }

    isLoading.value = true;
    try {
        if (onSend.value) {
            await onSend.value({
                subject: subject.value,
                body: body.value,
                backgroundColor: backgroundColor.value,
                sendAsText: sendAsText.value,
            });
        }
        uiStore.closeModal('adminUserEmail');
    } catch (error) {
        // Error handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="adminUserEmail"
        :title="user ? `Email User: ${user.username}` : 'Email User'"
        @close="uiStore.closeModal('adminUserEmail')"
        maxWidthClass="max-w-4xl"
    >
        <template #body>
            <form v-if="user" @submit.prevent="handleSubmit" class="p-6 space-y-6">
                <div class="flex items-center gap-4">
                    <div class="flex-grow">
                        <label for="user-email-subject" class="block text-sm font-medium">Subject</label>
                        <input id="user-email-subject" v-model="subject" type="text" class="input-field mt-1" required />
                    </div>
                    <div>
                        <label for="user-email-bg-color" class="block text-sm font-medium" :class="{'text-gray-400 dark:text-gray-500': sendAsText}">BG Color</label>
                        <input id="user-email-bg-color" v-model="backgroundColor" type="color" class="w-20 h-10 mt-1 p-1 border border-gray-300 dark:border-gray-600 rounded-md" :disabled="sendAsText" />
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium mb-1">Body</label>
                    <WysiwygEditor v-model="body" />
                </div>

                <div class="space-y-4">
                    <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <label for="user-send-as-text" class="text-sm font-medium text-gray-900 dark:text-gray-100">Send as plain text</label>
                        <button @click="sendAsText = !sendAsText" type="button" class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out" :class="sendAsText ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600'">
                            <span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition" :class="sendAsText ? 'translate-x-5' : 'translate-x-0'"></span>
                        </button>
                    </div>
                    <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <label for="user-show-custom-prompt" class="text-sm font-medium text-gray-900 dark:text-gray-100">Use Custom AI Prompt</label>
                        <button @click="showCustomPrompt = !showCustomPrompt" type="button" class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out" :class="showCustomPrompt ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600'">
                            <span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition" :class="showCustomPrompt ? 'translate-x-5' : 'translate-x-0'"></span>
                        </button>
                    </div>
                </div>

                <textarea v-if="showCustomPrompt" v-model="customPrompt" rows="3" class="input-field mt-2" placeholder="e.g., Rewrite this to be more professional..."></textarea>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-between items-center w-full">
                <button type="button" @click="handleEnhance" class="btn btn-secondary flex items-center gap-2" :disabled="isEnhancingEmail || sendAsText">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" :class="{'animate-spin': isEnhancingEmail}" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.898 20.572L16.5 21.75l-.398-1.178a3.375 3.375 0 00-2.3-2.3L12.75 18l1.178-.398a3.375 3.375 0 002.3-2.3L16.5 14.25l.398 1.178a3.375 3.375 0 002.3 2.3l1.178.398-1.178.398a3.375 3.375 0 00-2.3 2.3z" /></svg>
                    <span>{{ isEnhancingEmail ? 'Enhancing...' : 'Enhance with AI' }}</span>
                </button>
                <div class="flex justify-end space-x-3">
                    <button type="button" class="btn btn-secondary" @click="uiStore.closeModal('adminUserEmail')">Cancel</button>
                    <button type="button" @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">
                        {{ isLoading ? 'Sending...' : 'Send Email' }}
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>