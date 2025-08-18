<script setup>
import IconStar from '../../assets/icons/IconStar.vue';
import IconStarFilled from '../../assets/icons/IconStarFilled.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconArrowUpCircle from '../../assets/icons/IconArrowUpCircle.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import TaskProgressIndicator from './TaskProgressIndicator.vue';
import IconGitBranch from '../../assets/icons/ui/IconGitBranch.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';

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
    <div class="card">
        <div class="card-header">
            <img :src="prompt.icon || defaultIcon" :alt="prompt.name" class="card-icon" />
            <div class="flex-grow min-w-0">
                <div class="flex justify-between items-start">
                    <h3 class="card-title" :title="prompt.name">{{ prompt.name }}</h3>
                    <button @click.stop="$emit('star')" class="p-1.5 rounded-full transition-colors flex-shrink-0" :class="isStarred ? 'bg-yellow-400/20 text-yellow-500' : 'text-gray-400 hover:text-yellow-500'">
                        <IconStarFilled v-if="isStarred" class="w-5 h-5" />
                        <IconStar v-else class="w-5 h-5" />
                    </button>
                </div>
                <div class="card-tags">
                    <span v-if="prompt.is_installed" class="tag installed-tag">Installed</span>
                    <span v-if="prompt.author" class="tag">by {{ prompt.author }}</span>
                    <span v-if="prompt.category" class="tag">{{ prompt.category }}</span>
                    <span v-if="prompt.version" class="tag">v{{ prompt.version }}</span>
                </div>
            </div>
        </div>

        <div class="card-body">
            <p class="card-description" :title="prompt.description">{{ prompt.description }}</p>
        </div>
        
        <div v-if="prompt.repository" class="px-4 pb-2 text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
            <IconGitBranch class="w-3 h-3" />
            <span class="truncate" :title="`From: ${prompt.repository}`">{{ prompt.repository }}</span>
        </div>

        <div class="card-footer">
            <div class="flex-1 min-w-0">
                <TaskProgressIndicator v-if="task" :task="task" @view="$emit('view-task', task.id)" @cancel="$emit('cancel-install')" />
                
                <div v-else class="flex gap-2 w-full">
                    <button v-if="!prompt.is_installed" @click="$emit('install', prompt)" class="btn btn-primary w-full">
                        <IconArrowDownTray class="w-4 h-4 mr-2" />Install
                    </button>
                    
                    <button v-else-if="prompt.update_available" @click="$emit('update', prompt)" class="btn btn-warning w-full">
                        <IconArrowUpCircle class="w-4 h-4 mr-2" />Update
                    </button>

                    <button v-else @click="$emit('edit', prompt)" class="btn btn-secondary w-full">
                        <IconPencil class="w-4 h-4 mr-2" />Edit
                    </button>
                </div>
            </div>

            <div class="flex-shrink-0 flex gap-1">
                <button v-if="prompt.has_readme" @click="$emit('help', prompt)" class="btn btn-secondary p-2" title="Help">
                    <IconBookOpen class="w-4 h-4" />
                </button>
                 <button v-if="prompt.is_installed" @click="$emit('uninstall', prompt)" class="btn btn-danger-outline p-2" title="Uninstall">
                    <IconTrash class="w-4 h-4" />
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.card { @apply bg-white dark:bg-gray-800 rounded-lg shadow-md flex flex-col overflow-hidden transition-shadow hover:shadow-lg h-full; }
.card-header { @apply flex items-start p-4 gap-4; }
.card-icon { @apply w-12 h-12 object-cover rounded-md flex-shrink-0 bg-gray-200 dark:bg-gray-700 p-1; }
.card-body { @apply px-4 pb-4 flex-grow; }
.card-title { @apply font-bold text-base leading-tight; }
.card-tags { @apply flex flex-wrap gap-x-2 gap-y-1 mt-1; }
.tag { @apply text-xs bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded-full text-gray-600 dark:text-gray-300 capitalize; }
.installed-tag { @apply bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300; }
.card-description { @apply text-sm text-gray-600 dark:text-gray-400 mt-2 line-clamp-4; }
.card-footer { @apply p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-between gap-2 mt-auto; }
</style>