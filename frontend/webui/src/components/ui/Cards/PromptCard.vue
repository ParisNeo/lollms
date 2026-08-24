<script setup>
import IconStar from '../../../assets/icons/IconStar.vue';
import IconStarFilled from '../../../assets/icons/IconStarFilled.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconBookOpen from '../../../assets/icons/IconBookOpen.vue';
import IconArrowUpCircle from '../../../assets/icons/IconArrowUpCircle.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import TaskProgressIndicator from '../TaskProgressIndicator.vue';
import IconGitBranch from '../../../assets/icons/ui/IconGitBranch.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';

const props = defineProps({
    prompt: { type: Object, required: true },
    task: { type: Object, default: null },
    isStarred: { type: Boolean, default: false },
});

const emit = defineEmits([
    'star', 'install', 'update', 'uninstall', 'help', 'edit',
    'view-task', 'cancel-install'
]);

const defaultIcon = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIj4KICA8cGF0aCBmaWxsLXJ1bGU9ImV2ZW5vZGQiIGQ9Ik05LjE3MiA0LjU4NmMxLjA3Mi0xLjA3MiAyLjgyNy0xLjA3MiAzLjkwNiAwIGwxLjkyOCAxLjkyOGMuMDkuMDkuMTQ2LjIxMy4xNDYuMzM3djEuMjE5Yy43MTMuMDU0IDEuMzk3LjIxOCAyLjAyOC40NzhsMS45MS0xLjA0Yy4xNTYtLjA4NS4zMy0uMTA0LjQ5OC0uMDVMMjAuNzUgOC4xN2MuMjU0LjA4NC4zOTQuMzQzLjM5NC42MjV2My40M2MwIC4yODItLjE0LjU0MS0uMzk0LjYyNWwtMi42NTQgMS40NDRjLS4xNjguMDktLjM0Mi4xMDgtLjUxLjA1M2wtMS45MS0xLjA0Yy0uNjMyLS4yNi0xLjMxNS0uNDI0LTIuMDI4LS40NzhWNS41NUw5LjE3MiA0LjU4NnpNNCAxMS4yNWMwLS45OTQuNTk2LTEuODYgMS40NDctMi4yNTlMMTAuMDMgNC40M2MtLjM2OS4wMjYtLjczLjEzOC0xLjA3Mi4zMzJsLTEuOTI4IDEuOTI4Yy0xLjA3MiAxLjA3Mi0xLjA3MiAyLjgyNyAwIDMuOTA2bDQuNTk2IDQuNTk2Yy4zNzQuMzc0LjU4Ni44OC41ODYgMS40MTR2My4yMDJjLS45NC4wNS0xLjg1NS4zNzktMi41My45NDNsLTEuNzM2IDEuNzM3YTEuNSAxLjUgMCAwMS0yLjEyMiAwTDMgMTkuNWExLjUgMS41IDAgMDEgMC0yLjEyMWwxLjczNy0xLjczN2MuNTY0LS41NjQgMS4yMzYtLjkxNCAxLjk0My0uOTk2YTQuNDgzIDQuNDgzIDAgMDEtLjY4LS44NDhWMTMuNWExLjUgMS41IDAgMDEtLjQ0LTEuMDYxTDEuNDQ3IDkuMDA5QTcuNSA3LjUgMCAwMSA0IDQuNUMyLjQ4IDEuNSA1LjMzNCAxLjUgNy4wMyA1LjAzaDEuOTQzYy4wMy4zNjIuMTE4LjcxLjI2IDEuMDQzTDQuNDMgMTAuODNjLS44NTEuNDUtMS40MyAxLjMyMi0xLjQzIDIuMjQ4djIuODQ4YzAgMS4zMy42NzIgMi41MzMgMS42ODggMy4yMThhLjc1Ljc1IDAgMTEtLjgyMiAxLjE4NEEzLjAwMiAzLjAwMiAwIDAgMSA0IDE2LjM0OFYxMS4yNXoiIGNsaXAtcnVsZT0iZXZlbm9kZCIgLz4KPC9zdmc+';
</script>

<template>
    <div class="group relative bg-white/95 dark:bg-gray-800/90 rounded-2xl border border-gray-200/80 dark:border-gray-700/70 shadow-sm hover:shadow-xl hover:-translate-y-1 hover:border-blue-500/40 dark:hover:border-blue-500/40 flex flex-col overflow-hidden transition-all duration-300 h-full backdrop-blur-sm">
        <!-- Top Bar: Icon + Title + Status + Star -->
        <div class="flex items-start p-4 gap-3.5 border-b border-gray-100 dark:border-gray-750/50">
            <!-- Icon -->
            <div class="relative shrink-0">
                <img 
                    v-if="prompt.icon" 
                    :src="prompt.icon" 
                    :alt="prompt.name" 
                    class="w-12 h-12 rounded-xl object-cover bg-gray-50 dark:bg-gray-700/80 p-1 border border-gray-200/60 dark:border-gray-600/50 shadow-inner group-hover:scale-105 transition-transform duration-300" 
                />
                <div 
                    v-else 
                    class="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 dark:from-indigo-950/40 dark:to-purple-950/40 border border-indigo-200/60 dark:border-indigo-800/40 flex items-center justify-center text-indigo-600 dark:text-indigo-400 group-hover:scale-105 transition-transform duration-300 shadow-inner"
                >
                    <IconSparkles class="w-6 h-6" />
                </div>
            </div>

            <!-- Meta & Title -->
            <div class="grow min-w-0">
                <div class="flex justify-between items-start gap-1">
                    <h3 class="font-bold text-sm text-gray-900 dark:text-white truncate leading-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors" :title="prompt.name">
                        {{ prompt.name }}
                    </h3>
                    <button 
                        @click.stop="$emit('star')" 
                        class="p-1 rounded-lg transition-all duration-200 shrink-0 hover:scale-110 active:scale-95" 
                        :class="isStarred ? 'bg-amber-400/15 text-amber-500' : 'text-gray-300 dark:text-gray-600 hover:text-amber-400'"
                        :title="isStarred ? 'Remove from favorites' : 'Add to favorites'"
                    >
                        <IconStarFilled v-if="isStarred" class="w-4 h-4" />
                        <IconStar v-else class="w-4 h-4" />
                    </button>
                </div>

                <!-- Status Badges & Category -->
                <div class="flex flex-wrap items-center gap-1.5 mt-1.5">
                    <span 
                        v-if="prompt.is_installed" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200/60 dark:border-emerald-800/40 flex items-center gap-1"
                    >
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        Installed
                    </span>

                    <span 
                        v-if="prompt.update_available" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-300/60 dark:border-amber-700/40 animate-pulse"
                    >
                        Update: v{{ prompt.repo_version }}
                    </span>

                    <span v-if="prompt.category" class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-gray-100 dark:bg-gray-700/50 text-gray-600 dark:text-gray-300">
                        {{ prompt.category }}
                    </span>
                    <span v-if="prompt.version" class="px-1.5 py-0.5 rounded-md text-[10px] font-mono text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800">
                        v{{ prompt.version }}
                    </span>
                </div>
            </div>
        </div>

        <!-- Card Body: Description & Source Meta -->
        <div class="px-4 py-3 grow flex flex-col justify-between">
            <p class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed line-clamp-3" :title="prompt.description">
                {{ prompt.description || 'No prompt description provided.' }}
            </p>

            <div class="mt-3 flex items-center justify-between text-[11px] text-gray-400 dark:text-gray-500 pt-2 border-t border-gray-100 dark:border-gray-750/30">
                <span v-if="prompt.author" class="truncate max-w-[50%]" :title="`By: ${prompt.author}`">
                    by <span class="font-medium text-gray-600 dark:text-gray-400">{{ prompt.author }}</span>
                </span>
                <span v-else></span>

                <div v-if="prompt.repository" class="flex items-center gap-1 truncate max-w-[50%]" :title="`Source: ${prompt.repository}`">
                    <IconGitBranch class="w-3 h-3 shrink-0" />
                    <span class="truncate">{{ prompt.repository }}</span>
                </div>
            </div>
        </div>

        <!-- Card Footer: Actions & Progress -->
        <div class="p-3 border-t border-gray-150 dark:border-gray-750 bg-gray-50/80 dark:bg-gray-850/60 flex items-center justify-between gap-2 mt-auto">
            <div class="flex-1 min-w-0">
                <TaskProgressIndicator 
                    v-if="task" 
                    :task="task" 
                    @view="$emit('view-task', task.id)" 
                    @cancel="$emit('cancel-install')" 
                />
                
                <div v-else class="flex gap-2 w-full">
                    <button 
                        v-if="!prompt.is_installed" 
                        @click="$emit('install', prompt)" 
                        class="btn btn-primary btn-sm w-full text-xs justify-center shadow-sm font-semibold"
                    >
                        <IconArrowDownTray class="w-3.5 h-3.5 mr-1.5" />Install Prompt
                    </button>
                    
                    <button 
                        v-else-if="prompt.update_available" 
                        @click="$emit('update', prompt)" 
                        class="btn btn-warning btn-sm w-full text-xs justify-center shadow-sm font-semibold"
                    >
                        <IconArrowUpCircle class="w-3.5 h-3.5 mr-1.5" />Update
                    </button>

                    <button 
                        v-else 
                        @click="$emit('edit', prompt)" 
                        class="btn btn-secondary btn-sm w-full text-xs justify-center shadow-sm font-semibold"
                    >
                        <IconPencil class="w-3.5 h-3.5 mr-1.5" />Edit Prompt
                    </button>
                </div>
            </div>

            <div class="shrink-0 flex items-center gap-1 pl-1 border-l border-gray-200 dark:border-gray-700">
                <button 
                    v-if="prompt.has_readme" 
                    @click="$emit('help', prompt)" 
                    class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors" 
                    title="Documentation (README)"
                >
                    <IconBookOpen class="w-3.5 h-3.5" />
                </button>
                <button 
                    v-if="prompt.is_installed" 
                    @click="$emit('uninstall', prompt)" 
                    class="p-1.5 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 text-gray-400 hover:text-rose-600 dark:hover:text-rose-400 transition-colors" 
                    title="Uninstall prompt"
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