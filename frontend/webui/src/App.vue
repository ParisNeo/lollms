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
    if (isMaintenanceMode.value && !authStore.isAdmin) return 'maintenance';
    if (isAuthenticating.value || isFunFactHanging.value) return 'loading';
    return isAuthenticated.value ? 'authenticated' : 'guest';
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
watch(wsConnected, async (newVal, oldVal) => {
    if (newVal) {
        // If this is the first successful connection in this session, just mark it.
        // This prevents the overlay from flashing on initial load.
        if (!hasConnectedOnce.value) {
            hasConnectedOnce.value = true;
        } 
        // If we were previously disconnected (oldVal was explicitly false, not undefined) 
        // AND we are logged in, trigger synchronization logic.
        else if (oldVal === false && isAuthenticated.value) {
            isReconnecting.value = true;
            try {
                console.log("[App] Connection restored. Re-initializing...");
                // 1. Refresh User Data/Settings
                await authStore.fetchUser(); 
                // 2. Restart Task Listeners/Polling
                tasksStore.startPolling();
                // 3. Notify user
                uiStore.addNotification("Server connection restored. UI refreshed.", "success");
            } catch (e) {
                console.error("[App] Re-initialization failed:", e);
            } finally {
                // Small delay to let user see "Reconnected" status before hiding overlay
                setTimeout(() => {
                    isReconnecting.value = false;
                }, 800);
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
  <div class="h-screen w-screen overflow-hidden font-sans antialiased text-gray-800 dark:text-gray-100 bg-gray-50 dark:bg-gray-900 flex flex-col">
    
    <!-- Maintenance Overlay -->
    <MaintenanceOverlay v-if="layoutState === 'maintenance'" />

    <!-- Connection Lost Overlay -->
    <Transition
        enter-active-class="transition ease-out duration-300"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition ease-in duration-200"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
    >
        <ConnectionOverlay 
            v-if="(!wsConnected && isAuthenticated && hasConnectedOnce && layoutState !== 'maintenance') || isReconnecting" 
            :message="isReconnecting ? 'Synchronizing data...' : 'Searching for server'"
            :sub-message="isReconnecting ? 'Reconnected' : 'Connection Lost'"
        />
    </Transition>

    <!-- Splash Screen -->
    <div v-if="layoutState === 'loading'" class="fixed inset-0 z-[100] flex flex-col bg-gray-50 dark:bg-gray-950 transition-all duration-700 overflow-hidden">
        
        <!-- Background Decor -->
        <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none transition-all duration-1000" :class="{'blur-3xl opacity-20 scale-110': isFunFactHanging}">
            <div class="absolute top-[-5%] left-[-5%] w-2/3 h-2/3 rounded-full bg-blue-500/10 blur-[140px] animate-pulse"></div>
            <div class="absolute bottom-[-5%] right-[-5%] w-2/3 h-2/3 rounded-full bg-indigo-500/10 blur-[140px] animate-pulse delay-1000"></div>
        </div>

        <!-- Backdrop for expanded state -->
        <div v-if="isFunFactHanging" class="fixed inset-0 bg-white/40 dark:bg-black/60 backdrop-blur-xl z-[140] transition-all duration-500" @click="toggleFactHang"></div>

        <!-- Main Layout Container: Splits Top branding/fact from Bottom progress -->
        <div class="flex-grow flex flex-col relative z-10 transition-all duration-500" :class="{'blur-2xl opacity-10 scale-95 pointer-events-none': isFunFactHanging}">
            
            <!-- Branding & Fact Group: Pushed toward top-middle -->
            <div class="flex-grow flex flex-col items-center justify-center p-6 space-y-8 sm:space-y-12">
                
                <!-- Branding -->
                <div class="text-center splash-branding">
                    <div class="flex justify-center mb-4 sm:mb-6 logo-wrap">
                        <img :src="logoSrc" alt="Logo" class="h-24 sm:h-32 w-auto object-contain drop-shadow-2xl" />
                    </div>
                    <h1 class="text-6xl sm:text-8xl font-black text-transparent bg-clip-text bg-gradient-to-br from-blue-600 to-indigo-700 dark:from-blue-400 dark:to-indigo-500 tracking-tighter leading-none" style="font-family: 'Exo 2', sans-serif;">
                        {{ authStore.welcomeText || 'LoLLMs' }}
                    </h1>
                    <p class="mt-3 text-lg sm:text-2xl text-gray-400 dark:text-gray-500 font-medium tracking-wide italic">
                        {{ authStore.welcomeSlogan || 'One tool to rule them all' }}
                    </p>
                </div>

                <!-- Fact Card (Natural flow, z-index 20) -->
                <div v-if="authStore.funFact" 
                    class="w-full max-w-md cursor-pointer group transition-all duration-500"
                    @click="toggleFactHang()">
                    <div class="p-6 sm:p-8 border-l-[8px] rounded-2xl text-left shadow-xl bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl border border-gray-100 dark:border-gray-700 overflow-hidden transform group-hover:scale-[1.02]" :style="funFactStyle">
                        <div class="flex items-center justify-between mb-4">
                            <div class="flex items-center gap-3">
                                <span class="text-2xl">💡</span>
                                <span class="font-black text-[10px] uppercase tracking-[0.2em]" :style="{ color: funFactColor }">{{ funFactCategory || 'Knowledge Bit' }}</span>
                            </div>
                        </div>
                        <div class="max-h-[15vh] overflow-y-auto custom-scrollbar pr-2">
                            <MessageContentRenderer :key="authStore.funFact" :content="authStore.funFact" class="text-gray-900 dark:text-gray-100 text-sm sm:text-base line-clamp-4" />
                        </div>
                        <div class="mt-4 text-[8px] text-center text-gray-400 dark:text-gray-500 font-black uppercase tracking-[0.2em] animate-pulse">Tap to expand</div>
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

        <!-- Progress Area: Always at the bottom, z-30 -->
        <div class="w-full bg-white/30 dark:bg-black/40 backdrop-blur-2xl p-6 sm:p-10 border-t border-gray-200/20 dark:border-gray-800/20 relative z-30 transition-all duration-500" :class="{'translate-y-full opacity-0': isFunFactHanging}">
            <div class="max-w-md mx-auto">
                <div class="h-1.5 w-full rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden relative shadow-inner">
                    <div class="h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-600 transition-all duration-700 relative" :style="{ width: `${authStore.loadingProgress}%` }">
                         <div class="absolute inset-0 w-full h-full progress-bar-animated opacity-30"></div>
                    </div>
                </div>
                <div class="flex justify-between items-center mt-4">
                    <span class="text-[10px] font-black text-blue-600 dark:text-blue-400 uppercase tracking-[0.2em] animate-pulse">{{ authStore.loadingMessage }}</span>
                    <span class="text-sm font-black text-gray-500 dark:text-gray-500 font-mono">{{ authStore.loadingProgress }}%</span>
                </div>
            </div>
        </div>

        <footer class="absolute bottom-2 w-full text-center text-[9px] font-black uppercase tracking-[0.4em] text-gray-400 dark:text-gray-600 pointer-events-none" :class="{'opacity-0': isFunFactHanging}">ParisNeo &middot; 2025</footer>    
    </div>

    <!-- Main Layout -->
    <div v-else-if="layoutState === 'authenticated'" class="flex flex-col flex-grow min-h-0 relative overflow-hidden">
      <!-- HEADER NOW ON TOP OF EVERYTHING -->
      <GlobalHeader />
      
      <div class="flex flex-grow min-h-0 relative w-full h-full">
        <!-- Main Sidebar (Discussions, etc.) -->
        <div v-if="showMainSidebar" class="absolute md:relative inset-y-0 left-0 z-40 md:z-auto transition-transform duration-300 ease-in-out h-full" :class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'"><Sidebar/></div>
        <div v-if="showMainSidebar && isSidebarOpen" @click="uiStore.toggleSidebar" class="absolute inset-0 bg-black/30 z-30 md:hidden"></div>
        
        <!-- Viewport -->
        <main class="flex-1 overflow-hidden relative">
            <router-view />
        </main>
        
        <!-- Social/Messaging Sidebar -->
        <ChatSidebar />
      </div>
    </div>
    
    <!-- Guest Layout (Login/Welcome) -->
    <div v-else-if="layoutState === 'guest'" class="flex flex-col flex-grow min-h-0"><router-view /></div>

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
@keyframes progress-animation { 0% { background-position: 1rem 0; } 100% { background-position: 0 0; } }
.progress-bar-animated { background-image: linear-gradient(45deg, rgba(255, 255, 255, .15) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, .15) 50%, rgba(255, 255, 255, .15) 75%, transparent 75%, transparent); background-size: 1rem 1rem; animation: progress-animation 1s linear infinite; }

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in-up { animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards; }

/* Landscape optimization */
@media (max-height: 600px) {
    .splash-branding img { height: 4rem !important; }
    .splash-branding h1 { font-size: 3rem !important; }
    .space-y-8 > :not([hidden]) ~ :not([hidden]) { margin-top: 1rem !important; }
}
</style>
