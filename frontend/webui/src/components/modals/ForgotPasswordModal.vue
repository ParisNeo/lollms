<script setup>
import { ref } from 'vue';
import apiClient from '../../services/api';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';

const uiStore = useUiStore();

const usernameOrEmail = ref('');
const isLoading = ref(false);
const message = ref('');

const handleRequestReset = async () => {
    if (!usernameOrEmail.value) {
        message.value = 'Please enter your username or email address.';
        return;
    }
    isLoading.value = true;
    message.value = '';
    try {
        const response = await apiClient.post('/api/auth/forgot-password', {
            username_or_email: usernameOrEmail.value
        });
        message.value = response.data.message;
        // Do not close modal, so user can see the confirmation message.
    } catch (error) {
        message.value = error.response?.data?.detail || 'An unexpected error occurred.';
    } finally {
        isLoading.value = false;
    }
};

const close = () => {
    uiStore.closeModal('forgotPassword');
    uiStore.openModal('login');
};
</script>

<template>
    <GenericModal modalName="forgotPassword" title="Forgot Password" @close="close">
        <template #body>
            <div class="p-6 space-y-4">
                <p class="text-sm text-gray-600 dark:text-gray-400">
                    Enter your username or email address, and we will initiate the password reset process.
                </p>
                <form @submit.prevent="handleRequestReset" class="space-y-4">
                    <div>
                        <label for="username-or-email" class="block text-sm font-medium">Username or Email</label>
                        <input
                            v-model="usernameOrEmail"
                            type="text"
                            id="username-or-email"
                            required
                            :disabled="isLoading || message.includes('initiated')"
                            class="input-field mt-1 w-full"
                        />
                    </div>
                     <div v-if="message"
                         :class="[message.includes('initiated') ? 'text-green-700 bg-green-100 dark:text-green-300 dark:bg-green-900/50' : 'text-red-700 bg-red-100 dark:text-red-300 dark:bg-red-900/50', 'text-sm text-center p-3 rounded-md']"
                         role="alert">
                        {{ message }}
                    </div>
                    <div class="pt-2">
                        <button type="submit" class="btn btn-primary w-full" :disabled="isLoading || message.includes('initiated')">
                            {{ isLoading ? 'Processing...' : 'Request Reset' }}
                        </button>
                    </div>
                </form>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-start">
                <button type="button" @click="close" class="text-sm font-medium text-blue-600 hover:text-blue-500">
                    ← Back to Login
                </button>
            </div>
        </template>
    </GenericModal>
</template>