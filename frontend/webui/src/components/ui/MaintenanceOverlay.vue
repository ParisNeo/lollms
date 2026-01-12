<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import axios from 'axios';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';

const uiStore = useUiStore();
const maintenanceMessage = computed(() => uiStore.maintenanceMessage);

const funFact = ref(null);
const loadingFact = ref(false);
let factInterval = null;

async function fetchFunFact() {
    loadingFact.value = true;
    try {
        // Use the public ui router endpoint (or any public one) if possible
        // Or if session is invalid, the backend auth might block.
        // However, backend/routers/ui.py -> get_fun_fact is public (depends on get_db only).
        const res = await axios.get('/api/fun-fact');
        funFact.value = res.data;
    } catch (e) {
        console.error("Could not fetch fun fact during maintenance", e);
    } finally {
        loadingFact.value = false;
    }
}

async function checkStatus() {
    try {
        const res = await axios.get('/api/public/system-status');
        if (!res.data.maintenance_mode) {
            // Maintenance over!
            uiStore.setMaintenanceMode(false, "");
            window.location.reload();
        }
    } catch (e) {
        // Still down or error
    }
}

onMounted(() => {
    fetchFunFact();
    // Rotate facts every 30s
    factInterval = setInterval(() => {
        fetchFunFact();
        checkStatus(); // Also check if maintenance is over
    }, 15000);
});

onUnmounted(() => {
    if (factInterval) clearInterval(factInterval);
});

function manualRefresh() {
    checkStatus();
    fetchFunFact();
}
</script>

<template>
    <div class="fixed inset-0 z-[9999] bg-gray-900 text-white flex flex-col items-center justify-center p-6 text-center">
        
        <!-- Icon and Pulse -->
        <div class="relative mb-8">
            <div class="absolute inset-0 bg-yellow-500 blur-[60px] opacity-20 animate-pulse"></div>
            <div class="relative bg-gray-800 p-6 rounded-full border-4 border-yellow-500 shadow-2xl">
                <IconWrenchScrewdriver class="w-16 h-16 text-yellow-500 animate-bounce-slow" />
            </div>
        </div>

        <h1 class="text-4xl md:text-5xl font-black tracking-tight mb-4 text-transparent bg-clip-text bg-gradient-to-r from-yellow-400 to-orange-500">
            System Maintenance
        </h1>
        
        <div class="max-w-2xl bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-2xl p-8 shadow-xl mb-12">
            <p class="text-xl text-gray-300 font-medium leading-relaxed">
                {{ maintenanceMessage || "We are currently improving the system. Please check back shortly." }}
            </p>
        </div>

        <!-- Fun Fact Section -->
        <div class="max-w-lg w-full">
            <div class="text-xs font-black uppercase tracking-[0.3em] text-gray-500 mb-4">While you wait...</div>
            
            <div class="bg-gray-800 border border-gray-700 rounded-xl p-6 relative overflow-hidden group">
                <div class="absolute top-0 left-0 w-1 h-full transition-colors duration-500" :style="{ backgroundColor: funFact?.color || '#3B82F6' }"></div>
                
                <div v-if="loadingFact && !funFact" class="flex justify-center py-4">
                     <div class="w-2 h-2 bg-gray-500 rounded-full animate-ping"></div>
                </div>
                
                <transition name="fade" mode="out-in">
                    <div v-if="funFact" :key="funFact.content" class="text-left">
                        <div class="flex items-center gap-2 mb-2">
                             <span class="text-xs font-bold uppercase" :style="{ color: funFact.color }">{{ funFact.category }}</span>
                        </div>
                        <p class="text-gray-300 text-sm leading-relaxed">{{ funFact.fun_fact }}</p>
                    </div>
                </transition>
                
                <!-- Progress bar for next fact -->
                <div class="absolute bottom-0 left-0 h-0.5 bg-gray-700 w-full">
                    <div class="h-full bg-white/20 animate-progress origin-left"></div>
                </div>
            </div>
        </div>

        <button @click="manualRefresh" class="mt-12 flex items-center gap-2 px-6 py-2 rounded-full bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-all text-sm font-bold uppercase tracking-wider border border-gray-700">
            <IconRefresh class="w-4 h-4" :class="{'animate-spin': loadingFact}" />
            Check Status
        </button>

    </div>
</template>

<style scoped>
.animate-bounce-slow {
    animation: bounce 3s infinite;
}
@keyframes bounce {
  0%, 100% { transform: translateY(-5%); animation-timing-function: cubic-bezier(0.8, 0, 1, 1); }
  50% { transform: translateY(0); animation-timing-function: cubic-bezier(0, 0, 0.2, 1); }
}

.animate-progress {
    animation: progress 15s linear infinite;
    width: 100%;
    transform-origin: left;
}
@keyframes progress {
    from { transform: scaleX(0); }
    to { transform: scaleX(1); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
