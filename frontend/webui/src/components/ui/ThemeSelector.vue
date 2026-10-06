<script setup>
import { computed, ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import DropdownMenu from './DropDownMenu/DropdownMenu.vue';
import ThemeLabModal from './ThemeLabModal.vue';

import IconAdjustmentsHorizontal from '../../assets/icons/IconAdjustmentsHorizontal.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const uiStore = useUiStore();
const showThemeLab = ref(false);
const materialEffects = [
    { id: 'default', name: 'Standard', icon: 'M4 6h16M4 12h16M4 18h16' },
    { id: 'glass', name: 'Glassmorphism', icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
    { id: 'skeuo', name: 'Skeuomorphic', icon: 'M4 4h16v16H4z' },
    { id: 'paper', name: 'Paper', icon: 'M6 2h12v20H6z' },
    { id: 'flat', name: 'Flat Design', icon: 'M3 3h18v18H3z' }
];

const allVibes = [
    { id: 'default', name: 'Indigo Classic', color: 'bg-blue-600', desc: 'Original look', darkOnly: false },
    { id: 'midnight', name: 'Midnight Deep', color: 'bg-slate-900', desc: 'High contrast dark', darkOnly: true },
    { id: 'cyberpunk', name: 'Neon Cyber', color: 'bg-fuchsia-500', desc: 'Fuchsia/Cyan glow', darkOnly: false },
    { id: 'forest', name: 'Emerald Forest', color: 'bg-emerald-600', desc: 'Natural greens', darkOnly: false },
    { id: 'ocean', name: 'Ocean Breeze', color: 'bg-cyan-500', desc: 'Deep blue/cyan', darkOnly: false },
    { id: 'sunset', name: 'Sunset Warmth', color: 'bg-orange-500', desc: 'Warm coral', darkOnly: false },
    { id: 'lavender', name: 'Lavender Fields', color: 'bg-violet-500', desc: 'Soft purple', darkOnly: false },
    { id: 'monochrome', name: 'Monochrome', color: 'bg-gray-600', desc: 'Neutral grays', darkOnly: false }
];

const visibleVibes = computed(() => {
    if (uiStore.currentTheme === 'dark') return allVibes;
    return allVibes.filter(v => !v.darkOnly);
});

const isCustomActive = computed(() => uiStore.currentVibe === 'custom' && uiStore.currentCustomTheme);

function toggleDark() {
    uiStore.toggleTheme();
}

function selectVibe(id) {
    uiStore.setVibe(id);
    // Close dropdown by simulating click outside (optional, relying on dropdown behavior)
}

function openThemeLab() {
    showThemeLab.value = true;
}

function closeThemeLab() {
    showThemeLab.value = false;
}
</script>

<template>
  <div class="flex items-center gap-1 border dark:border-gray-700 rounded-xl p-0.5 bg-gray-50/50 dark:bg-gray-800/30 shrink-0 transition-colors">
    <!-- Dark Mode Toggle -->
    <button 
        @click="toggleDark" 
        class="relative p-2 rounded-lg transition-all duration-300 shrink-0 group"
        :class="uiStore.currentTheme === 'dark' ? 'bg-gray-800 text-yellow-400 shadow-inner' : 'bg-white text-gray-500 shadow border border-gray-200'"
        :title="uiStore.currentTheme === 'dark' ? 'Switch to Light' : 'Switch to Dark'">
        <div class="relative w-5 h-5">
            <svg v-if="uiStore.currentTheme === 'dark'" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5 transition-transform duration-500 group-hover:rotate-12">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5 transition-transform duration-500 group-hover:rotate-90">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
            </svg>
        </div>
    </button>

    <div class="w-px h-5 bg-gray-200 dark:bg-gray-700 mx-0.5 shrink-0"></div>

    <!-- Theme Dropdown Trigger -->
    <DropdownMenu title="Theme Selector" buttonClass="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-all flex items-center gap-2 shrink-0 border border-transparent hover:border-gray-200 dark:hover:border-gray-600">
        <template #icon>
            <IconAdjustmentsHorizontal class="w-5 h-5 text-blue-600 dark:text-blue-400" />
        </template>
        <template #label>
            <span class="text-xs font-bold uppercase tracking-wider hidden sm:inline">Themes</span>
        </template>

        <!-- Dropdown Content Container - Fixed Height with Scroll -->
        <div class="fixed-dropdown-content p-0 max-h-[70vh] overflow-y-auto custom-scrollbar flex flex-col gap-1">
            <!-- Active Custom Theme Badge -->
            <div v-if="isCustomActive" class="mb-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl border border-blue-200/50 dark:border-blue-800/50 flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                    <IconSparkles class="w-4 h-4 text-blue-600 dark:text-blue-400" />
                    <div>
                        <div class="text-xs font-black text-blue-900 dark:text-blue-100 uppercase tracking-wider">Custom Active</div>
                        <div class="text-[10px] text-blue-700 dark:text-blue-300 font-medium">{{ uiStore.currentCustomTheme.name }}</div>
                    </div>
                </div>
                <button @click="openThemeLab" class="p-1.5 bg-white dark:bg-blue-900/30 rounded-lg text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors shadow-sm" title="Edit Theme">
                    <IconAdjustmentsHorizontal class="w-4 h-4" />
                </button>
            </div>

            <!-- Section Label -->
            <div class="px-3 py-2 text-[9px] font-black uppercase tracking-[0.2em] border-b border-secondary mb-2 pb-1 sticky top-0 bg-surface-0 z-10" style="background-color: var(--brand-bg-sidebar); border-color: var(--brand-border-main);">
                Preset Atmospheres
            </div>

            <!-- Vibe Grid -->
            <div class="space-y-1.5 mb-3">
                <button v-for="vibe in visibleVibes" :key="vibe.id" 
                        @click="selectVibe(vibe.id)"
                        class="w-full group relative overflow-hidden rounded-xl p-2.5 transition-all duration-200 text-left border theme-item-hover mb-1"
                        :class="uiStore.currentVibe === vibe.id 
                            ? 'border-accent bg-surface-1' 
                            : 'border-transparent hover:border-primary hover:bg-surface-1'"
                        style="background-color: var(--brand-bg-card); border-color: var(--brand-border-main);">
                    
                    <!-- Active Checkmark Overlay -->
                    <div v-if="uiStore.currentVibe === vibe.id" class="absolute top-1.5 right-1.5 z-10">
                        <IconCheckCircle class="w-4 h-4 text-blue-600 dark:text-blue-400" />
                    </div>

                    <div class="flex items-start gap-3 relative z-0">
                        <!-- Color Swatch -->
                        <div class="mt-0.5 w-8 h-8 rounded-lg shadow-sm flex-shrink-0 flex items-center justify-center border" 
                             :class="[vibe.color, uiStore.currentVibe === vibe.id ? 'border-blue-300 dark:border-blue-700' : 'border-black/5 dark:border-white/5']">
                            <div class="w-2 h-2 rounded-full bg-white/20" v-if="vibe.darkOnly && uiStore.currentTheme !== 'dark'"></div>
                        </div>
                        
                        <!-- Text Content -->
                        <div class="flex flex-col min-w-0 flex-1">
                            <span class="text-xs font-bold leading-tight truncate text-primary"
                                  :class="uiStore.currentVibe === vibe.id ? 'opacity-100' : ''"
                                  style="color: var(--brand-text-main);">
                                {{ vibe.name }}
                            </span>
                            <span class="text-[10px] leading-tight truncate mt-0.5 text-secondary"
                                  style="color: var(--brand-text-dim);">
                                {{ vibe.desc }}
                            </span>
                        </div>
                    </div>

                    <!-- Dark Mode Indicator -->
                    <div v-if="vibe.darkOnly && uiStore.currentTheme !== 'dark'" 
                         class="absolute inset-0 bg-white/60 dark:bg-black/60 flex items-center justify-center rounded-xl backdrop-blur-[1px]">
                        <span class="text-[9px] font-black uppercase tracking-widest text-gray-500 dark:text-gray-400 bg-white/80 dark:bg-black/80 px-2 py-1 rounded shadow-sm">Requires Dark Mode</span>
                    </div>
                </button>
            </div>

            <!-- Material Effects Section -->
            <div class="px-3 py-2 text-[9px] font-black text-gray-400 dark:text-gray-500 uppercase tracking-[0.2em] border-b-2 border-gray-100 dark:border-gray-800 mb-2 pb-1 mt-4">
                Material Effects
            </div>
            
            <div class="grid grid-cols-2 gap-1.5 mb-3">
                <button v-for="effect in materialEffects" :key="effect.id"
                        @click="uiStore.setEffect(effect.id)"
                        class="p-2 rounded-lg text-center transition-all border"
                        :class="uiStore.currentEffect === effect.id 
                            ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800' 
                            : 'bg-gray-50 dark:bg-gray-800/50 border-transparent hover:bg-gray-100 dark:hover:bg-gray-700'">
                    <svg class="w-4 h-4 mx-auto mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="effect.icon" />
                    </svg>
                    <span class="text-[10px] font-medium" 
                          :class="uiStore.currentEffect === effect.id ? 'text-blue-700 dark:text-blue-300' : 'text-gray-600 dark:text-gray-400'">
                        {{ effect.name }}
                    </span>
                </button>
            </div>

            <div class="border-t-2 border-gray-100 dark:border-gray-800 pt-2 mt-2">
                <button @click="openThemeLab" 
                        class="w-full flex items-center gap-3 p-2.5 rounded-xl transition-all text-left hover:bg-gradient-to-r hover:from-blue-50 hover:to-indigo-50 dark:hover:from-gray-800 dark:hover:to-gray-700 border border-dashed border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700 group">
                    <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center shadow-md shadow-blue-500/20 group-hover:scale-110 transition-transform">
                        <svg class="w-4.5 h-4.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                        </svg>
                    </div>
                    <div class="flex flex-col">
                        <span class="text-xs font-bold text-gray-900 dark:text-white leading-none">Theme Lab</span>
                        <span class="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">Create custom palette</span>
                    </div>
                </button>
            </div>
        </div>
    </DropdownMenu>

    <Teleport to="body">
        <ThemeLabModal v-if="showThemeLab" @close="closeThemeLab" />
    </Teleport>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: var(--brand-border-main); border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-track { background: var(--brand-bg-app); }
.theme-item-hover:hover { transform: translateX(4px); }
</style>