<script setup>
import { ref, computed, watch } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';

const uiStore = useUiStore();

const user = computed(() => uiStore.modalProps?.user);

const newPassword = ref('');
const isLoading = ref(false);
const passwordCopied = ref(false);

const generatePassword = () => {
    const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+~`|}{[]:;?><,./-=";
    let password = "";
    for (let i = 0; i < 16; i++) {
        password += charset.charAt(Math.floor(Math.random() * charset.length));
    }
    newPassword.value = password;
    passwordCopied.value = false; // Reset copied state when new password is generated
};

watch(
    () => uiStore.isModalOpen('resetPassword'),
    (isOpen) => {
        if (isOpen) {
            generatePassword();
        }
    },
    { immediate: true }
);

const copyPassword = () => {
    navigator.clipboard.writeText(newPassword.value).then(() => {
        passwordCopied.value = true;
        setTimeout(() => {
            passwordCopied.value = false;
        }, 2000);
    });
};

async function handleSubmit() {
    if (!user.value || !user.value.id || !newPassword.value) return;

    isLoading.value = true;
    try {
        await apiClient.post(`/api/admin/users/${user.value.id}/reset-password`, { new_password: newPassword.value });
        uiStore.addNotification(`Password for ${user.value.username} has been reset.`, 'success');
        uiStore.closeModal('resetPassword');
    } catch (error) {
        // Error is handled by global interceptor
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal 
        :modal-name="'resetPassword'" 
        :title="user ? `Reset Password for ${user.username}` : 'Reset Password'" 
        @close="uiStore.closeModal('resetPassword')"
        max-width-class="max-w-md"
    >
        <template #body>
            <div v-if="user" class="p-6 space-y-4">
                <p class="text-sm text-gray-600 dark:text-gray-300">
                    A new secure password has been generated. Copy the password and provide it to the user. Once you confirm, the user's old password will no longer work.
                </p>

                <div>
                    <label for="new-password-display" class="block text-sm font-medium text-gray-700 dark:text-gray-200">New Password</label>
                    <div class="mt-1 relative rounded-md shadow-sm">
                        <input 
                            id="new-password-display"
                            type="text" 
                            :value="newPassword" 
                            readonly 
                            class="input-field w-full pr-24 font-mono"
                        />
                        <div class="absolute inset-y-0 right-0 flex items-center">
                             <button @click="generatePassword" type="button" class="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200" title="Generate New Password">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h5M20 20v-5h-5M4 4l16 16" />
                                </svg>
                            </button>
                            <button @click="copyPassword" type="button" class="p-2 mr-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200" title="Copy Password">
                                <svg v-if="!passwordCopied" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end space-x-3">
                <button type="button" class="btn btn-secondary" @click="uiStore.closeModal('resetPassword')">Cancel</button>
                <button type="button" class="btn btn-warning" :disabled="isLoading" @click="handleSubmit">
                    {{ isLoading ? 'Resetting...' : 'Confirm Reset' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>