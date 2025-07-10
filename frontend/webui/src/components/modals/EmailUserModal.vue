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
const { modalData } = storeToRefs(uiStore);

const subject = ref('');
const body = ref('');
const backgroundColor = ref('#f4f4f8');
const isLoading = ref(false);

// Safely access the user from modal data
const user = computed(() => modalData.value[MODAL_NAME]?.user || {});

// Reset state when the modal opens with a new user
watch(() => user.value.id, (newId) => {
    if (newId) {
        subject.value = '';
        body.value = '';
        backgroundColor.value = '#f4f4f8';
        isLoading.value = false;
    }
});

const isUserEligible = computed(() => {
    return user.value.is_active && user.value.receive_notification_emails && user.value.email;
});

async function handleEnhance() {
    if (!subject.value && !body.value) {
        uiStore.addNotification('Please provide a subject or body to enhance.', 'warning');
        return;
    }
    try {
        const enhanced = await adminStore.enhanceEmail(subject.value, body.value, backgroundColor.value);
        if (enhanced) {
            subject.value = enhanced.subject;
            body.value = enhanced.body;
            backgroundColor.value = enhanced.background_color || backgroundColor.value;
        }
    } catch (error) {
        // Error already handled by store/interceptor
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
        // The admin store now uses the global error handler
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
        maxWidthClass="max-w-3xl"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="p-6 space-y-6">
                 <div class="p-3 rounded-md bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600">
                    <p class="text-sm text-gray-700 dark:text-gray-300">
                        <span class="font-medium">To:</span> {{ user.username }}
                        <span class="text-gray-500 dark:text-gray-400"><{{ user.email || 'No Email' }}></span>
                    </p>
                    <p v-if="!isUserEligible" class="mt-1 text-xs text-yellow-600 dark:text-yellow-400">
                        Warning: This user may not receive the email because their account is inactive, has no email, or they have opted out of notifications.
                    </p>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div class="sm:col-span-2">
                        <label for="email-subject" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Subject</label>
                        <input id="email-subject" v-model="subject" type="text" class="input-field mt-1" required />
                    </div>
                    <div>
                        <label for="email-bg-color" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Background</label>
                        <input id="email-bg-color" v-model="backgroundColor" type="color" class="w-full h-10 mt-1 p-1 border border-gray-300 dark:border-gray-600 rounded-md cursor-pointer" />
                    </div>
                </div>
                <div class="flex flex-col">
                    <label for="email-body" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Body</label>
                    <div class="max-h-[50vh] overflow-y-auto">
                        <WysiwygEditor v-model="body" />
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-between items-center w-full">
                <button type="button" @click="handleEnhance" class="btn btn-secondary flex items-center gap-2" :disabled="isEnhancingEmail">
                     <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" :class="{'animate-spin': isEnhancingEmail}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.898 20.572L16.5 21.75l-.398-1.178a3.375 3.375 0 00-2.3-2.3L12.75 18l1.178-.398a3.375 3.375 0 002.3-2.3L16.5 14.25l.398 1.178a3.375 3.375 0 002.3 2.3l1.178.398-1.178.398a3.375 3.375 0 00-2.3 2.3z" />
                    </svg>
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