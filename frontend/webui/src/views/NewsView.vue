<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import apiClient from '../services/api';
import { useUiStore } from '../stores/ui';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import IconFileText from '../assets/icons/IconFileText.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconShare from '../assets/icons/IconShare.vue';
import IconCopy from '../assets/icons/IconCopy.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import MessageContentRenderer from '../components/ui/MessageContentRenderer/MessageContentRenderer.vue';

const route = useRoute();
const router = useRouter();
const uiStore = useUiStore();

const articles = ref([]);
const isLoading = ref(true);
const selectedArticleId = ref(null);

const selectedArticle = computed(() => {
    if (!selectedArticleId.value) return null;
    return articles.value.find(a => String(a.id) === String(selectedArticleId.value)) || null;
});

async function fetchNews() {
    isLoading.value = true;
    try {
        const response = await apiClient.get('/api/news');
        articles.value = Array.isArray(response.data) ? response.data : [];
        syncSelectionFromRoute();
    } catch (e) {
        console.error("Failed to load news articles:", e);
        articles.value = [];
    } finally {
        isLoading.value = false;
    }
}

function syncSelectionFromRoute() {
    const qId = route.query.articleId;
    if (qId) {
        selectedArticleId.value = String(qId);
    } else if (articles.value.length > 0 && !selectedArticleId.value) {
        selectedArticleId.value = String(articles.value[0].id);
    }
}

async function copyArticleContent(article) {
    if (!article) return;
    try {
        const text = `# ${article.title}\n\n${article.content}\n\nSource: ${article.url || 'N/A'}`;
        await navigator.clipboard.writeText(text);
        uiStore.addNotification('Article content copied to clipboard!', 'success');
    } catch (e) {
        uiStore.addNotification('Failed to copy to clipboard.', 'error');
    }
}

function handleExternalSelectEvent(event) {
    if (event.detail && event.detail.id) {
        selectedArticleId.value = String(event.detail.id);
        const article = articles.value.find(a => String(a.id) === String(event.detail.id));
        if (article) {
            router.replace({ query: { ...route.query, articleId: article.id } });
        }
    }
}

watch(() => route.query.articleId, (newId) => {
    if (newId) selectedArticleId.value = String(newId);
});

onMounted(() => {
    fetchNews();
    window.addEventListener('lollms:select-news-article', handleExternalSelectEvent);
});

onUnmounted(() => {
    window.removeEventListener('lollms:select-news-article', handleExternalSelectEvent);
});
</script>

<template>
    <PageViewLayout title="News" :title-icon="IconFileText" :show-sidebar="false">
        <template #main>
            <div class="h-full flex flex-col overflow-hidden bg-bg-app">
                <!-- Center Reading Header -->
                <div class="shrink-0 px-6 py-4 border-b border-border-main bg-bg-card/70 backdrop-blur-sm flex items-center justify-between gap-4">
                    <div class="min-w-0">
                        <h1 class="text-lg font-black tracking-tight text-text-main truncate">
                            {{ selectedArticle ? selectedArticle.title : 'News Reader' }}
                        </h1>
                        <p class="text-xs text-text-dim truncate">
                            {{ selectedArticle && selectedArticle.publication_date ? `Published: ${new Date(selectedArticle.publication_date).toLocaleString()}` : 'Select an article from the left sidebar to read' }}
                        </p>
                    </div>

                    <div class="flex items-center gap-2 shrink-0">
                        <button v-if="selectedArticle" @click="copyArticleContent(selectedArticle)" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Copy Markdown">
                            <IconCopy class="w-3.5 h-3.5 text-blue-500" />
                            <span>Copy MD</span>
                        </button>
                        <a v-if="selectedArticle && selectedArticle.url" :href="selectedArticle.url" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Open source link">
                            <IconShare class="w-3.5 h-3.5 text-emerald-500" />
                            <span>Source</span>
                        </a>
                        <button @click="fetchNews" class="btn btn-primary btn-sm flex items-center gap-1.5" :disabled="isLoading">
                            <IconRefresh class="w-3.5 h-3.5" :class="{'animate-spin': isLoading}" />
                            <span class="hidden sm:inline">Refresh</span>
                        </button>
                    </div>
                </div>

                <!-- Central Article Reader -->
                <div class="grow overflow-y-auto custom-scrollbar p-6 sm:p-10 lg:p-12">
                    <div v-if="isLoading && articles.length === 0" class="h-full flex flex-col items-center justify-center text-center">
                        <IconAnimateSpin class="w-8 h-8 text-primary animate-spin mb-3" />
                        <span class="text-xs text-text-dim font-bold uppercase tracking-wider">Loading article...</span>
                    </div>

                    <div v-else-if="selectedArticle" class="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300">
                        <!-- Headline & Badges -->
                        <div class="border-b border-border-main pb-6 space-y-3">
                            <div class="flex items-center gap-2.5 flex-wrap">
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                                    {{ selectedArticle.source || 'News Article' }}
                                </span>
                                <span v-if="selectedArticle.publication_date" class="text-xs text-text-dim font-mono">
                                    {{ new Date(selectedArticle.publication_date).toLocaleString() }}
                                </span>
                            </div>
                            <h1 class="text-2xl sm:text-3xl lg:text-4xl font-black text-text-main tracking-tight leading-tight">
                                {{ selectedArticle.title }}
                            </h1>
                        </div>

                        <!-- Rendered Markdown/HTML Body -->
                        <div class="prose dark:prose-invert max-w-none text-base leading-relaxed">
                            <MessageContentRenderer :content="selectedArticle.content" />
                        </div>

                        <!-- Publisher Link Footer -->
                        <div v-if="selectedArticle.url" class="pt-8 border-t border-border-main flex items-center justify-between">
                            <span class="text-xs text-text-dim font-medium">Original Publisher</span>
                            <a :href="selectedArticle.url" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm flex items-center gap-2">
                                <span>Read Original Source</span>
                                <IconShare class="w-3.5 h-3.5" />
                            </a>
                        </div>
                    </div>

                    <div v-else class="h-full flex flex-col items-center justify-center text-center p-8 text-text-dim">
                        <IconFileText class="w-16 h-16 opacity-30 mb-3" />
                        <h3 class="text-base font-bold text-text-main">No Article Selected</h3>
                        <p class="text-xs mt-1 max-w-xs">Select any article from the left sidebar under the NEWS tab to read its full content here.</p>
                    </div>
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>