<script setup>
import { ref } from 'vue';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();

const usernameOrEmail = ref('');
const isLoading = ref(false);
const message = ref('');
const errorMessage = ref('');

const handleSubmit = async () => {
  isLoading.value = true;
  message.value = '';
  errorMessage.value = '';
  try {
    const response = await apiClient.post('/api/auth/forgot-password', {
      username_or_email: usernameOrEmail.value,
    });
    message.value = response.data.message || 'If an account with that username or email exists, a password reset link has been sent.';
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'An error occurred. Please try again.';
  } finally {
    isLoading.value = false;
  }
};

const openLoginModal = () => {
  uiStore.closeModal('forgotPassword');
  uiStore.openModal('login');
};
</script>

<template>
  <GenericModal modalName="forgotPassword" title="Forgot Password" maxWidthClass="max-w-md">
    <template #body>
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Enter your username or email address and we'll send you a link to reset your password.
        </p>
        <div>
          <label for="usernameOrEmail" class="block text-sm font-medium">Username or Email</label>
          <input
            v-model="usernameOrEmail"
            type="text"
            id="usernameOrEmail"
            required
            class="input-field mt-1 w-full"
            placeholder="Enter username or email"
            autocomplete="username"
          />
        </div>
        <div v-if="message" class="text-green-500 text-sm">
          {{ message }}
        </div>
        <div v-if="errorMessage" class="text-red-500 text-sm">
          {{ errorMessage }}
        </div>
        <button
          type="submit"
          class="btn btn-primary w-full"
          :disabled="isLoading"
        >
          <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2" />
          {{ isLoading ? 'Sending...' : 'Send Reset Link' }}
        </button>
        <p class="text-center text-sm text-gray-500 dark:text-gray-400">
          Remember your password?
          <button
            type="button"
            @click="openLoginModal"
            class="text-blue-600 hover:underline dark:text-blue-400"
          >
            Back to Sign In
          </button>
        </p>
      </form>
    </template>
  </GenericModal>
</template>