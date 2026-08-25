<script setup>
import { computed } from 'vue';
import TaskProgressIndicator from '../TaskProgressIndicator.vue';
import IconStar from '../../../assets/icons/IconStar.vue';
import IconStarFilled from '../../../assets/icons/IconStarFilled.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconArrowUpCircle from '../../../assets/icons/IconArrowUpCircle.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconBookOpen from '../../../assets/icons/IconBookOpen.vue';
import IconGitBranch from '../../../assets/icons/ui/IconGitBranch.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconNoSymbol from '../../../assets/icons/IconNoSymbol.vue';

const props = defineProps({
    personality: { type: Object, required: true },
    task: { type: Object, default: null },
    isStarred: { type: Boolean, default: false }
});

const emit = defineEmits([
    'star', 'install', 'update', 'uninstall', 'help'
]);

const defaultIcon = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTguNiAxLjhBMi40IDIuNCAwIDAwMTYuOSAxTDEyIDUuOUg4YTIgMiAwIDAwLTIgMnYxLjVMMy4yIDEwLjdhMiAyIDAgMDAwIDIuNmwzLjcgMi41VjE4YTIgMiAwIDAwMiAySDdhMiAyIDAgMDAyLTJoNC4xaDIuNGEyIDIgMCAwMDItMmw0LjUtNC41YTIuNCAyLjQgMCAwMC42LTEuN1YyLjRhMi40IDIuNCAwIDAwLTIuNC0yLjR6IiBjbGlwLXJ1bGU9ImV2ZW5vZGQiLz4KPC9zdmc+';

const categoryColors = {
    'Creative': 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
    'Coding': 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    'Educational': 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    'Technical Support': 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
    'Writing': 'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300',
    'Science': 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300',
    'Business': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
    'Fun': 'bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/40 dark:text-fuchsia-300',
    'Generic': 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    'default': 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
};

const categoryBadgeClass = computed(() => {
    return categoryColors[props.personality.category] || categoryColors['default'];
});
</script>

<template>
    <div 
        class="group relative bg-white/95 dark:bg-gray-800/90 rounded-2xl border border-gray-200/80 dark:border-gray-700/70 shadow-sm hover:shadow-xl hover:-translate-y-1 hover:border-blue-500/40 dark:hover:border-blue-500/40 flex flex-col overflow-hidden transition-all duration-300 h-full backdrop-blur-sm"
        :class="{ 'opacity-60 pointer-events-none': personality.is_legacy_scripted }"
    >
        <!-- Legacy Incompatibility Overlay -->
        <div v-if="personality.is_legacy_scripted" class="absolute inset-0 bg-gray-900/60 backdrop-blur-sm flex flex-col items-center justify-center rounded-2xl z-20 p-4 text-center">
            <IconNoSymbol class="w-12 h-12 text-rose-500 mb-2 animate-pulse" />
            <span class="text-xs font-semibold text-white">Legacy Scripted Item</span>
            <span class="text-[10px] text-gray-300 mt-1">Incompatible with current runtime</span>
        </div>

        <!-- Card Top Bar: Icon + Title + Status + Star -->
        <div class="flex items-start p-4 gap-3.5 border-b border-gray-100 dark:border-gray-750/50">
            <!-- Personality Avatar -->
            <div class="relative shrink-0">
                <img 
                    :src="personality.icon || defaultIcon" 
                    :alt="personality.name" 
                    class="w-12 h-12 rounded-xl object-cover bg-gray-50 dark:bg-gray-700/80 p-1 border border-gray-200/60 dark:border-gray-600/50 shadow-inner group-hover:scale-105 transition-transform duration-300" 
                />
                <!-- Installed indicator badge -->
                <span 
                    v-if="personality.is_installed" 
                    class="absolute -top-1 -right-1 flex h-4 w-4 bg-emerald-500 rounded-full items-center justify-center border-2 border-white dark:border-gray-800 text-white shadow-xs"
                    title="Installed in System"
                >
                    <IconCheckCircle class="w-3 h-3" />
                </span>
            </div>

            <!-- Meta & Title -->
            <div class="grow min-w-0">
                <div class="flex justify-between items-start gap-1">
                    <h3 class="font-bold text-sm text-gray-900 dark:text-white truncate leading-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors" :title="personality.name">
                        {{ personality.name }}
                    </h3>
                    <button 
                        @click.stop="$emit('star', personality.name)" 
                        class="p-1 rounded-lg transition-all duration-200 shrink-0 hover:scale-110 active:scale-95" 
                        :class="isStarred ? 'bg-amber-400/15 text-amber-500' : 'text-gray-300 dark:text-gray-600 hover:text-amber-400'"
                        :title="isStarred ? 'Remove from favorites' : 'Add to favorites'"
                    >
                        <IconStarFilled v-if="isStarred" class="w-4 h-4" />
                        <IconStar v-else class="w-4 h-4" />
                    </button>
                </div>

                <!-- Badges (Installed, Update, Category, Version) -->
                <div class="flex flex-wrap items-center gap-1.5 mt-1.5">
                    <span 
                        v-if="personality.is_installed && !personality.update_available" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200/60 dark:border-emerald-800/40"
                    >
                        Installed
                    </span>
                    <span 
                        v-else-if="personality.is_installed && personality.update_available" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-300/60 dark:border-amber-700/40 animate-pulse"
                        :title="`Update available: v${personality.version}`"
                    >
                        Update Available
                    </span>

                    <!-- Category Badge -->
                    <span v-if="personality.category" class="px-2 py-0.5 rounded-md text-[10px] font-medium" :class="categoryBadgeClass">
                        {{ personality.category }}
                    </span>
                    
                    <!-- Version Tag -->
                    <span v-if="personality.version" class="px-1.5 py-0.5 rounded-md text-[10px] font-mono text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800">
                        v{{ personality.version }}
                    </span>
                </div>
            </div>
        </div>

        <!-- Card Body: Description & Source Meta -->
        <div class="px-4 py-3 grow flex flex-col justify-between">
            <p class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed line-clamp-3" :title="personality.description">
                {{ personality.description || 'No personality conditioning description provided.' }}
            </p>

            <div class="mt-3 flex items-center justify-between text-[11px] text-gray-400 dark:text-gray-500 pt-2 border-t border-gray-100 dark:border-gray-750/30">
                <span v-if="personality.author" class="truncate max-w-[50%]" :title="`Author: ${personality.author}`">
                    by <span class="font-medium text-gray-600 dark:text-gray-400">{{ personality.author }}</span>
                </span>
                <span v-else></span>

                <div v-if="personality.repository" class="flex items-center gap-1 truncate max-w-[50%]" :title="`Repository: ${personality.repository}`">
                    <IconGitBranch class="w-3 h-3 shrink-0" />
                    <span class="truncate">{{ personality.repository }}</span>
                </div>
            </div>
        </div>

        <!-- Card Footer: Actions & Progress -->
        <div class="p-3 border-t border-gray-150 dark:border-gray-750 bg-gray-50/80 dark:bg-gray-850/60 flex items-center justify-between gap-2 mt-auto">
            <!-- Left: Installation / Update Trigger -->
            <div class="flex-1 min-w-0">
                <TaskProgressIndicator 
                    v-if="task" 
                    :task="task" 
                />

                <div v-else class="flex items-center gap-1.5 w-full">
                    <!-- Not Installed -->
                    <button 
                        v-if="!personality.is_installed" 
                        @click="$emit('install', personality)" 
                        class="btn btn-primary btn-sm w-full text-xs justify-center shadow-sm font-semibold" 
                        :disabled="personality.is_legacy_scripted"
                    >
                        <IconArrowDownTray class="w-3.5 h-3.5 mr-1.5" />Install
                    </button>

                    <!-- Update Available -->
                    <button 
                        v-else-if="personality.update_available" 
                        @click="$emit('update', personality)" 
                        class="btn btn-warning btn-sm w-full text-xs justify-center shadow-sm font-semibold"
                    >
                        <IconArrowUpCircle class="w-3.5 h-3.5 mr-1.5" />Update v{{ personality.version }}
                    </button>

                    <!-- Installed State Badge -->
                    <span 
                        v-else 
                        class="inline-flex items-center justify-center gap-1.5 w-full px-3 py-1.5 text-xs font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200/80 dark:border-emerald-800/40 rounded-xl"
                    >
                        <IconCheckCircle class="w-3.5 h-3.5 text-emerald-500" />
                        Installed
                    </span>
                </div>
            </div>

            <!-- Right: Secondary Tools (README & Uninstall) -->
            <div class="shrink-0 flex items-center gap-1 pl-1 border-l border-gray-200 dark:border-gray-700">
                <!-- README Documentation -->
                <button 
                    v-if="personality.has_readme" 
                    @click="$emit('help', personality)" 
                    class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors" 
                    title="Open Documentation (README)"
                >
                    <IconBookOpen class="w-3.5 h-3.5" />
                </button>

                <!-- Uninstall Trigger -->
                <button 
                    v-if="personality.is_installed" 
                    @click="$emit('uninstall', personality)" 
                    class="p-1.5 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 text-gray-400 hover:text-rose-600 dark:hover:text-rose-400 transition-colors" 
                    title="Uninstall from System"
                >
                    <IconTrash class="w-3.5 h-3.5" />
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>