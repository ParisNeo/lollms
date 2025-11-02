<script setup>
import { ref, onMounted } from 'vue';
import apiClient from '../services/api';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import IconFileText from '../assets/icons/IconFileText.vue';
import MessageContentRenderer from '../components/ui/MessageContentRenderer/MessageContentRenderer.vue';

const articles = ref([]);
const isLoading = ref(true);

async function fetchNews() {
    isLoading.value = true;
    try {
        const response = await apiClient.get('/api/news');
        articles.value = response.data;
    } finally {
        isLoading.value = false;
    }
}

onMounted(fetchNews);
</script>

<template>
    <PageViewLayout title="News" :title-icon="IconFileText">
        <template #main>
            <div class="p-4 sm:p-6 space-y-6 max-w-4xl mx-auto">
                <div v-if="isLoading" class="text-center py-10">
                    <p class="text-gray-500">Loading news...</p>
                </div>
                <div v-else-if="articles.length === 0" class="text-center py-10">
                    <h3 class="text-lg font-semibold">No News Available</h3>
                    <p class="text-gray-500 mt-2">The news feed is empty. An administrator may need to add RSS feed sources.</p>
                </div>
                <div v-else class="space-y-8">
                    <div v-for="article in articles" :key="article.id" class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
                        <h2 class="text-2xl font-bold mb-2">{{ article.title }}</h2>
                        <p v-if="article.publication_date" class="text-xs text-gray-500 dark:text-gray-400 mb-4">
                            Published: {{ new Date(article.publication_date).toLocaleString() }}
                        </p>
                        <MessageContentRenderer :content="article.content" class="text-base"/>
                        <a :href="article.url" target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-blue-400 text-sm mt-4 inline-block hover:underline">
                            Read Original Article &rarr;
                        </a>
                    </div>
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>