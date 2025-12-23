<!-- frontend/webui/src/components/modals/RegisterModal.vue -->
<script setup>
import { ref, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconUserPlus from '../../assets/icons/IconUserPlus.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();

const username = ref('');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const errorMessage = ref('');

const passwordsMatch = computed(() => password.value === confirmPassword.value);
const isPasswordLongEnough = computed(() => password.value.length >= 8);

const openLoginModal = () => {
    uiStore.closeModal('register');
    uiStore.openModal('login');
};

const handleRegister = async () => {
    errorMessage.value = '';

    if (!username.value || !email.value || !password.value || !confirmPassword.value) {
        errorMessage.value = 'All fields are required.';
        return;
    }
    if (!isPasswordLongEnough.value) {
        errorMessage.value = 'Password must be at least 8 characters long.';
        return;
    }
    if (!passwordsMatch.value) {
        errorMessage.value = 'Passwords do not match.';
        return;
    }

    isLoading.value = true;
    try {
        await authStore.register({
            username: username.value,
            email: email.value,
            password: password.value,
        });
        // Notification is handled by authStore.register
        uiStore.closeModal('register');
        uiStore.openModal('login');
    } catch (error) {
        errorMessage.value = error.response?.data?.detail || 'An unexpected error occurred during registration.';
    } finally {
        isLoading.value = false;
    }
};
</script>

<template>
  <GenericModal
    modalName="register"
    title="Create Account"
    maxWidthClass="max-w-md"
  >
    <template #body>
      <div class="text-center mb-6">
        <div class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400 mb-3">
          <IconUserPlus class="w-6 h-6" />
        </div>
        <h3 class="text-lg font-medium text-gray-900 dark:text-white">Join the Community</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400">Fill in the form below to get started.</p>
      </div>

      <form @submit.prevent="handleRegister" class="space-y-4">
        <div>
          <label for="reg-username" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Username</label>
          <div class="mt-1">
            <input
                v-model="username"
                type="text"
                id="reg-username"
                required
                :disabled="isLoading"
                class="input-field w-full"
                placeholder="Choose a username"
                autocomplete="username"
            />
          </div>
        </div>

        <div>
          <label for="reg-email" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Email Address</label>
          <div class="mt-1">
            <input
                v-model="email"
                type="email"
                id="reg-email"
                required
                :disabled="isLoading"
                class="input-field w-full"
                placeholder="your@email.com"
                autocomplete="email"
            />
          </div>
        </div>

        <div>
          <label for="reg-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Password</label>
            <div class="mt-1">
                <input
                v-model="password"
                type="password"
                id="reg-password"
                required
                :disabled="isLoading"
                class="input-field w-full"
                placeholder="Create a password (min. 8 chars)"
                autocomplete="new-password"
                />
            </div>
             <p v-if="password && !isPasswordLongEnough" class="text-xs text-red-500 mt-1 flex items-center">
                <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
                Too short (min 8 characters)
             </p>
        </div>

        <div>
          <label for="reg-confirm-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Confirm Password</label>
            <div class="mt-1">
                <input
                v-model="confirmPassword"
                type="password"
                id="reg-confirm-password"
                required
                :disabled="isLoading"
                class="input-field w-full"
                placeholder="Confirm your password"
                autocomplete="new-password"
                />
            </div>
            <p v-if="confirmPassword && !passwordsMatch" class="text-xs text-red-500 mt-1 flex items-center">
                <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
                Passwords do not match
            </p>
        </div>

        <div v-if="errorMessage" class="rounded-md bg-red-50 dark:bg-red-900/20 p-3">
             <div class="flex">
                <div class="flex-shrink-0">
                    <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                    </svg>
                </div>
                <div class="ml-3">
                    <h3 class="text-sm font-medium text-red-800 dark:text-red-200">{{ errorMessage }}</h3>
                </div>
            </div>
        </div>

        <div class="pt-2">
            <button type="submit" class="btn btn-primary w-full justify-center py-2.5 text-sm font-semibold shadow-sm hover:shadow transition-all" :disabled="isLoading">
                <span v-if="isLoading" class="flex items-center">
                    <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Creating Account...
                </span>
                <span v-else>Create Account</span>
            </button>
        </div>
        
        <div class="text-sm text-center text-gray-600 dark:text-gray-400 pt-2 border-t dark:border-gray-700 mt-6">
            Already have an account?
            <a @click.prevent="openLoginModal" href="#" class="font-semibold text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300 ml-1 transition-colors">
                Sign in
            </a>
        </div>
      </form>
    </template>
  </GenericModal>
</template>
