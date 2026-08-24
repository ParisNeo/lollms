<script setup>
import { computed } from 'vue';
import TaskProgressIndicator from '../TaskProgressIndicator.vue';
import IconStar from '../../../assets/icons/IconStar.vue';
import IconStarFilled from '../../../assets/icons/IconStarFilled.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconBookOpen from '../../../assets/icons/IconBookOpen.vue';
import IconInfo from '../../../assets/icons/IconInfo.vue';
import IconArrowUpCircle from '../../../assets/icons/IconArrowUpCircle.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconGitBranch from '../../../assets/icons/ui/IconGitBranch.vue';
import IconGlobeAlt from '../../../assets/icons/IconGlobeAlt.vue';
import IconPlayCircle from '../../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../../assets/icons/IconStopCircle.vue';
import IconWrenchScrewdriver from '../../../assets/icons/IconWrenchScrewdriver.vue';
import IconNoSymbol from '../../../assets/icons/IconNoSymbol.vue';
import IconCog from '../../../assets/icons/IconCog.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconArrowPath from '../../../assets/icons/IconArrowPath.vue';

const props = defineProps({
    app: { type: Object, required: true },
    task: { type: Object, default: null },
    isStarred: { type: Boolean, default: false },
    itemTypeName: { type: String, default: 'App' }
});

const emit = defineEmits([
    'star', 'install', 'update', 'uninstall', 'details', 'help', 
    'view-task', 'cancel-install', 'start', 'stop', 'fix', 
    'configure', 'purge', 'logs', 'delete', 'edit-env', 'restart'
]);

const defaultIcon = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMy4zNzUgMS41YTguMjc1IDguMjc1IDAgMCAwLTguMjc1IDguMjc1YzAgNC4xMjIgMi41NjEgNy42MyA2LjA3NyA4LjgzNWEuNzUuNzUgMCAwIDAgLjc2NC0uMTExYy4xMjUtLjA3OC4yNTgtLjE5LjM5OS0uMzE0bC4wMDQtLjAwNSNhLjQ5OC40OTggMCAwIDEgLjYxMy0uMDIzbDIuNDQyIDEuMTM4YTEuNSAxLjUgMCAwIDAgMS42OTktLjkxM2w0LjQxMy05LjU3N2E4LjI1IDE4LjI1IDAgMCAwLTkuOTU0LTkuOTU0bC05LjU3NyA0LjQxM2ExLjUgMS41IDAgMCAwLS45MTMgMS42OTlsMS4xMzggMi40NDJhLjQ5OC40OTggMCAwIDEgLS4wMjMuNjEzbC0uMDA1LjAwNC0uMzE0LjM5OWEuNzUuNzUgMCAwIDAtLjExMS43NjRBMTEuMjIgMTEuMjIgMCAwIDEtMy4zNzUgMTguNWMtNS4wNzIgMC05LjE4OC00LjExNi05LjE4OC05LjE4OGE5LjE4OCA5LjE4OCAwIDAgMSAxLjYxNy01LjE2MmMuMjQ2LS40Mi4wMzgtLjkxOC0uMzY4LTEuMTU3bC0xLjQyNS0uODM4YTEuNSAxLjUgMCAwIDAtMi4wODYuNDlMMy4zNzUgMS41em00LjQ4OCAxMy4wMjNhLjUuNSAwIDAgMS0uMzU0LS4xNDdsLTEuNTQyLTEuNTQxYS41LjUgMCAxIDEgLjcwOC0uNzA4bDEuNTQxIDEuNTQyYS41LjUgMCAwIDEgLS4zNTQuODU0em0yLjk0LTIuOTRhLjUuNSAwIDAgMS0uMzU0LS4xNDZsLTEuNTQxLTEuNTQyYS41LjUgMCAwIDEgLjcwNy0uNzA4bDEuNTQyIDEuNTQxYS41LjUgMCAwIDEgLS4zNTQuODU0em0tMi45NC0yLjk0YS41LjUgMCAwIDEtLjM1My0uMTQ2bC0xLjU0Mi0xLjU0MmEuNS41IDAgMCAxIC43MDctLjcwN2wxLjU0MiAxLjU0MWEuNS41IDAgMCAxLS4zNTQuODUzem0yLjk0LTIuOTRhLjUuNSAwIDAgMS0uMzU0LS4xNDZsLTEuNTQxLTEuNTQyYS41LjUgMCAwIDEgLjcwNy0uNzA4bDEuNTQyIDEuNTQxYS41LjUgMCAwIDEgLS4zNTQuODU0em00LjQ4OC0uNzU3YS41LjUgMCAwIDEtLjM1NC0uMTQ3bC0xLjU0Mi0xLjU0MWEuNS41IDAgMCAxIC43MDgtLjcwOGwxLjU0MSAxLjU0MWEuNS41IDAgMCAxLS4zNTQuODU0em0yLjk0LTIuOTRhLjUuNSAwIDAgMS0uMzU0LS4xNDZsLTEuNTQxLTEuNTQyYS41LjUgMCAwIDEgLjcwNy0uNzA4bDEuNTQyIDEuNTQxYS41LjUgMCAwIDEgLS4zNTQuODU0em0tMS40NzEtNC40N2EuNS41IDAgMCAxLS4zNTQtLjE0N2wtMS41NDItMS41NDFhLjUuNSAwIDAgMSAuNzA4LS43MDhsMS41NDEgMS41NDFhLjUuNSAwIDAgMS0uMzU0Ljg1NHoiIGNsaXAtcnVsZT0iZXZlbm9kZCIgLz4KPC9zdmc+Cg==';
</script>

<template>
    <div 
        class="group relative bg-white/95 dark:bg-gray-800/90 rounded-2xl border border-gray-200/80 dark:border-gray-700/70 shadow-sm hover:shadow-xl hover:-translate-y-1 hover:border-blue-500/40 dark:hover:border-blue-500/40 flex flex-col overflow-hidden transition-all duration-300 h-full backdrop-blur-sm"
        :class="{ 'opacity-60 pointer-events-none': app.is_legacy_scripted }"
    >
        <!-- Legacy Incompatibility Overlay -->
        <div v-if="app.is_legacy_scripted" class="absolute inset-0 bg-gray-900/60 backdrop-blur-sm flex flex-col items-center justify-center rounded-2xl z-20 p-4 text-center" title="Legacy scripted personality incompatible with this version.">
            <IconNoSymbol class="w-12 h-12 text-rose-500 mb-2 animate-pulse" />
            <span class="text-xs font-semibold text-white">Legacy Scripted Item</span>
            <span class="text-[10px] text-gray-300 mt-1">Incompatible with current runtime</span>
        </div>

        <!-- Card Top Bar: Icon + Title + Status + Star -->
        <div class="flex items-start p-4 gap-3.5 border-b border-gray-100 dark:border-gray-750/50">
            <!-- App Icon -->
            <div class="relative shrink-0">
                <img 
                    :src="app.icon || defaultIcon" 
                    :alt="app.name" 
                    class="w-12 h-12 rounded-xl object-cover bg-gray-50 dark:bg-gray-700/80 p-1 border border-gray-200/60 dark:border-gray-600/50 shadow-inner group-hover:scale-105 transition-transform duration-300" 
                />
                <!-- Live Pulse Dot for Running Apps -->
                <span 
                    v-if="app.is_installed && app.status === 'running'" 
                    class="absolute -top-1 -right-1 flex h-3.5 w-3.5"
                    title="Service active"
                >
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500 border-2 border-white dark:border-gray-800"></span>
                </span>
            </div>

            <!-- Meta & Title -->
            <div class="grow min-w-0">
                <div class="flex justify-between items-start gap-1">
                    <h3 class="font-bold text-sm text-gray-900 dark:text-white truncate leading-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors" :title="app.name">
                        {{ app.name }}
                    </h3>
                    <button 
                        @click.stop="$emit('star', app.name)" 
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
                    <!-- Status Badge -->
                    <span 
                        v-if="app.is_broken" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border border-rose-200/60 dark:border-rose-800/40 flex items-center gap-1"
                    >
                        <span class="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                        Broken
                    </span>
                    <span 
                        v-else-if="app.is_installed && app.status === 'running'" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200/60 dark:border-emerald-800/40 flex items-center gap-1"
                    >
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                        Running <span v-if="app.port" class="opacity-75 font-mono">:{{ app.port }}</span>
                    </span>
                    <span 
                        v-else-if="app.is_installed" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-gray-100 text-gray-700 dark:bg-gray-700/60 dark:text-gray-300 border border-gray-200/60 dark:border-gray-600/40"
                    >
                        {{ app.status || 'Installed' }}
                    </span>
                    <span 
                        v-else-if="app.repository === 'Registered'" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/40"
                    >
                        Registered
                    </span>

                    <!-- Update Available Badge -->
                    <span 
                        v-if="app.is_installed && app.update_available" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-300/60 dark:border-amber-700/40 animate-pulse"
                        :title="`Update available: ${app.repo_version}`"
                    >
                        Update: v{{ app.repo_version }}
                    </span>

                    <!-- Category & Version -->
                    <span v-if="app.category" class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-gray-100 dark:bg-gray-700/50 text-gray-600 dark:text-gray-300">
                        {{ app.category }}
                    </span>
                    <span v-if="app.version && !app.update_available" class="px-1.5 py-0.5 rounded-md text-[10px] font-mono text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800">
                        v{{ app.version }}
                    </span>
                </div>
            </div>
        </div>

        <!-- Card Body: Description & Source Meta -->
        <div class="px-4 py-3 grow flex flex-col justify-between">
            <p class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed line-clamp-3" :title="app.description">
                {{ app.description || 'No description provided.' }}
            </p>

            <div class="mt-3 flex items-center justify-between text-[11px] text-gray-400 dark:text-gray-500 pt-2 border-t border-gray-100 dark:border-gray-750/30">
                <span v-if="app.author" class="truncate max-w-[50%]" :title="`By: ${app.author}`">
                    by <span class="font-medium text-gray-600 dark:text-gray-400">{{ app.author }}</span>
                </span>
                <span v-else></span>

                <div v-if="app.repository" class="flex items-center gap-1 truncate max-w-[50%]" :title="`Source: ${app.repository}`">
                    <IconGitBranch class="w-3 h-3 shrink-0" />
                    <span class="truncate">{{ app.repository }}</span>
                </div>
            </div>
        </div>

        <!-- Card Footer: Actions & Progress -->
        <div class="p-3 border-t border-gray-150 dark:border-gray-750 bg-gray-50/80 dark:bg-gray-850/60 flex items-center justify-between gap-2 mt-auto">
            <!-- Left: Main Execution / Lifecycle Control -->
            <div class="flex-1 min-w-0">
                <!-- Task Progress Bar -->
                <TaskProgressIndicator 
                    v-if="task" 
                    :task="task" 
                    @view="$emit('view-task', task.id)" 
                    @cancel="$emit('cancel-install')" 
                />
                
                <div v-else class="flex items-center gap-1.5 w-full">
                    <!-- Broken State Fix / Purge -->
                    <template v-if="app.is_broken">
                        <button @click="$emit('fix', app)" class="btn btn-warning btn-sm flex-1 text-xs justify-center shadow-sm" title="Attempt to fix broken DB record">
                            <IconWrenchScrewdriver class="w-3.5 h-3.5 mr-1" />Fix
                        </button>
                        <button @click="$emit('purge', app)" class="btn btn-danger btn-sm flex-1 text-xs justify-center shadow-sm" title="Purge files from disk">
                            <IconTrash class="w-3.5 h-3.5 mr-1" />Purge
                        </button>
                    </template>

                    <!-- Not Installed: Install Trigger -->
                    <button 
                        v-else-if="!app.is_installed && app.repository !== 'Registered'" 
                        @click="$emit('install', app)" 
                        class="btn btn-primary btn-sm w-full text-xs justify-center shadow-sm font-semibold" 
                        :disabled="app.is_legacy_scripted"
                    >
                        <IconArrowDownTray class="w-3.5 h-3.5 mr-1.5" />Install
                    </button>
                    
                    <!-- Update Available Trigger -->
                    <button 
                        v-else-if="app.is_installed && app.update_available" 
                        @click="$emit('update', app)" 
                        class="btn btn-warning btn-sm w-full text-xs justify-center shadow-sm font-semibold"
                    >
                        <IconArrowUpCircle class="w-3.5 h-3.5 mr-1.5" />Update v{{ app.repo_version }}
                    </button>

                    <!-- Installed & Stopped: Start Trigger -->
                    <button 
                        v-else-if="app.is_installed && app.status !== 'running'" 
                        @click="$emit('start', app)" 
                        class="btn btn-success btn-sm w-full text-xs justify-center shadow-sm font-semibold" 
                        title="Start application"
                    >
                        <IconPlayCircle class="w-4 h-4 mr-1.5" />Start
                    </button>

                    <!-- Installed & Running: Open + Restart + Stop Group -->
                    <div v-else-if="app.is_installed && app.status === 'running'" class="flex items-center gap-1.5 w-full">
                        <a 
                            v-if="app.url" 
                            :href="app.url" 
                            target="_blank" 
                            class="btn btn-primary btn-sm flex-1 text-xs justify-center font-semibold shadow-sm" 
                            title="Open Application in New Tab"
                        >
                            <IconGlobeAlt class="w-3.5 h-3.5 mr-1" />Open
                        </a>
                        <button 
                            @click="$emit('restart', app)" 
                            class="p-1.5 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 transition-colors shadow-sm" 
                            title="Restart application"
                        >
                            <IconArrowPath class="w-4 h-4" />
                        </button>
                        <button 
                            @click="$emit('stop', app)" 
                            class="p-1.5 rounded-lg bg-amber-100 hover:bg-amber-200 dark:bg-amber-950/60 dark:hover:bg-amber-900/80 text-amber-700 dark:text-amber-300 transition-colors shadow-sm" 
                            title="Stop application"
                        >
                            <IconStopCircle class="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>

            <!-- Right: Secondary Utility Toolbar -->
            <div class="shrink-0 flex items-center gap-1 pl-1 border-l border-gray-200 dark:border-gray-700">
                <template v-if="!task && !app.is_broken">
                    <!-- Config Schema Modal -->
                    <button 
                        v-if="app.is_installed && app.has_config_schema" 
                        @click="$emit('configure', app)" 
                        class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors" 
                        title="Configure Settings"
                    >
                        <IconCog class="w-3.5 h-3.5" />
                    </button>

                    <!-- .env Editor -->
                    <button 
                        v-if="app.is_installed && app.has_dot_env_config" 
                        @click="$emit('edit-env', app)" 
                        class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors" 
                        title="Edit .env file"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3.5 h-3.5">
                            <path d="m2.695 14.762-1.262 3.155a.5.5 0 0 0 .65.65l3.155-1.262a.5.5 0 0 0 .134-.05l8.606-8.606-3.155-3.155-8.606 8.606a.5.5 0 0 0-.05.134Z" />
                            <path d="M13.44 3.19a.5.5 0 0 0 0 .707l2.845 2.845a.5.5 0 0 0 .707 0l1.262-1.262a.5.5 0 0 0 0-.707l-2.845-2.845a.5.5 0 0 0-.707 0l-1.262 1.262Z" />
                        </svg>
                    </button>

                    <!-- Logs Viewer -->
                    <button 
                        v-if="app.is_installed" 
                        @click="$emit('logs', app)" 
                        class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors" 
                        title="View Process Logs"
                    >
                        <IconFileText class="w-3.5 h-3.5" />
                    </button>
                </template>

                <!-- Information / Details -->
                <button 
                    @click="$emit('details', app)" 
                    class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors" 
                    title="View Details"
                >
                    <IconInfo class="w-3.5 h-3.5" />
                </button>

                <!-- README Documentation -->
                <button 
                    v-if="app.has_readme" 
                    @click="$emit('help', app)" 
                    class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors" 
                    title="Open Documentation (README)"
                >
                    <IconBookOpen class="w-3.5 h-3.5" />
                </button>

                <!-- Uninstall Trigger -->
                <button 
                    v-if="app.is_installed" 
                    @click="$emit('uninstall', app)" 
                    class="p-1.5 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 text-gray-400 hover:text-rose-600 dark:hover:text-rose-400 transition-colors" 
                    title="Uninstall"
                >
                    <IconTrash class="w-3.5 h-3.5" />
                </button>

                <!-- Delete Registration (for registered items) -->
                <button 
                    v-if="app.repository === 'Registered'" 
                    @click="$emit('delete', app)" 
                    class="p-1.5 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 text-gray-400 hover:text-rose-600 dark:hover:text-rose-400 transition-colors" 
                    title="Delete Registration"
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