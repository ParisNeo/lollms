<script setup>
import { ref, onMounted } from 'vue';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';

const feeds = ref([]);
const isLoading = ref(false);
const isFormVisible = ref(false);
const isEditing = ref(false);
const form = ref({ id: null, name: '', url: '', is_active: true });
const uiStore = useUiStore();
const adminStore = useAdminStore();
const isScraping = ref(false);

async function fetchFeeds() {
    isLoading.value = true;
    try {
        const response = await apiClient.get('/api/admin/rss-feeds');
        feeds.value = response.data;
    } catch (error) {
        uiStore.addNotification('Failed to load RSS feeds.', 'error');
    } finally {
        isLoading.value = false;
    }
}

function showAddForm() {
    isEditing.value = false;
    form.value = { id: null, name: '', url: '', is_active: true };
    isFormVisible.value = true;
}

function showEditForm(feed) {
    isEditing.value = true;
    form.value = { ...feed };
    isFormVisible.value = true;
}

async function handleSubmit() {
    try {
        if (isEditing.value) {
            await apiClient.put(`/api/admin/rss-feeds/${form.value.id}`, form.value);
            uiStore.addNotification('Feed updated.', 'success');
        } else {
            await apiClient.post('/api/admin/rss-feeds', form.value);
            uiStore.addNotification('Feed added.', 'success');
        }
        await fetchFeeds();
        isFormVisible.value = false;
    } catch (error) {
        // Handled by interceptor
    }
}

async function handleDelete(feed) {
    const confirmed = await uiStore.showConfirmation({ 
        title: `Delete Feed '${feed.name}'?`, 
        message: 'This will also delete all news articles from this source. This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        await apiClient.delete(`/api/admin/rss-feeds/${feed.id}`);
        await fetchFeeds();
    }
}

async function handleScrape() {
    isScraping.value = true;
    try {
        await adminStore.triggerRssScraping();
    } finally {
        isScraping.value = false;
    }
}

onMounted(fetchFeeds);
</script>

<template>
    <div class="space-y-6">
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-lg p-6">
            <h3 class="text-xl font-semibold mb-4">{{ isEditing ? 'Edit RSS Feed' : 'Add New RSS Feed' }}</h3>
            <form @submit.prevent="handleSubmit" class="space-y-4">
                <div><label class="label">Name</label><input v-model="form.name" type="text" class="input-field" required placeholder="e.g., Tech News"></div>
                <div><label class="label">URL</label><input v-model="form.url" type="url" class="input-field" required placeholder="https://example.com/rss.xml"></div>
                <div class="flex items-center"><input v-model="form.is_active" type="checkbox" id="is_active_checkbox" class="h-4 w-4 rounded"><label for="is_active_checkbox" class="ml-2">Active</label></div>
                <div class="flex justify-end gap-2">
                    <button type="button" @click="isFormVisible = false" class="btn btn-secondary">Cancel</button>
                    <button type="submit" class="btn btn-primary">{{ isEditing ? 'Save Changes' : 'Add Feed' }}</button>
                </div>
            </form>
        </div>

        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-6 border-b dark:border-gray-700 flex justify-between items-center">
                <h3 class="text-xl font-semibold">RSS Feed Sources</h3>
                <div class="flex items-center gap-2">
                    <button @click="handleScrape" class="btn btn-secondary btn-sm" :disabled="isScraping">
                        <IconRefresh class="w-4 h-4 mr-1" :class="{'animate-spin': isScraping}"/>
                        {{ isScraping ? 'Scraping...' : 'Scrape Now' }}
                    </button>
                    <button @click="showAddForm" class="btn btn-primary btn-sm"><IconPlus class="w-4 h-4 mr-1"/>Add Feed</button>
                </div>
            </div>
            <div v-if="isLoading" class="p-6 text-center text-gray-500">Loading feeds...</div>
            <div v-else-if="feeds.length === 0" class="p-6 text-center text-gray-500">No RSS feeds configured. Add one to get started.</div>
            <ul v-else class="divide-y dark:divide-gray-700">
                <li v-for="feed in feeds" :key="feed.id" class="p-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <div>
                        <p class="font-semibold">{{ feed.name }} <span class="text-xs px-2 py-0.5 rounded-full ml-2" :class="feed.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300' : 'bg-gray-200 text-gray-800 dark:bg-gray-600 dark:text-gray-300'">{{ feed.is_active ? 'Active' : 'Inactive' }}</span></p>
                        <p class="text-sm text-gray-500 font-mono">{{ feed.url }}</p>
                    </div>
                    <div class="flex gap-2 flex-shrink-0">
                        <button @click="showEditForm(feed)" class="btn-icon" title="Edit"><IconPencil class="w-4 h-4" /></button>
                        <button @click="handleDelete(feed)" class="btn-icon-danger" title="Delete"><IconTrash class="w-4 h-4" /></button>
                    </div>
                </li>
            </ul>
        </div>
    </div>
</template>