<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import axios from 'axios';

const props = defineProps({
    message: { type: String, default: 'Searching for server' },
    subMessage: { type: String, default: 'Connection lost' }
});

const uiStore = useUiStore();
const dots = ref('.');
let visualInterval;
let checkInterval;

async function checkConnection() {
    try {
        // Try to hit a lightweight endpoint with short timeout
        await axios.get('/api/public/system-status', { timeout: 3000 });
        // If successful, the server is back!
        uiStore.setConnectionLost(false);
    } catch (e) {
        // Still down, keep waiting
    }
}

onMounted(() => {
    // 1. Visual Animation
    visualInterval = setInterval(() => {
        dots.value = dots.value.length >= 3 ? '.' : dots.value + '.';
    }, 500);

    // 2. Connection Check Logic (Every 5 seconds)
    checkConnection(); // Check immediately
    checkInterval = setInterval(checkConnection, 5000);
});

onUnmounted(() => {
    clearInterval(visualInterval);
    clearInterval(checkInterval);
});
</script>

<template>
    <div class="fixed top-0 left-0 right-0 z-[10000] pointer-events-none flex justify-center p-4">
        <div class="pointer-events-auto flex items-center gap-4 bg-gray-900/95 dark:bg-black/90 backdrop-blur-md px-6 py-3 rounded-2xl shadow-2xl border border-blue-500/30 animate-fade-in-down">
            
            <div class="relative flex items-center justify-center w-10 h-10">
                <!-- Radar Scanner Animation (Scaled Down) -->
                <div class="radar-container">
                    <div class="radar-sweep"></div>
                    <div class="radar-ring ring-1"></div>
                    <div class="radar-ring ring-2"></div>
                </div>
                
                <!-- Center Icon -->
                <div class="relative z-10 p-1.5 rounded-full text-blue-500">
                     <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
            </div>
            
            <div class="flex flex-col">
                <h2 class="text-sm font-black text-white uppercase tracking-tighter">{{ subMessage }}</h2>
                <p class="text-[10px] text-blue-400 font-mono uppercase tracking-widest animate-pulse whitespace-nowrap">{{ message }}{{ dots }}</p>
            </div>

            <!-- Tiny Progress Line -->
            <div class="w-16 h-1 bg-gray-800 rounded-full overflow-hidden ml-2 hidden sm:block">
                <div class="h-full bg-blue-500 animate-progress-indeterminate"></div>
            </div>
        </div>
    </div>
</template>

<style scoped>
@keyframes fadeInDown {
    from { opacity: 0; transform: translateY(-20px); }
    to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in-down {
    animation: fadeInDown 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.radar-container {
    @apply absolute w-12 h-12 flex items-center justify-center;
}

.radar-sweep {
    @apply absolute w-full h-full rounded-full;
    background: conic-gradient(from 0deg, transparent 0deg, rgba(59, 130, 246, 0.2) 60deg, transparent 60deg);
    animation: radar-spin 2s linear infinite;
}

.radar-ring {
    @apply absolute rounded-full border border-blue-500/30;
    animation: radar-ping 3s infinite cubic-bezier(0, 0, 0.2, 1);
}

.ring-1 { width: 40%; height: 40%; animation-delay: 0s; }
.ring-2 { width: 100%; height: 100%; animation-delay: 1.5s; }

@keyframes radar-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

@keyframes radar-ping {
    0% { transform: scale(0.8); opacity: 0.5; }
    100% { transform: scale(1.2); opacity: 0; }
}

.animate-progress-indeterminate {
    animation: progress-indeterminate 1.5s infinite linear;
    width: 30%;
    transform-origin: 0% 50%;
}

@keyframes progress-indeterminate {
    0% { transform: translateX(0) scaleX(0); }
    40% { transform: translateX(0) scaleX(0.4); }
    100% { transform: translateX(100%) scaleX(0.5); }
}
</style>
