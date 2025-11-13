<!-- [UPDATE] frontend/webui/src/components/modals/LoginModal.vue -->
<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

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
    title="Sign in to your account"
    maxWidthClass="max-w-md"
  >
    <template #body>
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label for="login-username" class="block text-sm font-medium">Username or Email</label>
          <input
            ref="usernameInput"
            v-model="username"
            type="text"
            id="login-username"
            required
            :disabled="isLoading"
            class="input-field mt-1 w-full"
            placeholder="your-username"
            autocomplete="username"
          />
        </div>

        <div>
            <div class="flex items-center justify-between">
                <label for="login-password" class="block text-sm font-medium">Password</label>
                <div class="text-sm">
                    <a @click.prevent="openForgotPassword" href="#" class="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-500 dark:hover:text-blue-400">
                        Forgot password?
                    </a>
                </div>
            </div>
            <input
              v-model="password"
              type="password"
              id="login-password"
              required
              :disabled="isLoading"
              class="input-field mt-1 w-full"
              placeholder="Your password"
              autocomplete="current-password"
            />
        </div>

        <div v-if="errorMessage" class="text-red-600 text-sm text-center" role="alert">
            {{ errorMessage }}
        </div>

        <div>
          <button type="submit" class="btn btn-primary w-full flex justify-center items-center" :disabled="isLoading">
            <span v-if="isLoading" class="flex items-center">
                <svg class="animate-spin -ml-1 mr-3 h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Signing in...</span>
            </span>
            <span v-else>Login</span>
          </button>
        </div>

        <button v-if="ssoClientConfig.enabled" @click="ssoLogin" type="button" class="btn btn-secondary w-full flex justify-center items-center gap-2 mt-4">
            <img v-if="ssoClientConfig.icon_url" :src="ssoClientConfig.icon_url" alt="" class="w-6 h-6">
            {{ ssoClientConfig.display_name }}
        </button>

        <div class="text-sm text-center text-gray-600 dark:text-gray-300">
          Not a member?
          <a @click.prevent="openRegister" href="#" class="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-500 dark:hover:text-blue-400">
            Create an account
          </a>
        </div>
      </form>
    </template>
  </GenericModal>
</template>
