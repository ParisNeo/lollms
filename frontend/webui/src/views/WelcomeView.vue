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
    <div class="flex-grow flex flex-col items-center justify-start pt-10 pb-20 sm:py-12 md:justify-center px-4 sm:px-6 relative z-10 w-full max-w-6xl mx-auto min-h-screen">
      
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
        <div class="text-center animate-fade-in-up">
            <h1 class="main-title font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-500 dark:from-blue-400 dark:via-indigo-400 dark:to-blue-300 tracking-tighter mb-4 filter drop-shadow-sm leading-tight" style="font-family: 'Exo 2', sans-serif;">
            {{ welcomeText }}
            </h1>
            <p class="text-base sm:text-xl md:text-2xl lg:text-3xl text-gray-500 dark:text-gray-400 font-extralight max-w-4xl mx-auto leading-tight italic tracking-wide px-4">
            {{ welcomeSlogan }}
            </p>
        </div>

        <!-- Auth Buttons -->
        <div class="mt-10 sm:mt-16 lg:mt-24 flex flex-col sm:flex-row justify-center items-center gap-4 sm:gap-6 w-full max-w-lg mx-auto sm:max-w-none px-4 mb-10">
          <button @click="openLogin" class="btn-welcome w-full sm:w-56 md:w-64 bg-blue-600 hover:bg-blue-700 text-white shadow-xl">Sign In</button>
          <button @click="openRegister" class="btn-welcome w-full sm:w-56 md:w-64 bg-gray-900 hover:bg-black dark:bg-gray-800 dark:hover:bg-gray-700 text-white shadow-lg">Register</button>
          <button v-if="ssoClientConfig.enabled" @click="ssoLogin" class="btn-welcome w-full sm:w-56 md:w-64 bg-white hover:bg-gray-50 text-gray-900 border border-gray-100 shadow-xl">
              <img v-if="ssoClientConfig.icon_url" :src="ssoClientConfig.icon_url" alt="" class="w-5 h-5 sm:w-6 sm:h-6">
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
              <div class="relative flex flex-col bg-white/90 dark:bg-gray-900/90 backdrop-blur-3xl rounded-[1.5rem] sm:rounded-[2.5rem] shadow-2xl border border-white/20 dark:border-gray-800 p-6 sm:p-10 md:p-12 overflow-hidden" :style="funFactStyle">
                  <div class="flex items-center gap-3 sm:gap-6 mb-4 border-b border-gray-100 dark:border-gray-800 pb-4">
                      <span class="text-2xl sm:text-4xl filter drop-shadow-lg">✨</span>
                      <h3 class="font-black text-gray-800 dark:text-gray-100 uppercase tracking-[0.2em] text-[8px] sm:text-[10px] flex-grow text-left">
                            {{ funFactCategory || 'Knowledge Bit' }}
                      </h3>
                      <div class="flex items-center gap-4">
                          <button v-if="isExpanded" @click.stop="authStore.fetchNewFunFact()" class="p-2 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-full text-blue-600 transition-all" :disabled="isFetchingFunFact">
                              <IconAnimateSpin v-if="isFetchingFunFact" class="w-5 h-5 sm:w-7 sm:h-7 animate-spin" />
                              <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 sm:w-7 sm:h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                          </button>
                          <button v-if="isExpanded" @click.stop="toggleExpand" class="p-2 hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 rounded-full transition-all hover:rotate-90">
                              <IconXMark class="w-6 h-6 sm:w-8 sm:h-8" />
                          </button>
                          <span v-else class="text-[8px] sm:text-[9px] font-black text-blue-500 uppercase tracking-[0.2em] animate-pulse">Learn More</span>
                      </div>
                  </div>
                  <div class="max-h-[20vh] sm:max-h-[50vh] overflow-y-auto custom-scrollbar pr-2">
                      <!-- ADDED :key to prevent DOM patching crash -->
                      <MessageContentRenderer :key="funFact" :content="funFact" class="text-sm sm:text-base text-gray-700 dark:text-gray-100" />
                  </div>
              </div>
          </div>
      </div>
    </div>
    
    <!-- Footer -->
    <footer class="relative z-10 w-full py-8 text-center text-[9px] sm:text-[10px] font-black uppercase tracking-[0.3em] text-gray-400 dark:text-gray-600 border-t border-gray-200/10 dark:border-gray-800/10 backdrop-blur-md bg-white/5 dark:bg-black/5 px-4" :class="{'opacity-0 pointer-events-none': isExpanded}">
        <div class="flex flex-col items-center gap-6">
            <div v-if="isHttpsEnabled" class="flex flex-col sm:flex-row gap-4 sm:gap-10">
                <button @click="installCert('windows')" class="footer-link"><IconLock class="w-3.5 h-3.5" /> Trusted Cert (Win)</button>
                <button @click="installCert('linux')" class="footer-link"><IconLock class="w-3.5 h-3.5" /> Trusted Cert (Linux)</button>
            </div>
            <div class="opacity-40"><span>LoLLMs v{{ appVersion }} &middot; ParisNeo 2025</span></div>
        </div>
    </footer>
  </div>
</template>

<style scoped>
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
    .flex-grow { justify-content: flex-start !important; padding-top: 1.5rem !important; }
    .welcome-logo { height: 3.5rem !important; }
    .main-title { font-size: 2rem !important; }
}
</style>
