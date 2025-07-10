<script setup>
import { ref } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const subject = ref('');
const body = ref('');
const isLoading = ref(false);

async function handleSubmit() {
    if (!subject.value || !body.value) {
        uiStore.addNotification('Subject and body are required.', 'error');
        return;
    }
    isLoading.value = true;
    try {
        await adminStore.sendEmailToAllUsers(subject.value, body.value);
        uiStore.closeModal('emailAllUsers');
    } catch (error) {
        // Error is handled by global interceptor
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="emailAllUsers"
        title="Email All Users"
        @close="uiStore.closeModal('emailAllUsers')"
        maxWidthClass="max-w-2xl"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="p-6 space-y-6">
                <div>
                    <label for="email-subject" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Subject</label>
                    <input
                        id="email-subject"
                        v-model="subject"
                        type="text"
                        class="input-field mt-1"
                        required
                    />
                </div>
                <div>
                    <label for="email-body" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Body</label>
                    <textarea
                        id="email-body"
                        v-model="body"
                        rows="10"
                        class="input-field mt-1"
                        required
                        placeholder="You can use HTML tags for formatting."
                    ></textarea>
                </div>
                 <p class="text-xs text-gray-500 dark:text-gray-400">
                    This will send an email to all active users who have opted-in to receive notifications. The email will be sent from the address configured in the Email Settings.
                </p>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end space-x-3">
                <button type="button" class="btn btn-secondary" @click="uiStore.closeModal('emailAllUsers')">Cancel</button>
                <button type="button" @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">
                    {{ isLoading ? 'Sending...' : 'Send Email' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>