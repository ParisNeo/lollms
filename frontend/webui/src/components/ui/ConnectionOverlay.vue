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
    <div class="fixed inset-0 z-[10000] flex flex-col items-center justify-center bg-gray-900/90 backdrop-blur-sm transition-opacity duration-300 cursor-wait">
        <div class="relative flex items-center justify-center mb-10">
            <!-- Radar Scanner Animation -->
            <div class="radar-container">
                <div class="radar-sweep"></div>
                <div class="radar-ring ring-1"></div>
                <div class="radar-ring ring-2"></div>
                <div class="radar-ring ring-3"></div>
            </div>
            
            <!-- Center Icon -->
            <div class="relative z-10 bg-gray-900 p-5 rounded-full border border-blue-500 shadow-[0_0_30px_rgba(59,130,246,0.6)]">
                 <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            </div>
        </div>
        
        <h2 class="text-3xl font-bold text-white mb-3 tracking-wide">{{ subMessage }}</h2>
        <p class="text-blue-400 font-mono text-base uppercase tracking-widest animate-pulse">{{ message }}{{ dots }}</p>
        
        <div class="mt-10 w-64 h-1 bg-gray-800 rounded-full overflow-hidden">
            <div class="h-full bg-blue-500 animate-progress-indeterminate"></div>
        </div>
    </div>
</template>

<style scoped>
.radar-container {
    @apply absolute w-80 h-80 flex items-center justify-center;
}

.radar-sweep {
    @apply absolute w-full h-full rounded-full;
    background: conic-gradient(from 0deg, transparent 0deg, rgba(59, 130, 246, 0.1) 60deg, transparent 60deg);
    animation: radar-spin 2s linear infinite;
    border-radius: 50%;
}

.radar-ring {
    @apply absolute rounded-full border border-blue-500/20;
    animation: radar-ping 3s infinite cubic-bezier(0, 0, 0.2, 1);
}

.ring-1 { width: 30%; height: 30%; animation-delay: 0s; }
.ring-2 { width: 60%; height: 60%; animation-delay: 1s; }
.ring-3 { width: 90%; height: 90%; animation-delay: 2s; }

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
