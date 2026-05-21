<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import DropdownMenu from './DropDownMenu/DropdownMenu.vue';

// Dynamic Icons
import IconAdjustmentsHorizontal from '../../assets/icons/IconAdjustmentsHorizontal.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

const uiStore = useUiStore();

const allVibes = [
    { id: 'default', name: 'Indigo Classic', color: 'bg-blue-600', desc: 'The original LoLLMs look' },
    { id: 'midnight', name: 'Midnight Deep', color: 'bg-slate-900', desc: 'High contrast dark slate' },
    { id: 'cyberpunk', name: 'Neon Cyber', color: 'bg-fuchsia-500', desc: 'Fuchsia and Cyan glow' },
    { id: 'forest', name: 'Emerald Forest', color: 'bg-emerald-600', desc: 'Natural green tones' }
];

// [FIX] Filter vibes based on luminance. Midnight is dark-only.
const visibleVibes = computed(() => {
    if (uiStore.currentTheme === 'dark') return allVibes;
    return allVibes.filter(v => v.id !== 'midnight');
});

const currentVibeData = computed(() => allVibes.find(v => v.id === uiStore.currentVibe) || allVibes[0]);

function toggleDark() {
    uiStore.toggleTheme();
}

function selectVibe(id) {
    uiStore.setVibe(id);
}
</script>
<style scoped>
@reference "tailwindcss";
@reference "../../assets/css/main.css";

/* Ensure specific vibe text colors apply correctly within the dropdown */
.text-primary {
    color: var(--color-primary);
}
</style>
<template>
  <div class="flex items-center gap-1 border dark:border-gray-700 rounded-xl p-0.5 bg-gray-50/50 dark:bg-gray-800/30 shrink-0">
    <!-- Luminance Toggle (Light/Dark) -->
    <button @click="toggleDark" 
            class="p-2 rounded-lg hover:bg-white dark:hover:bg-gray-700 text-gray-500 transition-all active:scale-90 shadow-sm shrink-0" 
            :title="uiStore.currentTheme === 'dark' ? 'Switch to Light' : 'Switch to Dark'">
        <svg v-if="uiStore.currentTheme === 'dark'" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5 text-yellow-400">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5 text-slate-400">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
        </svg>
    </button>

    <div class="w-px h-4 bg-gray-200 dark:bg-gray-700 mx-1 shrink-0"></div>

    <!-- Vibe Selector (Dynamic Icon) -->
    <DropdownMenu title="Vibe Selector" buttonClass="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-all flex items-center gap-2 shrink-0 border border-transparent hover:border-gray-200 dark:hover:border-gray-600 shadow-sm">
        <span class="text-[10px] font-black uppercase text-blue-500 block">Vibes</span>
        <template #icon>
              <IconAdjustmentsHorizontal class="w-5 h-5 text-blue-600 dark:text-blue-400" />
        </template>

        <div class="p-2 min-w-[220px] space-y-1">
            <div class="px-3 py-2 text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] border-b dark:border-gray-700 mb-2">Vibe Selection</div>

            <button v-for="vibe in visibleVibes" :key="vibe.id" 
                    @click="selectVibe(vibe.id)"
                    class="w-full flex items-center gap-3 p-2.5 rounded-xl transition-all text-left group relative"
                    :class="uiStore.currentVibe === vibe.id ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-700/50'">
                
                <div class="w-10 h-10 rounded-lg border border-black/5 shrink-0 flex items-center justify-center shadow-sm" :class="vibe.color">
                    <IconCheckCircle v-if="uiStore.currentVibe === vibe.id" class="w-5 h-5 text-white" />
                </div>
                
                <div class="flex flex-col min-w-0">
                    <span class="text-xs font-bold leading-none mb-1" :class="uiStore.currentVibe === vibe.id ? 'text-blue-600 dark:text-blue-400' : 'text-gray-700 dark:text-gray-200'">{{ vibe.name }}</span>
                    <span class="text-[10px] text-gray-400 truncate">{{ vibe.desc }}</span>
                </div>
            </button>
        </div>
    </DropdownMenu>
  </div>
</template>
