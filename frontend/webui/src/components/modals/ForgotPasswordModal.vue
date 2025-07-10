<script setup>
import { ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import GenericModal from '../ui/GenericModal.vue';
import appLogo from '../../assets/logo.png';

const uiStore = useUiStore();

const usernameOrEmail = ref('');
const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');

const handleRequestReset = async () => {
  errorMessage.value = '';
  successMessage.value = '';

  if (!usernameOrEmail.value) {
    errorMessage.value = 'Please enter your username or email address.';
    return;
  }

  isLoading.value = true;
  try {
    const response = await apiClient.post('/api/auth/forgot-password', {
      username_or_email: usernameOrEmail.value,
    });
    successMessage.value = response.data.message;
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'An unexpected error occurred.';
  } finally {
    isLoading.value = false;
  }
};

const closeAndOpenLogin = () => {
  uiStore.closeModal('forgotPassword');
  uiStore.openModal('login');
};
</script>

<template>
  <GenericModal
    modalName="forgotPassword"
    title="Forgot Your Password?"
    maxWidthClass="max-w-md"
    @close="uiStore.closeModal('forgotPassword')"
  >
    <template #body>
      <div class="flex justify-center mb-6">
        <img :src="appLogo" alt="Application Logo" class="h-16 w-auto" />
      </div>

      <div v-if="successMessage" class="text-center p-4">
        <p class="text-green-700 dark:text-green-300">{{ successMessage }}</p>
        <p class="text-sm text-gray-600 dark:text-gray-400 mt-2">
            Please check your email or contact an administrator for the next steps.
        </p>
      </div>

      <form v-else @submit.prevent="handleRequestReset" class="space-y-4">
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Enter the username or email address associated with your account, and we will start the recovery process.
        </p>
        <div>
          <label for="recovery-id" class="block text-sm font-medium">Username or Email</label>
          <input
            v-model="usernameOrEmail"
            type="text"
            id="recovery-id"
            required
            :disabled="isLoading"
            class="input-field mt-1 w-full"
            placeholder="e.g., your_username or you@example.com"
          />
        </div>

        <div v-if="errorMessage" class="text-red-600 text-sm text-center p-2 bg-red-100 dark:bg-red-900/50 rounded-md" role="alert">
          {{ errorMessage }}
        </div>

        <div class="pt-2">
          <button type="submit" class="btn btn-primary w-full" :disabled="isLoading">
            {{ isLoading ? 'Submitting...' : 'Request Password Reset' }}
          </button>
        </div>
      </form>
    </template>

    <template #footer>
      <div class="text-center text-sm">
        <button @click="closeAndOpenLogin" class="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300">
          Back to Login
        </button>
      </div>
    </template>
  </GenericModal>
</template>