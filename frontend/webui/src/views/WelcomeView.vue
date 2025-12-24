<!-- [UPDATE] frontend/webui/src/views/WelcomeView.vue -->
<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import apiClient from '../services/api';
import logoDefault from '../assets/logo.png';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconLock from '../assets/icons/IconLock.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import MessageContentRenderer from '../components/ui/MessageContentRenderer/MessageContentRenderer.vue';

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

// --- Expanded Fact logic ---
const isExpanded = ref(false);

onMounted(async () => {
    if (!authStore.ssoClientConfig.enabled) {
        authStore.fetchSsoClientConfig();
    }
    
    try {
        const res = await apiClient.get('/api/public/ssl-status');
        isHttpsEnabled.value = res.data.is_https_enabled;
    } catch (e) {}

    try {
        const res = await apiClient.get('/api/public/version');
        appVersion.value = res.data.version;
    } catch (e) {}
});

function ssoLogin() {
    window.location.href = '/api/sso-client/login';
}

function toggleExpand() {
    isExpanded.value = !isExpanded.value;
}

const funFactStyle = computed(() => ({
    '--fun-fact-color': funFactColor.value,
    'backgroundColor': isExpanded.value ? 'transparent' : `${funFactColor.value}15`,
    'borderColor': funFactColor.value,
}));

function openLogin() { uiStore.openModal('login'); }
function openRegister() { uiStore.openModal('register'); }
function installCert(type) { window.open(`/api/public/cert/install-script?script_type=${type}`, '_blank'); }
</script>

<template>
  <div class="min-h-screen w-full bg-gray-50 dark:bg-gray-950 flex flex-col relative overflow-hidden selection:bg-blue-500 selection:text-white">
    
    <!-- Ultra Modern Background -->
    <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none transition-all duration-1000" :class="{'opacity-20 blur-3xl scale-110': isExpanded}">
        <div class="absolute top-[-10%] left-[-10%] w-[70%] h-[70%] rounded-full bg-blue-500/10 dark:bg-blue-600/5 blur-[120px] animate-blob"></div>
        <div class="absolute top-[20%] right-[-10%] w-[60%] h-[60%] rounded-full bg-purple-500/10 dark:bg-purple-600/5 blur-[120px] animate-blob animation-delay-2000"></div>
        <div class="absolute bottom-[-10%] left-[10%] w-[70%] h-[70%] rounded-full bg-cyan-500/10 dark:bg-cyan-600/5 blur-[120px] animate-blob animation-delay-4000"></div>
    </div>

    <!-- Modal backdrop for expanded fact -->
    <div v-if="isExpanded" class="absolute inset-0 bg-white/60 dark:bg-black/80 backdrop-blur-2xl z-40 transition-all duration-500" @click="toggleExpand"></div>

    <div class="flex-grow flex flex-col items-center justify-center p-6 relative z-10 w-full max-w-6xl mx-auto">
      
      <!-- Main Branding Section -->
      <div class="text-center w-full animate-fade-in-up transition-all duration-700" :class="{'scale-90 opacity-10 blur-xl pointer-events-none': isExpanded}">
        
        <div class="flex justify-center mb-12">
            <div class="relative group">
                <div class="absolute -inset-4 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-[2.5rem] blur opacity-15 group-hover:opacity-30 transition duration-1000 group-hover:duration-300"></div>
                <div class="relative bg-white dark:bg-gray-900 rounded-[2rem] p-6 ring-1 ring-gray-900/5 shadow-[0_50px_100px_-20px_rgba(0,0,0,0.2)] transition-all duration-500 group-hover:scale-110 group-hover:-rotate-3">
                    <img v-if="logoSrc" :src="logoSrc" alt="Logo" class="h-28 sm:h-40 w-auto object-contain" @error="($event.target.src=logoDefault)" />
                    <img v-else :src="logoDefault" alt="lollms" class="h-28 sm:h-40 w-auto object-contain">
                </div>
            </div>
        </div>
        
        <h1 class="text-7xl sm:text-9xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-500 dark:from-blue-400 dark:via-indigo-400 dark:to-blue-300 tracking-tighter mb-8 filter drop-shadow-sm" style="font-family: 'Exo 2', sans-serif;">
          {{ welcomeText }}
        </h1>
        <p class="text-2xl sm:text-4xl text-gray-500 dark:text-gray-400 font-extralight max-w-4xl mx-auto leading-tight italic tracking-wide">
          {{ welcomeSlogan }}
        </p>

        <!-- Auth Action Cluster -->
        <div class="mt-24 flex flex-col sm:flex-row justify-center items-center gap-8 w-full max-w-2xl mx-auto sm:max-w-none">
          <button @click="openLogin" class="btn-lg-primary w-full sm:w-72 py-6 text-xl tracking-[0.2em] shadow-[0_25px_50px_-12px_rgba(37,99,235,0.4)]">
            Sign In
          </button>
          <button @click="openRegister" class="btn-lg-secondary w-full sm:w-72 py-6 text-xl tracking-[0.2em]">
            Register
          </button>
          <button v-if="ssoClientConfig.enabled" @click="ssoLogin" class="btn-lg-white w-full sm:w-72 py-6 text-xl flex items-center justify-center gap-4">
              <img v-if="ssoClientConfig.icon_url" :src="ssoClientConfig.icon_url" alt="" class="w-7 h-7">
              <span>{{ ssoClientConfig.display_name }}</span>
          </button>
        </div>
      </div>

      <!-- Fun Fact Block (Interactive with Markdown) -->
      <div v-if="funFact" class="mt-20 mx-auto w-full transition-all duration-700 cubic-bezier(0.34, 1.56, 0.64, 1) z-[50]" :class="isExpanded ? 'max-w-4xl fixed inset-0 flex items-center justify-center p-8' : 'max-w-2xl'">
          <div 
            @click="!isExpanded && toggleExpand()"
            class="relative group transform transition-all duration-500 w-full"
            :class="isExpanded ? 'scale-100' : 'cursor-pointer hover:-translate-y-3'"
          >
              <div class="absolute -inset-2 bg-gradient-to-br from-blue-500 to-indigo-700 rounded-[3rem] blur opacity-10 group-hover:opacity-30 transition duration-700"></div>
              <div class="relative flex flex-col bg-white/80 dark:bg-gray-900/80 backdrop-blur-3xl rounded-[3rem] shadow-[0_50px_100px_-20px_rgba(0,0,0,0.5)] border border-white/20 dark:border-gray-800 p-12 sm:p-16 overflow-hidden">
                  <div class="flex items-center gap-6 mb-8 border-b border-gray-100 dark:border-gray-800 pb-8">
                      <span class="text-5xl filter drop-shadow-lg">✨</span>
                      <h3 class="font-black text-gray-800 dark:text-gray-100 uppercase tracking-[0.5em] text-[10px] flex-grow text-left">
                           {{ funFactCategory || 'Knowledge Bit' }}
                      </h3>
                      
                      <div class="flex items-center gap-4">
                          <button v-if="isExpanded" @click.stop="authStore.fetchNewFunFact()" class="p-4 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-full text-blue-600 transition-all hover:scale-110" :disabled="isFetchingFunFact">
                              <IconAnimateSpin v-if="isFetchingFunFact" class="w-8 h-8 animate-spin" />
                              <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                          </button>
                          <button v-if="isExpanded" @click.stop="toggleExpand" class="p-4 hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 rounded-full transition-all hover:rotate-90">
                              <IconXMark class="w-10 h-10" />
                          </button>
                          <span v-else class="text-[10px] font-black text-blue-500 uppercase tracking-[0.3em] animate-pulse">Learn More</span>
                      </div>
                  </div>
                  <div class="max-h-[50vh] overflow-y-auto custom-scrollbar pr-4">
                      <MessageContentRenderer :content="funFact" class="text-gray-700 dark:text-gray-100" />
                  </div>
              </div>
          </div>
      </div>
    </div>
    
    <!-- Footer -->
    <footer class="relative z-10 w-full py-10 text-center text-[10px] font-black uppercase tracking-[0.5em] text-gray-400 dark:text-gray-600 border-t border-gray-200/20 dark:border-gray-800/20 backdrop-blur-md bg-white/10 dark:bg-black/10" :class="{'opacity-0 pointer-events-none': isExpanded}">
        <div class="flex flex-col items-center gap-6">
            <div v-if="isHttpsEnabled" class="flex gap-12">
                <button @click="installCert('windows')" class="footer-link">
                    <IconLock class="w-4 h-4" /> Trusted Cert (Win)
                </button>
                <button @click="installCert('linux')" class="footer-link">
                    <IconLock class="w-4 h-4" /> Trusted Cert (Linux)
                </button>
            </div>
            <div class="opacity-50 hover:opacity-100 transition-opacity">
                <span>LoLLMs v{{ appVersion }} &middot; ParisNeo 2025</span>
            </div>
        </div>
    </footer>
  </div>
</template>

<style scoped>
@keyframes blob {
  0% { transform: translate(0px, 0px) scale(1); }
  33% { transform: translate(40px, -60px) scale(1.15); }
  66% { transform: translate(-30px, 30px) scale(0.9); }
  100% { transform: translate(0px, 0px) scale(1); }
}
.animate-blob { animation: blob 18s infinite ease-in-out; }
.animation-delay-2000 { animation-delay: 3s; }
.animation-delay-4000 { animation-delay: 6s; }

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(40px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in-up { animation: fadeInUp 1s cubic-bezier(0.16, 1, 0.3, 1) forwards; }

.btn-lg-primary {
    @apply bg-blue-600 hover:bg-blue-700 text-white font-black rounded-3xl transition-all transform hover:-translate-y-1 active:translate-y-0 focus:outline-none focus:ring-8 focus:ring-blue-500/20;
}
.btn-lg-secondary {
    @apply bg-gray-900 hover:bg-black dark:bg-gray-800 dark:hover:bg-gray-700 text-white font-black rounded-3xl transition-all transform hover:-translate-y-1 active:translate-y-0 focus:outline-none focus:ring-8 focus:ring-gray-500/20;
}
.btn-lg-white {
    @apply bg-white hover:bg-gray-50 text-gray-900 border border-gray-100 font-black rounded-3xl transition-all transform hover:-translate-y-1 active:translate-y-0 focus:outline-none focus:ring-8 focus:ring-gray-200 shadow-2xl;
}
.footer-link {
    @apply flex items-center gap-3 hover:text-blue-600 dark:hover:text-blue-400 transition-all transform hover:scale-105 cursor-pointer;
}
</style>
