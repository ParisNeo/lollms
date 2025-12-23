<!-- [UPDATE] frontend/webui/src/components/modals/LoginModal.vue -->
<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconLogin from '../../assets/icons/IconLogin.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();

const username = ref('');
const password = ref('');
const isLoading = ref(false);
const errorMessage = ref('');

const usernameInput = ref(null);

const ssoClientConfig = computed(() => authStore.ssoClientConfig);

onMounted(() => {
    if(!authStore.ssoClientConfig.enabled) {
        authStore.fetchSsoClientConfig();
    }
});
function ssoLogin() {
    window.location.href = '/api/sso-client/login';
}


// When the modal becomes active, focus the username input
watch(() => uiStore.activeModal, (newModal) => {
    if (newModal === 'login') {
        nextTick(() => {
            usernameInput.value?.focus();
        });
    }
});

const handleLogin = async () => {
    errorMessage.value = '';
    isLoading.value = true;
    try {
        await authStore.login(username.value, password.value);
        // On success, the authStore will handle fetching user data and closing the modal.
    } catch (error) {
        errorMessage.value = 'Incorrect username or password.';
    } finally {
        isLoading.value = false;
    }
};

const openRegister = () => {
    uiStore.closeModal('login');
    uiStore.openModal('register');
};

const openForgotPassword = () => {
    uiStore.closeModal('login');
    uiStore.openModal('forgotPassword');
};
</script>

<template>
  <GenericModal
    modalName="login"
    title="Welcome Back"
    maxWidthClass="max-w-md"
  >
    <template #body>
      <div class="text-center mb-6">
        <div class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 mb-3">
          <IconLogin class="w-6 h-6" />
        </div>
        <h3 class="text-lg font-medium text-gray-900 dark:text-white">Sign in to your account</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400">Enter your credentials to access your workspace.</p>
      </div>

      <form @submit.prevent="handleLogin" class="space-y-5">
        <div>
          <label for="login-username" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Username or Email</label>
          <div class="mt-1">
            <input
                ref="usernameInput"
                v-model="username"
                type="text"
                id="login-username"
                required
                :disabled="isLoading"
                class="input-field w-full"
                placeholder="Enter username"
                autocomplete="username"
            />
          </div>
        </div>

        <div>
            <label for="login-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Password</label>
            <div class="mt-1">
                <input
                v-model="password"
                type="password"
                id="login-password"
                required
                :disabled="isLoading"
                class="input-field w-full"
                placeholder="Enter password"
                autocomplete="current-password"
                />
            </div>
            <!-- Forgot Password Link moved below input -->
            <div class="mt-2 text-right">
                <a @click.prevent="openForgotPassword" href="#" class="text-sm font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300 transition-colors">
                    Forgot password?
                </a>
            </div>
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

        <div>
          <button type="submit" class="btn btn-primary w-full justify-center py-2.5 text-sm font-semibold shadow-sm hover:shadow transition-all" :disabled="isLoading">
            <span v-if="isLoading" class="flex items-center">
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Signing in...
            </span>
            <span v-else>Sign In</span>
          </button>
        </div>

        <div v-if="ssoClientConfig.enabled" class="relative">
            <div class="absolute inset-0 flex items-center">
                <div class="w-full border-t border-gray-300 dark:border-gray-600"></div>
            </div>
            <div class="relative flex justify-center text-sm">
                <span class="px-2 bg-white dark:bg-gray-800 text-gray-500">Or continue with</span>
            </div>
        </div>

        <button v-if="ssoClientConfig.enabled" @click="ssoLogin" type="button" class="btn btn-secondary w-full justify-center flex items-center gap-3 py-2.5">
            <img v-if="ssoClientConfig.icon_url" :src="ssoClientConfig.icon_url" alt="" class="w-5 h-5">
            {{ ssoClientConfig.display_name }}
        </button>

        <div class="text-sm text-center text-gray-600 dark:text-gray-400 pt-2">
          Don't have an account?
          <a @click.prevent="openRegister" href="#" class="font-semibold text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300 ml-1 transition-colors">
            Register now
          </a>
        </div>
      </form>
    </template>
  </GenericModal>
</template>
