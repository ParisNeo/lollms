<!-- [UPDATE] frontend/webui/src/components/ui/AppCard.vue -->
<script setup>
import IconStar from '../../assets/icons/IconStar.vue';
import IconStarFilled from '../../assets/icons/IconStarFilled.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconArrowUpCircle from '../../assets/icons/IconArrowUpCircle.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import TaskProgressIndicator from './TaskProgressIndicator.vue';
import IconGitBranch from '../../assets/icons/ui/IconGitBranch.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';
import IconNoSymbol from '../../assets/icons/IconNoSymbol.vue';
import IconCog from '../../assets/icons/IconCog.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';

const props = defineProps({
    app: { type: Object, required: true },
    task: { type: Object, default: null },
    isStarred: { type: Boolean, default: false },
    itemTypeName: { type: String, default: 'App' }
});

const emit = defineEmits([
    'star', 'install', 'update', 'uninstall', 'details', 'help', 
    'view-task', 'cancel-install', 'start', 'stop', 'fix', 
    'configure', 'purge', 'logs', 'delete'
]);

const defaultIcon = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMy4zNzUgMS41YTguMjc1IDguMjc1IDAgMCAwLTguMjc1IDguMjc1YzAgNC4xMjIgMi41NjEgNy42MyA2LjA3NyA4LjgzNWEuNzUuNzUgMCAwIDAgLjc2NC0uMTExYy4xMjUtLjA3OC4yNTgtLjE5LjM5OS0uMzE0bC4wMDQtLjAwNSNhLjQ5OC40OTggMCAwIDEgLjYxMy0uMDIzbDIuNDQyIDEuMTM4YTEuNSAxLjUgMCAwIDAgMS42OTktLjkxM2w0LjQxMy05LjU3N2E4LjI1IDE4LjI1IDAgMCAwLTkuOTU0LTkuOTU0bC05LjU3NyA0LjQxM2ExLjUgMS41IDAgMCAwLS45MTMgMS42OTlsMS4xMzggMi40NDJhLjQ5OC40OTggMCAwIDEgLS4wMjMuNjEzbC0uMDA1LjAwNC0uMzE0LjM5OWEuNzUuNzUgMCAwIDAtLjExMS43NjRBMTEuMjIgMTEuMjIgMCAwIDEtMy4zNzUgMTguNWMtNS4wNzIgMC05LjE4OC00LjExNi05LjE4OC05LjE4OGE5LjE4OCA5LjE4OCAwIDAgMSAxLjYxNy01LjE2MmMuMjQ2LS40Mi4wMzgtLjkxOC0uMzY4LTEuMTU3bC0xLjQyNS0uODM4YTEuNSAxLjUgMCAwIDAtMi4wODYuNDlMMy4zNzUgMS41em00LjQ4OCAxMy4wMjNhLjUuNSAwIDAgMS0uMzU0LS4xNDdsLTEuNTQyLTEuNTQxYS41LjUgMCAxIDEgLjcwOC0uNzA4bDEuNTQxIDEuNTQyYS41LjUgMCAwIDEgLS4zNTQuODU0em0yLjk0LTIuOTRhLjUuNSAwIDAgMS0uMzU0LS4xNDZsLTEuNTQxLTEuNTQyYS41LjUgMCAwIDEgLjcwNy0uNzA4bDEuNTQyIDEuNTQxYS41LjUgMCAwIDEgLS4zNTQuODU0em0tMi45NC0yLjk0YS41LjUgMCAwIDEtLjM1My0uMTQ2bC0xLjU0Mi0xLjU0MmEuNS41IDAgMCAxIC43MDctLjcwN2wxLjU0MiAxLjU0MWEuNS41IDAgMCAxLS4zNTQuODUzem0yLjk0LTIuOTRhLjUuNSAwIDAgMS0uMzU0LS4xNDZsLTEuNTQxLTEuNTQyYS41LjUgMCAwIDEgLjcwNy0uNzA4bDEuNTQyIDEuNTQxYS41LjUgMCAwIDEgLS4zNTQuODU0em00LjQ4OC0uNzU3YS41LjUgMCAwIDEtLjM1NC0uMTQ3bC0xLjU0Mi0xLjU0MWEuNS41IDAgMCAxIC43MDgtLjcwOGwxLjU0MSAxLjU0MWEuNS41IDAgMCAxLS4zNTQuODU0em0yLjk0LTIuOTRhLjUuNSAwIDAgMS0uMzU0LS4xNDZsLTEuNTQxLTEuNTQyYS41LjUgMCAwIDEgLjcwNy0uNzA4bDEuNTQyIDEuNTQxYS41LjUgMCAwIDEgLS4zNTQuODU0em0tMS40NzEtNC40N2EuNS41IDAgMCAxLS4zNTQtLjE0N2wtMS41NDItMS41NDFhLjUuNSAwIDAgMSAuNzA4LS43MDhsMS41NDEgMS41NDFhLjUuNSAwIDAgMS0uMzU0Ljg1NHoiIGNsaXAtcnVsZT0iZXZlbm9kZCIgLz4KPC9zdmc+Cg==';
</script>

<template>
    <div class="card" :class="{ 'opacity-60 pointer-events-none': app.is_legacy_scripted }">
        <div v-if="app.is_legacy_scripted" class="absolute inset-0 bg-gray-500/30 dark:bg-gray-900/50 flex items-center justify-center rounded-lg z-10" title="This is a legacy scripted personality and is not compatible with this version of the application.">
            <IconNoSymbol class="w-16 h-16 text-red-500" />
        </div>

        <div class="card-header">
            <img :src="app.icon || defaultIcon" :alt="app.name" class="card-icon" />
            <div class="flex-grow min-w-0">
                <div class="flex justify-between items-start">
                    <h3 class="card-title" :title="app.name">{{ app.name }}</h3>
                    <button @click.stop="$emit('star', app.name)" class="p-1.5 rounded-full transition-colors flex-shrink-0" :class="isStarred ? 'bg-yellow-400/20 text-yellow-500' : 'text-gray-400 hover:text-yellow-500'">
                        <IconStarFilled v-if="isStarred" class="w-5 h-5" />
                        <IconStar v-else class="w-5 h-5" />
                    </button>
                </div>
                <div class="card-tags">
                    <span v-if="app.is_broken" class="tag installed-tag-broken">Broken</span>
                    <span v-else-if="app.is_installed" class="tag" :class="{ 'installed-tag-running': app.status === 'running', 'installed-tag-stopped': app.status !== 'running' }">{{ app.status || 'Installed' }}</span>
                    <span v-else-if="app.repository === 'Registered'" class="tag registered-tag">Registered</span>
                    <span v-if="app.author" class="tag">by {{ app.author }}</span>
                    <span v-if="app.category" class="tag">{{ app.category }}</span>
                    <span v-if="app.version" class="tag">v{{ app.version }}</span>
                </div>
            </div>
        </div>

        <div class="card-body">
            <p class="card-description" :title="app.description">{{ app.description }}</p>
        </div>
        
        <div v-if="app.repository" class="px-4 pb-2 text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
            <IconGitBranch class="w-3 h-3" />
            <span class="truncate" :title="`From: ${app.repository}`">{{ app.repository }}</span>
        </div>

        <div class="card-footer">
            <div class="flex-1 min-w-0">
                <TaskProgressIndicator v-if="task" :task="task" @view="$emit('view-task', task.id)" @cancel="$emit('cancel-install')" />
                
                <div v-else class="flex gap-2 w-full">
                    <div v-if="app.is_broken" class="flex gap-2 w-full">
                        <button @click="$emit('fix', app)" class="btn btn-warning w-full" title="Fix Installation"><IconWrenchScrewdriver class="w-4 h-4 mr-2" />Fix</button>
                        <button @click="$emit('purge', app)" class="btn btn-danger w-full" title="Purge Installation"><IconTrash class="w-4 h-4 mr-2" />Purge</button>
                    </div>

                    <button v-else-if="!app.is_installed && app.repository !== 'Registered'" @click="$emit('install', app)" class="btn btn-primary w-full" :disabled="app.is_legacy_scripted">
                        <IconArrowDownTray class="w-4 h-4 mr-2" />Install
                    </button>
                    
                    <button v-else-if="app.is_installed && app.update_available" @click="$emit('update', app)" class="btn btn-warning w-full">
                        <IconArrowUpCircle class="w-4 h-4 mr-2" />Update to {{ app.repo_version }}
                    </button>

                    <button v-else-if="app.is_installed && app.status !== 'running'" @click="$emit('start', app)" class="btn btn-success p-2" title="Start App">
                        <IconPlayCircle class="w-5 h-5" />
                    </button>

                    <div v-else-if="app.is_installed && app.status === 'running'" class="flex items-center gap-2">
                        <a v-if="app.url" :href="app.url" target="_blank" class="btn btn-primary p-2" title="Open App">
                            <IconGlobeAlt class="w-5 h-5" />
                        </a>
                        <button @click="$emit('stop', app)" class="btn btn-warning p-2" title="Stop App">
                            <IconStopCircle class="w-5 h-5" />
                        </button>
                    </div>
                </div>
            </div>

            <div class="flex-shrink-0 flex gap-1">
                <template v-if="!task && !app.is_broken">
                    <button v-if="app.is_installed" @click="$emit('logs', app)" class="btn btn-secondary p-2" title="View Logs">
                        <IconFileText class="w-4 h-4" />
                    </button>
                    <button v-if="app.is_installed || app.repository === 'Registered'" @click="$emit('configure', app)" class="btn btn-secondary p-2" title="Configure">
                        <IconCog class="w-4 h-4" />
                    </button>
                </template>

                <button @click="$emit('details', app)" class="btn btn-secondary p-2" title="Details">
                    <IconInfo class="w-4 h-4" />
                </button>
                <button v-if="app.has_readme" @click="$emit('help', app)" class="btn btn-secondary p-2" title="Help">
                    <IconBookOpen class="w-4 h-4" />
                </button>
                 <button v-if="app.is_installed" @click="$emit('uninstall', app)" class="btn btn-danger-outline p-2" title="Uninstall">
                    <IconTrash class="w-4 h-4" />
                </button>
                 <button v-if="app.repository === 'Registered'" @click="$emit('delete', app)" class="btn btn-danger-outline p-2" title="Delete Registration">
                    <IconTrash class="w-4 h-4" />
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.card { @apply relative bg-white dark:bg-gray-800 rounded-lg shadow-md flex flex-col overflow-hidden transition-shadow hover:shadow-lg h-full; }
.card-header { @apply flex items-start p-4 gap-4; }
.card-icon { @apply w-12 h-12 object-cover rounded-md flex-shrink-0; }
.card-body { @apply px-4 pb-4 flex-grow; }
.card-title { @apply font-bold text-base leading-tight; }
.card-tags { @apply flex flex-wrap gap-x-2 gap-y-1 mt-1; }
.tag { @apply text-xs bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded-full text-gray-600 dark:text-gray-300 capitalize; }
.installed-tag-running { @apply bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300; }
.installed-tag-stopped { @apply bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-300; }
.installed-tag-broken { @apply bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300; }
.registered-tag { @apply bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300; }
.card-description { @apply text-sm text-gray-600 dark:text-gray-400 mt-2 line-clamp-4; }
.card-footer { @apply p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-between gap-2 mt-auto; }
</style>