<template>
    <div class="fixed inset-0 z-[100] flex flex-col items-center justify-center p-4 bg-gray-100 dark:bg-gray-900">
        <div class="w-full max-w-md mx-auto bg-white dark:bg-gray-800 rounded-lg shadow-xl overflow-hidden">
            
            <div class="p-6 text-center border-b dark:border-gray-700">
                <div class="flex justify-center items-center gap-4 mb-4">
                    <img src="/logo.png" alt="LoLLMs Logo" class="h-12 w-12">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
                    <div class="h-12 w-12 rounded-md bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
                        <img v-if="appDetails.icon && !iconError" :src="appDetails.icon" @error="iconError = true" alt="App Icon" class="h-full w-full object-cover">
                        <svg v-else class="w-7 h-7 text-gray-500 dark:text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21.75 17.25v-.228a4.5 4.5 0 0 0-.12-1.03l-2.268-9.64a3.375 3.375 0 0 0-3.285-2.602H7.923a3.375 3.375 0 0 0-3.285 2.602l-2.268 9.64a4.5 4.5 0 0 0-.12 1.03v.228m19.5 0a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3m19.5 0a3 3 0 0 0-3-3H5.25a3 3 0 0 0-3 3m16.5 0h.008v.008h-.008v-.008Z" /></svg>
                    </div>
                </div>
                <h1 v-if="!isLoading" class="text-xl font-bold text-gray-800 dark:text-gray-100">
                    Login to <span class="text-blue-600 dark:text-blue-400">{{ appDetails.name }}</span>
                </h1>
                <p v-if="!isLoading" class="text-sm text-gray-500 dark:text-gray-400 mt-1">with your LoLLMs Account</p>
                <p v-if="isLoading" class="text-lg text-gray-500 dark:text-gray-400 animate-pulse">Loading Application Details...</p>
            </div>

            <div v-if="!isLoading && !authStore.isAuthenticated" class="p-6">
                <form @submit.prevent="handleLogin" class="space-y-4">
                    <div>
                        <label for="sso-username" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Username</label>
                        <input v-model="username" type="text" id="sso-username" required class="input-field mt-1 w-full" :disabled="isAuthorizing">
                    </div>
                    <div>
                        <label for="sso-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Password</label>
                        <input v-model="password" type="password" id="sso-password" required class="input-field mt-1 w-full" :disabled="isAuthorizing">
                    </div>
                    <div v-if="errorMessage" class="text-sm text-center p-2 rounded-md bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300">{{ errorMessage }}</div>
                    <button type="submit" class="btn btn-primary w-full" :disabled="isAuthorizing">
                        {{ isAuthorizing ? 'Logging In...' : 'Login & Authorize' }}
                    </button>
                </form>
            </div>
            
            <div v-if="!isLoading && authStore.isAuthenticated && !isAuthorized" class="p-6 space-y-4">
                <p class="text-sm text-center">You are logged in as <strong class="font-medium">{{ authStore.user.username }}</strong>.</p>
                <div v-if="appDetails.sso_user_infos_to_share.length > 0">
                    <p class="text-sm text-gray-600 dark:text-gray-300 mb-2">
                        <strong class="font-semibold text-gray-800 dark:text-gray-100">{{ appDetails.name }}</strong> is requesting access to the following information:
                    </p>
                    <ul class="text-sm list-disc list-inside bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md space-y-1">
                        <li>Username</li>
                        <li v-for="info in appDetails.sso_user_infos_to_share" :key="info">{{ formatScope(info) }}</li>
                    </ul>
                </div>
                 <p v-else class="text-sm text-center text-gray-500 dark:text-gray-400">
                    This application has not requested any personal information beyond your username.
                </p>
                <button @click="handleAuthorize" class="btn btn-primary w-full" :disabled="isAuthorizing">
                    {{ isAuthorizing ? 'Authorizing...' : 'Authorize' }}
                </button>
                 <button @click="handleLogout" class="btn btn-secondary w-full">Logout & Switch Account</button>
            </div>

            <div v-if="fatalError" class="p-6 text-center space-y-4">
                <h2 class="text-lg font-bold text-red-600 dark:text-red-400">Error</h2>
                <p class="text-sm text-gray-600 dark:text-gray-300">{{ fatalError }}</p>
                <router-link to="/" class="btn btn-secondary">Go to Homepage</router-link>
            </div>

        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import apiClient from '../services/api';

const route = useRoute();
const authStore = useAuthStore();

const clientId = route.params.clientId;
const appDetails = ref({});
const isLoading = ref(true);
const iconError = ref(false);
const fatalError = ref('');

const username = ref('');
const password = ref('');
const isAuthorizing = ref(false);
const errorMessage = ref('');
const isAuthorized = ref(false);

function formatScope(scope) {
    return scope.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

async function fetchAppDetails() {
    console.log(`[SSO LOG] Fetching details for client_id: ${clientId}`);
    try {
        const response = await apiClient.get(`/api/sso/app_details/${clientId}`);
        appDetails.value = response.data;
        console.log('[SSO LOG] App details received:', response.data);
    } catch (error) {
        console.error('[SSO LOG] Error fetching app details:', error.response?.data?.detail || error.message);
        fatalError.value = error.response?.data?.detail || 'This application is not configured for SSO.';
    } finally {
        isLoading.value = false;
    }
}

async function handleLogin() {
    isAuthorizing.value = true;
    errorMessage.value = '';
    console.log(`[SSO LOG] Attempting login for user '${username.value}' to authorize client '${clientId}'.`);
    try {
        const tokenData = await authStore.ssoLoginWithPassword(clientId, username.value, password.value);
        if (tokenData?.redirect_uri) {
            isAuthorized.value = true;
            const redirectUrl = `${tokenData.redirect_uri}?token=${tokenData.access_token}`;
            console.log(`[SSO LOG] Login successful. Redirecting to: ${redirectUrl}`);
            window.location.href = redirectUrl;
        } else {
            throw new Error("Redirect URI not found after login.");
        }
    } catch (error) {
        errorMessage.value = error.response?.data?.detail || 'Login failed. Please check your credentials.';
        console.error('[SSO LOG] Login failed:', errorMessage.value);
    } finally {
        isAuthorizing.value = false;
    }
}

async function handleAuthorize() {
    isAuthorizing.value = true;
    errorMessage.value = '';
    console.log(`[SSO LOG] Authorizing client '${clientId}' for logged-in user '${authStore.user.username}'.`);
    try {
        const tokenData = await authStore.ssoAuthorizeApplication(clientId);
        if (tokenData?.redirect_uri) {
            isAuthorized.value = true;
            const redirectUrl = `${tokenData.redirect_uri}?token=${tokenData.access_token}`;
            console.log(`[SSO LOG] Authorization successful. Redirecting to: ${redirectUrl}`);
            window.location.href = redirectUrl;
        } else {
             throw new Error("Redirect URI not found after authorization.");
        }
    } catch (error) {
        fatalError.value = 'Failed to authorize the application. Please try again.';
        console.error('[SSO LOG] Authorization failed:', error);
    } finally {
        isAuthorizing.value = false;
    }
}

function handleLogout() {
    console.log("[SSO LOG] User chose to logout and switch account.");
    authStore.logout();
}

onMounted(() => {
    console.log('[SSO LOG] SSO Login View mounted.');
    authStore.attemptInitialAuth().then(() => {
        fetchAppDetails();
    });
});
</script>