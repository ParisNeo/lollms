
<script setup>
import { ref, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { newsArticles, isLoadingNewsArticles } = storeToRefs(adminStore);
const selectedArticleIds = ref([]);

const sortedArticles = computed(() => {
    return [...newsArticles.value].sort((a, b) => new Date(b.publication_date) - new Date(a.publication_date));
});

onMounted(() => {
    adminStore.fetchNewsArticles();
});

const areAllSelected = computed({
    get: () => sortedArticles.value.length > 0 && selectedArticleIds.value.length === sortedArticles.value.length,
    set: (value) => {
        selectedArticleIds.value = value ? sortedArticles.value.map(a => a.id) : [];
    }
});

function openEditModal(article) {
    uiStore.openModal('newsArticleEditor', { article });
}

async function handleDeleteSelected() {
    if (selectedArticleIds.value.length === 0) return;
    const confirmed = await uiStore.showConfirmation({
        title: `Delete ${selectedArticleIds.value.length} Article(s)?`,
        message: 'This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        await adminStore.deleteBatchNewsArticles(selectedArticleIds.value);
        selectedArticleIds.value = [];
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b dark:border-gray-700 flex justify-between items-center">
            <h3 class="text-xl font-semibold">News Article Management</h3>
            <button v-if="selectedArticleIds.length > 0" @click="handleDeleteSelected" class="btn btn-danger btn-sm">
                <IconTrash class="w-4 h-4 mr-2" />
                Delete Selected ({{ selectedArticleIds.length }})
            </button>
        </div>
        <div v-if="isLoadingNewsArticles" class="p-6 text-center">Loading articles...</div>
        <div v-else-if="newsArticles.length === 0" class="p-6 text-center text-gray-500">No news articles found in the database.</div>
        <div v-else class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead class="bg-gray-50 dark:bg-gray-700/50">
                    <tr>
                        <th scope="col" class="px-6 py-3"><input type="checkbox" v-model="areAllSelected" class="h-4 w-4 rounded" /></th>
                        <th scope="col" class="table-header">Title</th>
                        <th scope="col" class="table-header">Source</th>
                        <th scope="col" class="table-header">Published</th>
                        <th scope="col" class="relative py-3.5 px-4"><span class="sr-only">Actions</span></th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
                    <tr v-for="article in sortedArticles" :key="article.id" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <td class="px-6 py-4"><input type="checkbox" :value="article.id" v-model="selectedArticleIds" class="h-4 w-4 rounded" /></td>
                        <td class="table-cell font-medium max-w-sm truncate" :title="article.title">{{ article.title }}</td>
                        <td class="table-cell text-sm">{{ article.source_name }}</td>
                        <td class="table-cell text-sm">{{ new Date(article.publication_date).toLocaleString() }}</td>
                        <td class="table-cell text-right space-x-2">
                            <button @click="openEditModal(article)" class="btn-icon" title="Edit Article"><IconPencil class="w-4 h-4" /></button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>