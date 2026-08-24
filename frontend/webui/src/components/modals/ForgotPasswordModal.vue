<script setup>
import { ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();

const usernameOrEmail = ref('');
const isSubmitting = ref(false);
const isSubmitted = ref(false);

async function handleSubmit() {
    if (!usernameOrEmail.value.trim()) return;
    isSubmitting.value = true;
    try {
        const response = await apiClient.post('/api/auth/forgot-password', {
            username_or_email: usernameOrEmail.value.trim()
        });
        isSubmitted.value = true;
        uiStore.addNotification(response.data.message || 'Password reset process initiated.', 'info', 6000);
    } catch (error) {
        const msg = error.response?.data?.detail || 'An error occurred during password reset.';
        uiStore.addNotification(msg, 'error');
    } finally {
        isSubmitting.value = false;
    }
}

function openLogin() {
    uiStore.closeModal('forgotPassword');
    uiStore.openModal('login');
}
</script>

<template>
  <GenericModal modalName="forgotPassword" title="Reset Password" maxWidthClass="max-w-md">
    <template #body>
      <div v-if="isSubmitted" class="space-y-4 py-4 text-center animate-in fade-in">
        <div class="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 text-blue-600 rounded-full flex items-center justify-center mx-auto text-xl">
          ✉️
        </div>
        <h4 class="font-bold text-gray-900 dark:text-gray-100">Request Sent</h4>
        <p class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed px-4">
          If an account exists with that username or email address, instructions have been dispatched according to server mail settings.
        </p>
        <div class="pt-2">
          <button @click="openLogin" class="btn btn-primary w-full py-2 font-bold">
            Back to Sign In
          </button>
        </div>
      </div>

      <form v-else @submit.prevent="handleSubmit" class="space-y-4 py-2">
        <p class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
          Enter your registered username or email address. We'll send you a link to reset your password.
        </p>

        <div>
          <label class="label">Username or Email</label>
          <input 
            v-model="usernameOrEmail" 
            type="text" 
            class="input-field mt-1" 
            placeholder="Username or email"
            required 
            autofocus 
          />
        </div>

        <div class="pt-2">
          <button type="submit" class="btn btn-primary w-full py-2.5 font-bold flex items-center justify-center gap-2 shadow-lg" :disabled="isSubmitting || !usernameOrEmail.trim()">
            <IconAnimateSpin v-if="isSubmitting" class="w-4 h-4 animate-spin" />
            <span>{{ isSubmitting ? 'Sending Link...' : 'Send Reset Link' }}</span>
          </button>
        </div>

        <div class="text-center pt-2">
          <button type="button" @click="openLogin" class="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline">
            Back to Sign In
          </button>
        </div>
      </form>
    </template>
    <template #footer>
      <div></div>
    </template>
  </GenericModal>
</template>