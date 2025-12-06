<!-- [UPDATE] frontend/webui/src/components/admin/ModerationQueue.vue -->
<script setup>
import { ref, onMounted, watch } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const items = ref([]);
const isLoading = ref(false);
const filter = ref('flagged'); // 'flagged' or 'pending' or '' for all

onMounted(() => {
    fetchQueue();
});

async function fetchQueue() {
    isLoading.value = true;
    items.value = []; // Clear current items while loading
    try {
        const res = await adminStore.fetchModerationQueue(filter.value);
        
        if (Array.isArray(res)) {
            // Filter out any malformed items
            items.value = res.filter(i => 
                i && 
                typeof i === 'object' && 
                i.id !== undefined && 
                i.id !== null && 
                i.type
            );
        } else {
            console.error("Moderation queue response is not an array:", res);
            items.value = [];
        }
    } catch (e) {
        console.error("Error fetching moderation queue:", e);
        uiStore.addNotification('Failed to load queue', 'error');
    } finally {
        isLoading.value = false;
    }
}

async function handleApprove(item) {
    if (!item?.id || !item?.type) return;
    try {
        await adminStore.approveContent(item.type, item.id);
        // Optimistically remove from list
        items.value = items.value.filter(i => i.id !== item.id || i.type !== item.type);
        uiStore.addNotification('Content validated.', 'success');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to approve content.', 'error');
        // Refresh to ensure sync
        fetchQueue();
    }
}

async function handleDelete(item) {
    if (!item?.id || !item?.type) return;
    if (!confirm('Are you sure you want to permanently delete this content?')) return;
    try {
        await adminStore.deleteContent(item.type, item.id);
        // Optimistically remove from list
        items.value = items.value.filter(i => i.id !== item.id || i.type !== item.type);
        uiStore.addNotification('Content deleted.', 'info');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to delete content.', 'error');
        // Refresh to ensure sync
        fetchQueue();
    }
}

function formatDate(dateStr) {
    if (!dateStr) return 'Unknown Date';
    try {
        return new Date(dateStr).toLocaleString();
    } catch {
        return dateStr;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg h-full flex flex-col">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
            <div>
                <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">Moderation Queue</h3>
                <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Review flagged posts and comments.</p>
            </div>
            <div class="flex items-center gap-3">
                <select v-model="filter" @change="fetchQueue" class="input-field-sm">
                    <option value="">All Pending</option>
                    <option value="flagged">Flagged Only</option>
                    <option value="pending">Unreviewed Only</option>
                </select>
                <button @click="fetchQueue" class="btn btn-secondary btn-sm" title="Refresh Queue">
                    <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoading}"/>
                </button>
            </div>
        </div>

        <div class="flex-grow overflow-y-auto p-0">
            <div v-if="isLoading" class="text-center py-10 text-gray-500">Loading queue...</div>
            <div v-else-if="items.length === 0" class="text-center py-10 text-gray-500">
                <p>No content pending moderation.</p>
            </div>
            <div v-else class="divide-y divide-gray-200 dark:divide-gray-700">
                <template v-for="item in items" :key="`${item.type}-${item.id}`">
                    <div class="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors">
                        <div class="flex items-start gap-4">
                            <!-- Author -->
                            <div class="flex-shrink-0 pt-1">
                                <UserAvatar 
                                    v-if="item.author" 
                                    :username="item.author.username" 
                                    :icon="item.author.icon" 
                                    size-class="h-10 w-10" 
                                />
                                <div v-else class="h-10 w-10 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-gray-500">
                                    <span class="text-xs">?</span>
                                </div>
                            </div>
                            
                            <!-- Content -->
                            <div class="flex-grow min-w-0">
                                <div class="flex items-center justify-between mb-1">
                                    <div class="flex items-center gap-2">
                                        <span class="font-bold text-sm">
                                            {{ item.author ? item.author.username : 'Unknown User' }}
                                        </span>
                                        <span class="text-xs text-gray-500">{{ formatDate(item.created_at) }}</span>
                                        <span class="px-2 py-0.5 text-xs rounded-full font-bold capitalize"
                                              :class="{
                                                  'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300': item.moderation_status === 'flagged',
                                                  'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300': item.moderation_status === 'pending'
                                              }">
                                            {{ item.moderation_status }} {{ item.type }}
                                        </span>
                                    </div>
                                </div>
                                <div class="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 p-3 rounded border dark:border-gray-600">
                                    {{ item.content }}
                                </div>
                            </div>

                            <!-- Actions -->
                            <div class="flex flex-col gap-2 flex-shrink-0 ml-2">
                                <button @click="handleApprove(item)" class="btn btn-success btn-sm flex items-center gap-1" title="Validate (Safe)">
                                    <IconCheckCircle class="w-4 h-4" /> Valid
                                </button>
                                <button @click="handleDelete(item)" class="btn btn-danger btn-sm flex items-center gap-1" title="Delete Permanently">
                                    <IconTrash class="w-4 h-4" /> Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </template>
            </div>
        </div>
    </div>
</template>
