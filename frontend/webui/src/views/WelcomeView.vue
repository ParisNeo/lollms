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
  <div class="min-h-screen w-full bg-gray-50 dark:bg-gray-900 flex flex-col relative overflow-hidden selection:bg-blue-500 selection:text-white">
    
    <!-- Background Decor -->
    <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        <div class="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] rounded-full bg-blue-400/20 dark:bg-blue-600/10 blur-3xl animate-blob"></div>
        <div class="absolute top-[40%] -right-[10%] w-[40%] h-[40%] rounded-full bg-purple-400/20 dark:bg-purple-600/10 blur-3xl animate-blob animation-delay-2000"></div>
        <div class="absolute -bottom-[20%] left-[20%] w-[50%] h-[50%] rounded-full bg-cyan-400/20 dark:bg-cyan-600/10 blur-3xl animate-blob animation-delay-4000"></div>
    </div>

    <div class="flex-grow flex flex-col items-center justify-center p-6 relative z-10 w-full max-w-4xl mx-auto">
      
      <!-- Main Content -->
      <div class="text-center w-full animate-fade-in-up">
        
        <!-- Logo -->
        <div class="flex justify-center mb-8">
            <div class="relative group">
                <div class="absolute -inset-1 bg-gradient-to-r from-blue-600 to-cyan-600 rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-1000 group-hover:duration-200"></div>
                <div class="relative bg-white dark:bg-gray-800 rounded-xl p-4 ring-1 ring-gray-900/5 shadow-xl transition-transform duration-300 group-hover:scale-105">
                    <img 
                      v-if="logoSrc" 
                      :src="logoSrc" 
                      alt="Custom Logo" 
                      class="h-24 sm:h-32 w-auto object-contain" 
                      @error="($event.target.src=logoDefault)"
                    />
                    <img 
                      v-else 
                      :src="logoDefault" 
                      alt="lollms Logo" 
                      class="h-24 sm:h-32 w-auto object-contain"
                    >
                </div>
            </div>
        </div>
        
        <!-- Text -->
        <h1 class="text-5xl sm:text-7xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-500 dark:from-blue-400 dark:to-cyan-300 tracking-tight mb-4 drop-shadow-sm" style="font-family: 'Exo 2', sans-serif;">
          {{ welcomeText }}
        </h1>
        <p class="text-xl sm:text-2xl text-gray-600 dark:text-gray-300 font-light max-w-2xl mx-auto leading-relaxed">
          {{ welcomeSlogan }}
        </p>

        <!-- Fun Fact Card -->
        <div v-if="funFact" class="mt-12 mx-auto max-w-xl perspective w-full">
            <div class="relative group cursor-default transform transition-all hover:-translate-y-1 duration-300">
                <div class="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-purple-600 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-500"></div>
                <div class="relative flex flex-col bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-100 dark:border-gray-700 p-6">
                    <div class="flex items-center gap-3 mb-3 border-b border-gray-100 dark:border-gray-700 pb-3">
                        <span class="text-2xl">💡</span>
                        <h3 class="font-bold text-gray-800 dark:text-gray-100 uppercase tracking-wider text-xs flex-grow text-left">
                             {{ funFactCategory || 'Did you know?' }}
                        </h3>
                        <button 
                            @click="authStore.fetchNewFunFact()" 
                            class="text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors flex items-center gap-1"
                            :disabled="isFetchingFunFact"
                            title="Get another fact"
                        >
                            <IconAnimateSpin v-if="isFetchingFunFact" class="w-4 h-4 animate-spin" />
                            <span v-else>Next &rarr;</span>
                        </button>
                    </div>
                    <p class="text-gray-600 dark:text-gray-300 text-lg leading-relaxed text-left font-serif italic">
                        "{{ funFact }}"
                    </p>
                </div>
            </div>
        </div>

        <!-- Auth Actions -->
        <div class="mt-16 flex flex-col sm:flex-row justify-center items-center gap-4 animate-fade-in-up animation-delay-200 w-full max-w-md mx-auto sm:max-w-none">
          <button @click="openLogin" class="btn-lg-primary w-full sm:w-auto min-w-[160px] shadow-lg shadow-blue-500/30">
            Sign In
          </button>
          <button @click="openRegister" class="btn-lg-secondary w-full sm:w-auto min-w-[160px]">
            Register
          </button>
          <button v-if="ssoClientConfig.enabled" @click="ssoLogin" class="btn-lg-white w-full sm:w-auto min-w-[160px] flex items-center justify-center gap-2">
              <img v-if="ssoClientConfig.icon_url" :src="ssoClientConfig.icon_url" alt="" class="w-5 h-5">
              <span>{{ ssoClientConfig.display_name }}</span>
          </button>
        </div>

      </div>
    </div>
    
    <!-- Footer -->
    <footer class="relative z-10 w-full py-6 text-center text-xs text-gray-500 dark:text-gray-400 border-t border-gray-200/50 dark:border-gray-800/50 backdrop-blur-sm bg-white/30 dark:bg-black/20">
        <div class="flex flex-col items-center gap-3">
            <div v-if="isHttpsEnabled" class="flex gap-6">
                <button @click="installCert('windows')" class="footer-link">
                    <IconLock class="w-3 h-3" /> Windows Cert
                </button>
                <button @click="installCert('linux')" class="footer-link">
                    <IconLock class="w-3 h-3" /> Linux Cert
                </button>
            </div>
            <div class="flex items-center gap-1 opacity-70 hover:opacity-100 transition-opacity">
                <span>Powered by <a href="https://github.com/ParisNeo/lollms-webui" target="_blank" class="font-bold hover:text-blue-500 transition-colors">LoLLMs</a> v{{ appVersion }}</span>
            </div>
        </div>
    </footer>
  </div>
</template>

<style scoped>
/* Custom animations */
@keyframes blob {
  0% { transform: translate(0px, 0px) scale(1); }
  33% { transform: translate(30px, -50px) scale(1.1); }
  66% { transform: translate(-20px, 20px) scale(0.9); }
  100% { transform: translate(0px, 0px) scale(1); }
}
.animate-blob {
  animation: blob 10s infinite;
}
.animation-delay-2000 {
  animation-delay: 2s;
}
.animation-delay-4000 {
  animation-delay: 4s;
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in-up {
  animation: fadeInUp 0.8s ease-out forwards;
}
.animation-delay-200 {
  animation-delay: 0.2s;
}

/* Custom Button Styles */
.btn-lg-primary {
    @apply px-8 py-3.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-all transform hover:-translate-y-0.5 active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-blue-500/30;
}
.btn-lg-secondary {
    @apply px-8 py-3.5 bg-gray-800 hover:bg-gray-900 dark:bg-gray-700 dark:hover:bg-gray-600 text-white font-bold rounded-xl transition-all transform hover:-translate-y-0.5 active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-gray-500/30;
}
.btn-lg-white {
    @apply px-8 py-3.5 bg-white hover:bg-gray-50 text-gray-900 border border-gray-200 font-bold rounded-xl transition-all transform hover:-translate-y-0.5 active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-gray-200 shadow-sm;
}
.footer-link {
    @apply flex items-center gap-1.5 hover:text-blue-600 dark:hover:text-blue-400 transition-colors font-medium cursor-pointer;
}
</style>
