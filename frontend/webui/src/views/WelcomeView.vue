<!-- [UPDATE] frontend/webui/src/views/WelcomeView.vue -->
<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import apiClient from '../services/api';
import logoDefault from '../assets/logo.png';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconLock from '../assets/icons/IconLock.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();
  
const welcomeText = computed(() => authStore.welcomeText);
const welcomeSlogan = computed(() => authStore.welcomeSlogan);
const funFact = computed(() => authStore.funFact);
const logoSrc = computed(() => authStore.welcome_logo_url);
const funFactColor = computed(() => authStore.welcome_fun_fact_color || '#3B82F6');
const funFactCategory = computed(() => authStore.welcome_fun_fact_category);
const ssoClientConfig = computed(() => authStore.ssoClientConfig);
const isFetchingFunFact = computed(() => authStore.isFetchingFunFact);

const isHttpsEnabled = ref(false);
const appVersion = ref('');

onMounted(async () => {
    if (!authStore.ssoClientConfig.enabled) {
        authStore.fetchSsoClientConfig();
    }
    
    // Check SSL status from public endpoint
    try {
        const res = await apiClient.get('/api/public/ssl-status');
        isHttpsEnabled.value = res.data.is_https_enabled;
    } catch (e) {
        console.error("Failed to check SSL status", e);
    }

    // Fetch App Version
    try {
        const res = await apiClient.get('/api/public/version');
        appVersion.value = res.data.version;
    } catch (e) {
        console.error("Failed to fetch version", e);
    }
});

function ssoLogin() {
    window.location.href = '/api/sso-client/login';
}

const funFactStyle = computed(() => ({
    '--fun-fact-color': funFactColor.value,
    'backgroundColor': `${funFactColor.value}20`,
    'borderColor': funFactColor.value,
}));

const funFactTextStyle = computed(() => ({
    color: funFactColor.value
}));

function openLogin() {
  uiStore.openModal('login');
}
function openRegister() {
  uiStore.openModal('register');
}

function installCert(type) {
    const url = `/api/public/cert/install-script?script_type=${type}`;
    window.open(url, '_blank');
}
</script>

<template>
  <div class="h-screen w-screen bg-gray-100 dark:bg-gray-900 flex flex-col items-center justify-center p-6 relative">
    <div class="text-center w-full max-w-2xl">
      <div class="flex justify-center mb-6">
        <img 
          v-if="logoSrc" 
          :src="logoSrc" 
          alt="Custom Logo" 
          class="h-24 sm:h-28 w-auto object-contain border-4 border-gray-200 dark:border-gray-700 rounded-lg shadow-md" 
          @error="($event.target.src=logoDefault)"
        />
        <img 
          v-else 
          :src="logoDefault" 
          alt="lollms Logo" 
          class="h-24 sm:h-28 w-auto border-4 border-gray-200 dark:border-gray-700 rounded-lg shadow-md"
        >
      </div>
      
      <h1 class="text-5xl sm:text-6xl md:text-8xl font-bold text-yellow-600 dark:text-yellow-400 drop-shadow-lg" style="font-family: 'Exo 2', sans-serif;">
        {{ welcomeText }}
      </h1>
      <p class="mt-3 text-xl sm:text-2xl md:text-3xl text-gray-600 dark:text-gray-300">
        {{ welcomeSlogan }}
      </p>

      <div v-if="funFact" class="mt-10 mx-auto max-w-md">
        <div :title="funFactCategory ? `Category: ${funFactCategory}` : 'Fun Fact'" class="p-4 border-l-4 rounded-lg text-sm text-left text-gray-900 dark:text-gray-100" :style="funFactStyle">
          <span class="font-bold" :style="funFactTextStyle">🤓 {{ funFactCategory || 'Fun Fact' }}:</span> {{ funFact }}
        </div>
        <div class="mt-4">
            <button @click="authStore.fetchNewFunFact()" class="btn btn-secondary btn-sm min-w-[120px]" :disabled="isFetchingFunFact">
                <IconAnimateSpin v-if="isFetchingFunFact" class="w-4 h-4 animate-spin" />
                <span v-else>Next Fun Fact</span>
            </button>
        </div>
      </div>

      <div class="mt-12 flex flex-col sm:flex-row justify-center items-center space-y-4 sm:space-y-0 sm:space-x-4">
        <button @click="openLogin" class="btn btn-primary btn-lg w-full sm:w-auto">
          Sign In
        </button>
        <button @click="openRegister" class="btn btn-secondary btn-lg w-full sm:w-auto">
          Register
        </button>
        <button v-if="ssoClientConfig.enabled" @click="ssoLogin" class="btn btn-secondary btn-lg w-full sm:w-auto flex items-center justify-center gap-2">
            <img v-if="ssoClientConfig.icon_url" :src="ssoClientConfig.icon_url" alt="" class="w-6 h-6">
            {{ ssoClientConfig.display_name }}
        </button>
      </div>
    </div>
    
    <!-- Footer Section -->
    <footer class="absolute bottom-4 w-full flex flex-col items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
        <div v-if="isHttpsEnabled" class="flex gap-4">
            <button @click="installCert('windows')" class="hover:underline flex items-center gap-1 text-gray-600 dark:text-gray-400 hover:text-blue-500 dark:hover:text-blue-400">
                <IconLock class="w-3 h-3" />
                Install Certificate (Windows)
            </button>
            <button @click="installCert('linux')" class="hover:underline flex items-center gap-1 text-gray-600 dark:text-gray-400 hover:text-blue-500 dark:hover:text-blue-400">
                <IconLock class="w-3 h-3" />
                Install Certificate (Linux)
            </button>
        </div>
        <div class="flex items-center gap-1">
            <span>Powered by <a href="https://github.com/ParisNeo/lollms-webui" target="_blank" class="font-semibold hover:underline">LoLLMs</a> v{{ appVersion }} by <a href="https://github.com/ParisNeo" target="_blank" class="font-semibold hover:underline">ParisNeo</a></span>
        </div>
    </footer>
  </div>
</template>
