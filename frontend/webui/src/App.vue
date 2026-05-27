<script setup>
import { computed, onMounted, watch, ref, defineAsyncComponent } from 'vue';
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
import ChatSidebar from './components/chat/ChatSidebar.vue';
import AudioPlayer from './components/chat/AudioPlayer.vue';
import NotificationPanel from './components/ui/NotificationPanel.vue';
import ModalContainer from './components/modals/ModalContainer.vue';
import ImageViewerModal from './components/ui/ImageViewerModal.vue';
import ConnectionOverlay from './components/ui/ConnectionOverlay.vue';
import MaintenanceOverlay from './components/ui/MaintenanceOverlay.vue';


// Async Modals
const SlideshowModal = defineAsyncComponent(() => import('./components/modals/SlideshowModal.vue'));
const CommandOutputModal = defineAsyncComponent(() => import('./components/modals/CommandOutputModal.vue'));
const ArtefactImportWizardModal = defineAsyncComponent(() => import('./components/modals/ArtefactImportWizardModal.vue'));
const ArtefactViewerModal = defineAsyncComponent(() => import('./components/modals/ArtefactViewerModal.vue'));
const NotebookWizardModal = defineAsyncComponent(() => import('./components/modals/NotebookWizardModal.vue'));
const WhatsNextModal = defineAsyncComponent(() => import('./components/modals/WhatsNextModal.vue'));

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
const user = computed(() => authStore.user);
const wsConnected = computed(() => authStore.wsConnected);
const isMaintenanceMode = computed(() => uiStore.isMaintenanceMode);
const isConnectionLost = computed(() => uiStore.isConnectionLost);

const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);
const funFactColor = computed(() => authStore.welcome_fun_fact_color || '#3B82F6');
const funFactCategory = computed(() => authStore.welcome_fun_fact_category);

const isFunFactHanging = ref(false);
const isReconnecting = ref(false);
const hasConnectedOnce = ref(false); // Track if we ever connected successfully to suppress startup overlay

const funFactStyle = computed(() => {
    const style = {
        '--fun-fact-color': funFactColor.value,
        'borderColor': funFactColor.value,
    };
    // Only apply the subtle tinted background to the collapsed card
    if (!isFunFactHanging.value) {
        style.backgroundColor = `${funFactColor.value}10`;
    }
    return style;
});

const layoutState = computed(() => {
    // Admins can bypass the maintenance overlay if they are already logged in
    if (isMaintenanceMode.value && !authStore.isAdmin) return 'maintenance';
    if (isAuthenticating.value || isFunFactHanging.value) return 'loading';
    return isAuthenticated.value ? 'authenticated' : 'guest';
});

const funnyStatusHint = computed(() => {
    const prog = authStore.loadingProgress;
    if (prog <= 15) return "Feeding the server hamsters...";
    if (prog <= 30) return "Reticulating splines...";
    if (prog <= 45) return "Convincing the AI not to escape the sandbox...";
    if (prog <= 60) return "Downloading extra sarcasm protocols...";
    if (prog <= 75) return "Brewing espresso for the GPU...";
    if (prog <= 90) return "Calibrating flux-capacitor coordinates...";
    return "Finalizing world-domination formulas...";
});

const showMainSidebar = computed(() => {
    if (!isAuthenticated.value) return false;
    const noSidebarPaths = ['/settings', '/admin', '/friends', '/help', '/profile', '/messages', '/voices-studio', '/image-studio'];
    return !noSidebarPaths.some(path => route.path.startsWith(path));
});

function toggleFactHang() { isFunFactHanging.value = !isFunFactHanging.value; }

onMounted(async () => {
    // 1. Start Auth/Connection check immediately (Async)
    const authPromise = authStore.attemptInitialAuth();

    // 2. Initialize UI (Synchronous)
    uiStore.initializeTheme();
    uiStore.initializeSidebarState();

    // 3. Await Auth Result
    await authPromise;

    if (isAuthenticated.value) {
        pyodideStore.initialize();
        tasksStore.startPolling();
    }
});

// Watch for connection restoration to re-initialize UI state
let isSyncing = false;
watch(wsConnected, async (newVal, oldVal) => {
    if (newVal) {
        if (!hasConnectedOnce.value) {
            hasConnectedOnce.value = true;
        } 
        else if (oldVal === false && isAuthenticated.value && !isSyncing) {
            isSyncing = true;
            isReconnecting.value = true;
            try {
                console.log("[App] Connection restored. Re-initializing...");
                await authStore.refreshUser(); 
                tasksStore.startPolling();
                uiStore.addNotification("Server connection restored.", "success");
            } catch (e) {
                console.error("[App] Re-initialization failed:", e);
            } finally {
                setTimeout(() => {
                    isReconnecting.value = false;
                    isSyncing = false;
                }, 1000);
            }
        }
    }
});

// Watch for first login to show terms/welcome modal
watch(user, (newUser) => {
    if (newUser && newUser.first_login_done === false) {
        uiStore.openModal('whatsNext');
    }
}, { immediate: true });

watch(message_font_size, (sz) => { if (sz) document.documentElement.style.setProperty('--message-font-size', `${sz}px`); }, { immediate: true });
</script>

<template>
  <div class="h-screen w-screen overflow-hidden font-sans antialiased text-text-main bg-bg-app flex flex-col transition-colors duration-500">

    <!-- Maintenance Overlay -->
    <MaintenanceOverlay v-if="layoutState === 'maintenance'" />

    <!-- Editorial Connection HUD (Floating Pill) -->
    <Transition
        enter-active-class="transition-all duration-700 ease-out"
        enter-from-class="opacity-0 -translate-y-10 scale-95"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition-all duration-500 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-10 scale-95"
    >
        <div v-if="((!wsConnected || isConnectionLost) && isAuthenticated && hasConnectedOnce && layoutState !== 'maintenance') || isReconnecting" 
             class="fixed top-6 left-1/2 -translate-x-1/2 z-[100] pointer-events-none">
            <div class="px-6 py-3 rounded-full border shadow-2xl backdrop-blur-xl flex items-center gap-4 transition-all duration-500"
                 :class="isReconnecting ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-600' : 'bg-rose-500/10 border-rose-500/20 text-rose-600'">
                <div class="relative shrink-0">
                    <div class="w-3 h-3 rounded-full bg-current animate-pulse"></div>
                    <div class="absolute inset-0 w-3 h-3 rounded-full bg-current animate-ping opacity-40"></div>
                </div>
                <div class="flex flex-col leading-none">
                    <span class="text-[10px] font-black uppercase tracking-[0.2em] opacity-60 mb-0.5">Connectivity</span>
                    <span class="text-sm font-bold">{{ isReconnecting ? 'Resyncing Cluster' : 'Server Connection Interrupted' }}</span>
                </div>
            </div>
        </div>
    </Transition>

    <!-- Splash Screen -->
    <div v-if="layoutState === 'loading'" class="fixed inset-0 z-[100] flex flex-col bg-bg-app transition-all duration-1000 overflow-hidden splash-grid-bg">
        
        <!-- Background Decor (Reduced blur to prevent STATUS_BREAKPOINT crash) -->
        <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none transition-all duration-1000" :class="{'blur-xl opacity-20 scale-110': isFunFactHanging}">
            <div class="absolute top-[-5%] left-[-5%] w-2/3 h-2/3 rounded-full bg-blue-500/5 blur-[80px] animate-pulse"></div>
            <div class="absolute bottom-[-5%] right-[-5%] w-2/3 h-2/3 rounded-full bg-indigo-500/5 blur-[80px] animate-pulse delay-1000"></div>
        </div>

        <!-- Backdrop for expanded state -->
        <div v-if="isFunFactHanging" class="fixed inset-0 bg-white/40 dark:bg-black/60 backdrop-blur-md z-[140] transition-all duration-500" @click="toggleFactHang"></div>

        <!-- Background Ambient Geometry -->
        <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none transition-all duration-1000" :class="{'blur-3xl opacity-20 scale-110': isFunFactHanging}">
            <div class="absolute -top-[10%] -left-[10%] w-[80%] h-[80%] rounded-full bg-primary/5 blur-[120px] animate-pulse"></div>
            <div class="absolute -bottom-[10%] -right-[10%] w-[80%] h-[80%] rounded-full bg-accent/5 blur-[120px] animate-pulse delay-1000"></div>
        </div>

        <div class="grow flex flex-col relative z-10 transition-all duration-700" :class="{'blur-2xl opacity-0 scale-90 pointer-events-none': isFunFactHanging}">

            <div class="grow flex flex-col items-center justify-center p-6 space-y-6 max-w-lg mx-auto w-full">
                <!-- Compact Logo & Branding -->
                <div class="text-center splash-branding animate-in fade-in zoom-in-95 duration-1000">
                    <div class="flex justify-center mb-6 logo-wrap animate-float">
                        <div class="relative group">
                            <!-- Rotating glowing backplate -->
                            <div class="absolute -inset-4 bg-gradient-to-tr from-primary/30 to-accent/30 blur-2xl rounded-full opacity-70 group-hover:opacity-100 animate-rotate-glow transition-all duration-1000"></div>
                            <img :src="logoSrc" alt="Logo" class="relative h-24 sm:h-28 w-auto object-contain drop-shadow-[0_15px_30px_rgba(0,0,0,0.15)] dark:drop-shadow-[0_15px_30px_rgba(255,255,255,0.1)] transition-transform duration-700 hover:scale-105" />
                        </div>
                    </div>
                    <h1 class="welcome-title text-transparent bg-clip-text bg-gradient-to-b from-text-main to-text-dim">
                        {{ authStore.welcomeText || 'LoLLMs' }}
                    </h1>
                    <p class="welcome-slogan mt-2 opacity-60">
                        {{ authStore.welcomeSlogan || 'Universal Intelligence Orchestrator' }}
                    </p>
                </div>

                <!-- Unified Sleek Loader & Knowledge Card -->
                <div class="w-full text-left shadow-2xl bg-white/40 dark:bg-black/30 backdrop-blur-xl border border-white/10 dark:border-white/5 overflow-hidden rounded-[1.5rem] transition-all duration-500 p-6 sm:p-8 border-l-[8px]" 
                     :style="{ borderLeftColor: authStore.funFact ? funFactColor : 'var(--color-primary)' }">

                    <!-- Header Row -->
                    <div class="flex items-center justify-between gap-4 mb-5">
                        <div class="flex items-center gap-4 min-w-0">
                            <div class="w-10 h-10 rounded-full flex items-center justify-center bg-gray-100 dark:bg-gray-800 shadow-inner shrink-0">
                                <span v-if="authStore.funFact" class="text-xl">💡</span>
                                <IconAnimateSpin v-else class="w-5 h-5 text-primary animate-spin" />
                            </div>
                            <div class="flex flex-col min-w-0">
                                <span class="text-[9px] font-black uppercase tracking-[0.3em] opacity-40 leading-none mb-1">
                                    {{ authStore.funFact ? 'Knowledge Discovery' : 'System Boot' }}
                                </span>
                                <span class="text-xs font-bold truncate" :style="{ color: authStore.funFact ? funFactColor : 'var(--color-primary)' }">
                                    {{ authStore.funFact ? (funFactCategory || 'Fact Discovery') : 'Preparing Workspace' }}
                                </span>
                            </div>
                        </div>

                        <!-- Pin / Expand Button -->
                        <button 
                            v-if="authStore.funFact"
                            @click.stop="toggleFactHang()" 
                            class="p-2.5 bg-gray-100/50 hover:bg-gray-200/50 dark:bg-gray-800/50 dark:hover:bg-gray-700/50 text-gray-500 hover:text-blue-500 rounded-xl transition-all duration-300 active:scale-95 flex items-center justify-center pointer-events-auto"
                            title="Pin & Expand Fact"
                        >
                            <!-- Sleek Pushpin Icon -->
                            <svg xmlns="http://www.w3.org/2000/svg" class="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a3 3 0 016 0v2M7 7h10" />
                            </svg>
                        </button>
                    </div>

                    <!-- Fun Fact Body (Only visible if loaded) -->
                    <div v-if="authStore.funFact" class="mb-6 pr-2 max-h-[14vh] overflow-y-auto custom-scrollbar italic font-serif text-lg text-text-main/85 leading-relaxed border-l-2 pl-4 border-gray-200 dark:border-gray-800">
                        <MessageContentRenderer :content="authStore.funFact" class="line-clamp-3" />
                    </div>

                    <!-- Integrated Progress Bar Section -->
                    <div class="pt-4 border-t border-gray-150 dark:border-gray-850/50">
                        <div class="flex justify-between items-end mb-2.5">
                            <div class="flex flex-col min-w-0">
                                <span class="splash-loading-label">System Initialization</span>
                                <span class="text-[11px] font-bold text-primary dark:text-blue-400 animate-pulse tracking-wide truncate pr-4">
                                    {{ authStore.loadingMessage }}
                                </span>
                            </div>
                            <div class="text-right shrink-0">
                                <span class="text-base font-black text-gray-900 dark:text-gray-100 font-mono tracking-tighter">{{ authStore.loadingProgress }}%</span>
                            </div>
                        </div>

                        <!-- Progress Track -->
                        <div class="splash-progress-track !bg-gray-200/10 dark:!bg-gray-800/10 border border-white/5 h-2">
                            <div class="splash-progress-fill" :style="{ width: `${authStore.loadingProgress}%` }">
                                <div class="absolute inset-0 w-full h-full progress-bar-animated opacity-40"></div>
                            </div>
                        </div>

                        <!-- Funny / System Status Hint -->
                        <p class="mt-3.5 text-center text-[8px] font-black uppercase tracking-[0.3em] text-gray-400 dark:text-gray-600 opacity-65">
                            {{ authStore.funFact ? funnyStatusHint : 'Connecting to local worker cluster...' }}
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Expanded Fact Overlay (Z-150 ensures it's above the loading screen) -->
        <Teleport to="body" v-if="isFunFactHanging">
            <div class="fixed inset-0 z-[150] flex items-center justify-center p-6" @click.self="toggleFactHang">
                <div class="p-8 sm:p-12 border-l-[12px] rounded-[2.5rem] text-left shadow-[0_50px_100px_-20px_rgba(0,0,0,0.6)] bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 overflow-hidden w-full max-w-4xl animate-fade-in-up" :style="funFactStyle">
                    <div class="flex items-center justify-between mb-8 border-b dark:border-gray-800 pb-6">
                        <div class="flex items-center gap-4">
                            <span class="text-4xl">💡</span>
                            <span class="font-black text-xs uppercase tracking-[0.3em]" :style="{ color: funFactColor }">{{ funFactCategory || 'Fact Discovery' }}</span>
                        </div>
                        <button @click.stop="toggleFactHang" class="p-3 bg-gray-100 dark:bg-gray-800 hover:bg-red-50 dark:hover:bg-red-950/30 text-red-500 rounded-full transition-all hover:rotate-90">
                            <IconXMark class="w-8 h-8" />
                        </button>
                    </div>
                    <div class="max-h-[55vh] overflow-y-auto custom-scrollbar pr-6">
                        <MessageContentRenderer :key="authStore.funFact" :content="authStore.funFact" class="text-gray-900 dark:text-gray-100 text-lg sm:text-xl leading-relaxed" />
                    </div>
                    <div class="mt-10 flex items-center justify-between">
                        <button @click.stop="authStore.fetchNewFunFact()" class="btn btn-secondary px-6" :disabled="authStore.isFetchingFunFact">
                            <IconAnimateSpin v-if="authStore.isFetchingFunFact" class="w-5 h-5 mr-2 animate-spin" />
                            Next Fact
                        </button>
                        <button @click.stop="toggleFactHang" class="btn btn-primary px-10 py-3 text-sm font-black uppercase tracking-widest rounded-2xl shadow-xl">
                            Got it &rarr;
                        </button>
                    </div>
                </div>
            </div>
        </Teleport>

        <footer class="absolute bottom-2 w-full text-center text-[9px] font-black uppercase tracking-[0.4em] text-gray-400 dark:text-gray-600 pointer-events-none" :class="{'opacity-0': isFunFactHanging}">ParisNeo &middot; 2025</footer>    
    </div>

    <!-- Main Authenticated Layout -->
    <div v-else-if="layoutState === 'authenticated'" class="flex flex-col grow min-h-0 relative overflow-hidden bg-bg-app">
      <!-- FORCE SYNC: Ensure this is the component from components/layout/GlobalHeader.vue -->
      <GlobalHeader :key="authStore.user?.id" />

      <div class="flex grow min-h-0 relative w-full h-full">
        <!-- Main Sidebar -->
        <div v-if="showMainSidebar" 
             class="absolute md:relative inset-y-0 left-0 z-40 md:z-auto transition-all duration-500 ease-in-out h-full shadow-2xl md:shadow-none" 
             :class="isSidebarOpen ? 'translate-x-0 opacity-100' : '-translate-x-full md:translate-x-0 opacity-0 md:opacity-100'">
            <Sidebar/>
        </div>

        <!-- Mobile Sidebar Backdrop -->
        <Transition enter-active-class="duration-300 ease-out" enter-from-class="opacity-0" enter-to-class="opacity-100" leave-active-class="duration-200 ease-in" leave-from-class="opacity-100" leave-to-class="opacity-0">
            <div v-if="showMainSidebar && isSidebarOpen" @click="uiStore.toggleSidebar" class="absolute inset-0 bg-black/40 backdrop-blur-sm z-30 md:hidden"></div>
        </Transition>

        <!-- Principal Viewport -->
        <main class="flex-1 overflow-hidden relative bg-bg-app border-x border-border-main transition-colors duration-500">
            <router-view />
        </main>

        <ChatSidebar />
      </div>
      <AudioPlayer />
    </div>
    
    <!-- Guest Layout (Login/Welcome) -->
    <div v-else-if="layoutState === 'guest'" class="flex flex-col grow min-h-0"><router-view /></div>

    <!-- Global Overlays -->
    <ModalContainer />
    <WhatsNextModal />
    <NotebookWizardModal />
    <ImageViewerModal />
    <SlideshowModal />
    <CommandOutputModal />
    <ArtefactImportWizardModal /> 
    <ArtefactViewerModal />       
    <NotificationPanel /><AudioPlayer />
  </div>
</template>

<style>
/** 
 * UI PROTECTION LAYER 
 * Prevents AI-generated global resets (like * { margin: 0 }) 
 * from breaking the application's core layout components.
 */
#app, .modal-panel, header, aside, .message-row {
    margin: 0 !important;
    padding: 0 !important;
    box-sizing: border-box !important;
}

#app {
    display: flex !important;
    flex-direction: column !important;
    height: 100vh !important;
    width: 100vw !important;
}

@keyframes progress-animation { 0% { background-position: 1rem 0; } 100% { background-position: 0 0; } }
.progress-bar-animated { background-image: linear-gradient(45deg, rgba(255, 255, 255, .15) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, .15) 50%, rgba(255, 255, 255, .15) 75%, transparent 75%, transparent); background-size: 1rem 1rem; animation: progress-animation 1s linear infinite; }

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in-up { animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards; }

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
}
.animate-float {
    animation: float 4s ease-in-out infinite;
}

@keyframes rotate-glow {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
.animate-rotate-glow {
    animation: rotate-glow 20s linear infinite;
}

.splash-grid-bg {
    background-image: linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
    background-size: 50px 50px;
    background-position: center;
}
.dark .splash-grid-bg {
    background-image: linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px);
}

/* Landscape optimization */
@media (max-height: 600px) {
    .splash-branding img { height: 4rem !important; }
    .splash-branding h1 { font-size: 3rem !important; }
    .space-y-8 > :not([hidden]) ~ :not([hidden]) { margin-top: 1rem !important; }
}
</style>
