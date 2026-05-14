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

function ssoLogin() { window.location.href = '/api/sso-client/login'; }
function toggleExpand() { isExpanded.value = !isExpanded.value; }

const funFactStyle = computed(() => {
    const style = {
        '--fun-fact-color': funFactColor.value,
        'borderColor': funFactColor.value,
    };
    // Only apply the subtle tinted background to the collapsed card
    if (!isExpanded.value) {
        style.backgroundColor = `${funFactColor.value}10`;
    }
    return style;
});

function openLogin() { uiStore.openModal('login'); }
function openRegister() { uiStore.openModal('register'); }
function installCert(type) { window.open(`/api/public/cert/install-script?script_type=${type}`, '_blank'); }
</script>

<template>
  <div class="min-h-screen w-full bg-gray-50 dark:bg-gray-950 flex flex-col relative overflow-x-hidden overflow-y-auto selection:bg-blue-500 selection:text-white">
    
    <!-- 1. FIXED BACKGROUND LAYER -->
    <div class="fixed inset-0 z-0 overflow-hidden pointer-events-none transition-all duration-1000" :class="{'blur-3xl opacity-20 scale-110': isExpanded}">
        <div class="absolute top-[-10%] left-[-10%] w-[100%] h-[70%] rounded-full bg-blue-500/10 dark:bg-blue-600/5 blur-[120px] animate-blob"></div>
        <div class="absolute top-[20%] right-[-10%] w-[80%] h-[60%] rounded-full bg-purple-500/10 dark:bg-purple-600/5 blur-[120px] animate-blob animation-delay-2000"></div>
    </div>

    <!-- 2. MODAL BACKDROP (Appears between background and expanded card) -->
    <div v-if="isExpanded" class="fixed inset-0 bg-white/40 dark:bg-black/60 backdrop-blur-xl z-40 transition-all duration-500" @click="toggleExpand"></div>

    <!-- 3. MAIN UI CONTENT -->
    <div class="grow flex flex-col items-center justify-start pt-10 pb-20 sm:py-12 md:justify-center px-4 sm:px-6 relative z-10 w-full max-w-6xl mx-auto min-h-screen">
      
      <!-- BRANDING & ACTIONS (This container blurs when a fact is expanded) -->
      <div class="w-full flex flex-col items-center transition-all duration-700" :class="{'scale-90 opacity-10 blur-2xl pointer-events-none': isExpanded}">
        
        <!-- Logo -->
        <div class="flex justify-center mb-6 sm:mb-10 lg:mb-12">
            <div class="relative group">
                <div class="absolute -inset-2 sm:-inset-4 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-[1.5rem] sm:rounded-[2rem] blur opacity-15"></div>
                <div class="relative bg-white dark:bg-gray-900 rounded-[1.5rem] sm:rounded-[2rem] p-3 sm:p-6 shadow-xl">
                    <img v-if="logoSrc" :src="logoSrc" alt="Logo" class="welcome-logo h-16 sm:h-24 md:h-32 lg:h-40 w-auto object-contain" @error="($event.target.src=logoDefault)" />
                    <img v-else :src="logoDefault" alt="lollms" class="welcome-logo h-16 sm:h-24 md:h-32 lg:h-40 w-auto object-contain">
                </div>
            </div>
        </div>
        
        <!-- Title & Slogan -->
        <div class="text-center animate-fade-in-up max-w-5xl mx-auto mb-12">
            <h1 class="splash-title">
              {{ welcomeText }}
            </h1>
            <p class="welcome-slogan opacity-60">
              {{ welcomeSlogan }}
            </p>
        </div>

        <!-- Auth Buttons -->
        <div class="mt-16 lg:mt-24 flex flex-col sm:flex-row justify-center items-center gap-6 w-full max-w-4xl px-4 mb-10">
          <button @click="openLogin" class="welcome-btn w-full sm:w-64 bg-blue-600 text-white">Sign In</button>
          <button @click="openRegister" class="welcome-btn w-full sm:w-64 bg-gray-950 dark:bg-white dark:text-gray-950 text-white">Register</button>
          <button v-if="ssoClientConfig.enabled" @click="ssoLogin" class="welcome-btn w-full sm:w-64 bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-100 dark:border-gray-700">
              <img v-if="ssoClientConfig.icon_url" :src="ssoClientConfig.icon_url" alt="" class="w-5 h-5">
              <span>{{ ssoClientConfig.display_name }}</span>
          </button>
        </div>

      </div>

      <!-- FUN FACT CARD (Sits outside the blur container, on top of the backdrop) -->
      <div v-if="funFact" class="mx-auto w-full transition-all duration-700 cubic-bezier(0.34, 1.56, 0.64, 1)" 
           :class="isExpanded ? 'fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-8' : 'relative z-20 mt-8 sm:mt-12 max-w-lg lg:max-w-2xl px-2'">
          <div 
            @click="!isExpanded && toggleExpand()"
            class="relative group transform transition-all duration-500 w-full"
            :class="isExpanded ? 'scale-100 max-w-4xl animate-fade-in-up' : 'cursor-pointer hover:-translate-y-1'"
          >
              <div class="absolute -inset-1 bg-gradient-to-br from-blue-500 to-indigo-700 rounded-[1.5rem] sm:rounded-[2.5rem] blur opacity-10 group-hover:opacity-20 transition duration-700"></div>
              <div class="relative flex flex-col bg-white dark:bg-gray-900 rounded-[2rem] shadow-2xl border border-gray-200/50 dark:border-gray-700/50 p-8 sm:p-12 overflow-hidden" :style="funFactStyle">
                  <div class="flex items-start justify-between mb-8">
                      <div class="flex flex-col gap-1">
                          <span class="modal-tag !mb-0">{{ funFactCategory || 'Knowledge Bit' }}</span>
                          <div class="flex items-center gap-2">
                             <span class="text-xl">✨</span>
                             <span v-if="!isExpanded" class="text-[9px] font-black text-blue-500 uppercase tracking-widest animate-pulse">Discovery awaits</span>
                          </div>
                      </div>
                      
                      <div class="flex items-center gap-3">
                          <button v-if="isExpanded" @click.stop="authStore.fetchNewFunFact()" class="modal-close-btn" :disabled="isFetchingFunFact">
                              <IconAnimateSpin v-if="isFetchingFunFact" class="w-5 h-5 animate-spin" />
                              <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                          </button>
                          <button v-if="isExpanded" @click.stop="toggleExpand" class="modal-close-btn !text-red-500">
                              <IconXMark class="w-6 h-6" />
                          </button>
                      </div>
                  </div>

                  <div class="max-h-[50vh] overflow-y-auto custom-scrollbar">
                      <MessageContentRenderer :key="funFact" :content="funFact" class="text-gray-800 dark:text-gray-100" />
                  </div>
              </div>
          </div>
      </div>
    </div>
    
    <!-- Enhanced Loading Footer -->
    <footer class="relative z-10 w-full max-w-2xl mx-auto py-12 px-6" :class="{'opacity-0': isExpanded}">
        <div class="flex flex-col gap-4">
            <div class="flex items-end justify-between">
                <div class="flex flex-col gap-1">
                    <span class="splash-loading-label">System Initialization</span>
                    <span class="text-[10px] font-mono text-gray-400 italic">Loading AI models & personalities...</span>
                </div>
                <span class="text-[10px] font-black text-gray-400">50%</span>
            </div>
            
            <div class="splash-progress-track">
                <div class="splash-progress-fill" style="width: 50%"></div>
            </div>

            <div class="flex justify-center gap-8 mt-6 opacity-30">
                <div class="text-[8px] font-black uppercase tracking-[0.3em] text-gray-400">v{{ appVersion }}</div>
                <div class="text-[8px] font-black uppercase tracking-[0.3em] text-gray-400">ParisNeo &copy; 2025</div>
            </div>
        </div>
    </footer>
  </div>
</template>

<style scoped>
@reference "tailwindcss";

@keyframes blob {
  0% { transform: translate(0px, 0px) scale(1); }
  33% { transform: translate(30px, -40px) scale(1.1); }
  66% { transform: translate(-20px, 20px) scale(0.95); }
  100% { transform: translate(0px, 0px) scale(1); }
}
.animate-blob { animation: blob 18s infinite ease-in-out; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.animate-fade-in-up { animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
.main-title { font-size: clamp(2.2rem, 10vw + 0.5rem, 7rem); }
.btn-welcome { @apply flex items-center justify-center gap-3 py-3.5 sm:py-5 text-sm sm:text-base font-black uppercase tracking-widest rounded-2xl sm:rounded-3xl transition-all transform hover:-translate-y-1 active:translate-y-0 focus:outline-none focus:ring-8 focus:ring-blue-500/10; }
.footer-link { @apply flex items-center justify-center gap-2 sm:gap-3 hover:text-blue-600 dark:hover:text-blue-400 transition-all transform hover:scale-105 cursor-pointer; }

@media (max-height: 550px) {
    .grow { justify-content: flex-start !important; padding-top: 1.5rem !important; }
    .welcome-logo { height: 3.5rem !important; }
    .main-title { font-size: 2rem !important; }
}
</style>
