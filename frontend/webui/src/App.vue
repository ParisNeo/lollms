<!-- [UPDATE] frontend/webui/src/App.vue -->
<script setup>
import { computed, onMounted, watch, ref } from 'vue';
import { useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useAuthStore } from './stores/auth';
import { useUiStore } from './stores/ui';
import { usePyodideStore } from './stores/pyodide';
import { useTasksStore } from './stores/tasks';
import logoDefault from './assets/logo.png';

// Layouts
import Sidebar from './components/layout/Sidebar.vue';
import GlobalHeader from './components/layout/GlobalHeader.vue';
import AudioPlayer from './components/chat/AudioPlayer.vue';
import NotificationPanel from './components/ui/NotificationPanel.vue';
import ModalContainer from './components/modals/ModalContainer.vue';

// UI Components
import MessageContentRenderer from './components/ui/MessageContentRenderer/MessageContentRenderer.vue';
import IconXMark from './assets/icons/IconXMark.vue';
import IconAnimateSpin from './assets/icons/IconAnimateSpin.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();
const pyodideStore = usePyodideStore();
const tasksStore = useTasksStore();
const route = useRoute();
const { message_font_size } = storeToRefs(uiStore);

const isAuthenticating = computed(() => authStore.isAuthenticating);
const isAuthenticated = computed(() => authStore.isAuthenticated);
const isSidebarOpen = computed(() => uiStore.isSidebarOpen);

const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);
const funFactColor = computed(() => authStore.welcome_fun_fact_color || '#3B82F6');
const funFactCategory = computed(() => authStore.welcome_fun_fact_category);

const isFunFactHanging = ref(false);

const funFactStyle = computed(() => ({
    '--fun-fact-color': funFactColor.value,
    'backgroundColor': isFunFactHanging.value ? 'transparent' : `${funFactColor.value}15`,
    'borderColor': funFactColor.value,
}));

const layoutState = computed(() => {
    if (isAuthenticating.value || isFunFactHanging.value) return 'loading';
    return isAuthenticated.value ? 'authenticated' : 'guest';
});

const showMainSidebar = computed(() => {
    if (!isAuthenticated.value) return false;
    const noSidebarPaths = ['/settings', '/admin', '/datastores', '/friends', '/help', '/profile', '/messages', '/voices-studio', '/image-studio'];
    return !noSidebarPaths.some(path => route.path.startsWith(path));
});

function toggleFactHang() { isFunFactHanging.value = !isFunFactHanging.value; }

onMounted(async () => {
    uiStore.initializeTheme();
    await authStore.attemptInitialAuth();
    uiStore.initializeSidebarState();
    if (isAuthenticated.value) {
        pyodideStore.initialize();
        tasksStore.startPolling();
    }
});

watch(message_font_size, (sz) => { if (sz) document.documentElement.style.setProperty('--message-font-size', `${sz}px`); }, { immediate: true });
</script>

<template>
  <div class="h-screen w-screen overflow-hidden font-sans antialiased text-gray-800 dark:text-gray-100 bg-gray-50 dark:bg-gray-900 flex flex-col">
    
    <!-- Splash Screen -->
    <div v-if="layoutState === 'loading'" class="fixed inset-0 z-[100] flex flex-col items-center justify-center text-center p-6 bg-gray-50 dark:bg-gray-950 transition-all duration-700">
        
        <!-- Optimized Background Decor -->
        <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none">
            <div class="absolute top-[-5%] left-[-5%] w-2/3 h-2/3 rounded-full bg-blue-500/10 blur-[140px] animate-pulse will-change-transform"></div>
            <div class="absolute bottom-[-5%] right-[-5%] w-2/3 h-2/3 rounded-full bg-indigo-500/10 blur-[140px] animate-pulse delay-1000 will-change-transform"></div>
        </div>

        <div v-if="isFunFactHanging" class="absolute inset-0 bg-white/50 dark:bg-black/60 backdrop-blur-md z-10" @click="toggleFactHang"></div>

        <div class="w-full max-w-lg mx-auto relative z-20 transition-all duration-500" :class="{'scale-90 opacity-10 blur-sm pointer-events-none': isFunFactHanging}">
            <div class="flex justify-center mb-10">
                <img :src="logoSrc" alt="Logo" class="h-28 sm:h-36 w-auto object-contain drop-shadow-2xl" />
            </div>
            <h1 class="text-6xl sm:text-7xl font-black text-transparent bg-clip-text bg-gradient-to-br from-blue-600 to-indigo-700 dark:from-blue-400 dark:to-indigo-500 tracking-tighter" style="font-family: 'Exo 2', sans-serif;">
                {{ authStore.welcomeText || 'LoLLMs' }}
            </h1>
            <p class="mt-4 text-xl text-gray-400 dark:text-gray-500 font-medium tracking-wide">
                {{ authStore.welcomeSlogan || 'One tool to rule them all' }}
            </p>
            
            <div class="mt-16 w-full max-w-sm mx-auto">
                <div class="h-1.5 w-full rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden relative shadow-inner">
                    <div class="h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-600 transition-all duration-700 relative" :style="{ width: `${authStore.loadingProgress}%` }">
                         <div class="absolute inset-0 w-full h-full progress-bar-animated opacity-30"></div>
                    </div>
                </div>
                <div class="flex justify-between items-center mt-4">
                    <span class="text-[10px] font-black text-blue-500 uppercase tracking-[0.2em]">{{ authStore.loadingMessage }}</span>
                    <span class="text-sm font-black text-gray-400 dark:text-gray-600 font-mono">{{ authStore.loadingProgress }}%</span>
                </div>
            </div>
        </div>

        <!-- Fun Fact Card -->
        <div v-if="authStore.funFact" class="mt-14 mx-auto w-full transition-all duration-700 cubic-bezier(0.34, 1.56, 0.64, 1) relative z-30"
            :class="isFunFactHanging ? 'max-w-4xl scale-100' : 'max-w-md cursor-pointer group'"
            @click="!isFunFactHanging && toggleFactHang()">
            <div class="p-10 border-l-[12px] rounded-[2rem] text-left shadow-[0_35px_60px_-15px_rgba(0,0,0,0.3)] bg-white/90 dark:bg-gray-800/90 backdrop-blur-xl border border-gray-100 dark:border-gray-700 overflow-hidden" :style="funFactStyle">
                <div class="flex items-center justify-between mb-6">
                    <div class="flex items-center gap-4">
                        <span class="text-4xl filter drop-shadow-md">💡</span>
                        <span class="font-black text-[11px] uppercase tracking-[0.3em]" :style="{ color: funFactColor }">{{ funFactCategory || 'Fact Discovery' }}</span>
                    </div>
                    <button v-if="isFunFactHanging" @click.stop="toggleFactHang" class="p-2 hover:bg-red-50 dark:hover:bg-red-950/30 text-red-500 rounded-full transition-all hover:rotate-90 shadow-sm"><IconXMark class="w-8 h-8" /></button>
                </div>
                <div class="max-h-[60vh] overflow-y-auto custom-scrollbar pr-2">
                    <MessageContentRenderer :content="authStore.funFact" class="text-gray-900 dark:text-gray-100" />
                </div>
                <div v-if="!isFunFactHanging" class="mt-8 text-[9px] text-center text-gray-400 dark:text-gray-500 font-black uppercase tracking-[0.2em] animate-pulse">Tap to expand and stay here</div>
                <div v-if="isFunFactHanging" class="mt-12 flex items-center justify-between border-t border-gray-100 dark:border-gray-700 pt-8">
                    <button @click.stop="authStore.fetchNewFunFact()" class="btn btn-secondary btn-sm px-6" :disabled="authStore.isFetchingFunFact"><IconAnimateSpin v-if="authStore.isFetchingFunFact" class="w-4 h-4 mr-2 animate-spin" />Another Fact</button>
                    <button @click.stop="toggleFactHang" class="btn btn-primary px-10 py-3 text-sm font-black uppercase tracking-widest rounded-xl shadow-xl shadow-blue-500/20">Continue &rarr;</button>
                </div>
            </div>
        </div>
        <footer class="absolute bottom-8 w-full text-center text-[10px] font-black uppercase tracking-[0.4em] text-gray-400 dark:text-gray-600" :class="{'opacity-0 pointer-events-none': isFunFactHanging}">ParisNeo &middot; 2025</footer>    
    </div>

    <!-- Main Layout -->
    <div v-else-if="layoutState === 'authenticated'" class="flex flex-col flex-grow min-h-0 relative overflow-hidden">
      <div class="flex flex-grow min-h-0 relative w-full h-full">
        <div v-if="showMainSidebar" class="absolute md:relative inset-y-0 left-0 z-40 md:z-auto transition-transform duration-300 ease-in-out h-full" :class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'"><Sidebar/></div>
        <div v-if="showMainSidebar && isSidebarOpen" @click="uiStore.toggleSidebar" class="absolute inset-0 bg-black/30 z-30 md:hidden"></div>
        <div class="flex-1 flex flex-col overflow-hidden h-full relative">
          <GlobalHeader /><main class="flex-1 overflow-hidden relative"><router-view /></main>
        </div>
        <ChatSidebar />
      </div>
    </div>
    <div v-else-if="layoutState === 'guest'" class="flex flex-col flex-grow min-h-0"><router-view /></div>

    <ModalContainer />
    <NotificationPanel /><AudioPlayer />
  </div>
</template>

<style>
@keyframes progress-animation { 0% { background-position: 1rem 0; } 100% { background-position: 0 0; } }
.progress-bar-animated { background-image: linear-gradient(45deg, rgba(255, 255, 255, .15) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, .15) 50%, rgba(255, 255, 255, .15) 75%, transparent 75%, transparent); background-size: 1rem 1rem; animation: progress-animation 1s linear infinite; }
</style>
