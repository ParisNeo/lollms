<!-- frontend/webui/src/views/HelpView.vue -->
<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import IconBookOpen from '../assets/icons/IconBookOpen.vue';
import IconMagnifyingGlass from '../assets/icons/IconMagnifyingGlass.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconChevronRight from '../assets/icons/IconChevronRight.vue';
import IconInfo from '../assets/icons/IconInfo.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import apiClient from '../services/api';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const userUiLevel = computed(() => authStore.user?.user_ui_level || 0);

const helpIndex = ref([]);
const helpContentHtml = ref('');
const isLoadingContent = ref(true);
const isLoadingIndex = ref(true);
const searchQuery = ref('');
const currentTopic = ref(null);
const mainContentAreaRef = ref(null);

// --- Robust Marked Configuration ---
// Signature handles both v13 token objects and standard positional arguments
marked.use({
    renderer: {
        heading(arg1, arg2, arg3) {
            let text = "";
            let depth = 1;

            if (arg1 && typeof arg1 === 'object') {
                // Version 13+ Token Object path
                text = arg1.text || "";
                depth = arg1.depth || 1;
            } else {
                // Positional arguments path
                text = arg1 || "";
                depth = arg2 || 1;
            }

            const id = text.toLowerCase().replace(/[^\w]+/g, '-');
            return `
                <h${depth} id="${id}" class="scroll-mt-24 group flex items-center mb-6 mt-12 font-black tracking-tight text-gray-900 dark:text-white">
                    ${text}
                    <a href="#${id}" class="ml-3 opacity-0 group-hover:opacity-100 text-blue-500 transition-opacity text-base font-normal no-underline">#</a>
                </h${depth}>`;
        },
        code(arg1, arg2) {
            let code = "";
            let language = "plaintext";

            if (arg1 && typeof arg1 === 'object') {
                code = arg1.text || "";
                language = arg1.lang || "plaintext";
            } else {
                code = arg1 || "";
                language = arg2 || "plaintext";
            }

            const validLanguage = hljs.getLanguage(language) ? language : 'plaintext';
            const highlighted = hljs.highlight(code, { language: validLanguage }).value;
            return `<pre class="hljs language-${validLanguage} rounded-2xl p-6 my-6 border border-gray-200 dark:border-gray-800 shadow-xl overflow-x-auto"><code>${highlighted}</code></pre>`;
        }
    },
    gfm: true,
    breaks: true
});

// --- Helpers ---

function getDefaultFilename(level) {
    if (level >= 4) return 'level_4_expert.md';
    if (level >= 2) return 'level_2_intermediate.md';
    return 'level_0_beginner.md';
}

function parseIndex(markdown) {
    const sections = [];
    let currentSection = null;
    const lines = markdown.split('\n');

    lines.forEach(line => {
        if (line.startsWith('### ')) {
            currentSection = { title: line.replace('### ', '').trim(), items: [] };
            sections.push(currentSection);
        } else if (line.trim().startsWith('*')) {
            const match = line.match(/\[\*\*(.*?)\*\*\]\s*\((.*?\.md)(?:#(.*))?\)\s*-\s*(.*)/);
            if (match && currentSection) {
                currentSection.items.push({
                    title: match[1],
                    filename: match[2],
                    sectionId: match[3] || null,
                    description: match[4]
                });
            }
        }
    });
    return sections;
}

const filteredIndex = computed(() => {
    if (!searchQuery.value) return helpIndex.value;
    const q = searchQuery.value.toLowerCase();
    return helpIndex.value.map(section => ({
        ...section,
        items: section.items.filter(i => 
            i.title.toLowerCase().includes(q) || 
            (i.description && i.description.toLowerCase().includes(q))
        )
    })).filter(s => s.items.length > 0);
});

// --- Actions ---

async function fetchTopic(filename, sectionId = null) {
    if (!filename) return;
    isLoadingContent.value = true;
    try {
        const res = await apiClient.get('/api/help/topic', { 
            params: { topic_filename: filename } 
        });
        
        helpContentHtml.value = await marked.parse(res.data);
        currentTopic.value = filename;
        
        await nextTick();
        if (sectionId) {
            const el = document.getElementById(sectionId.toLowerCase().replace(/[^\w]+/g, '-'));
            if (el) el.scrollIntoView({ behavior: 'smooth' });
        } else {
            mainContentAreaRef.value?.scrollTo({ top: 0 });
        }
    } catch (e) {
        console.error("Documentation fetch error:", e);
        const detail = e.response?.data?.detail || e.message;
        helpContentHtml.value = `
            <div class="p-8 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-2xl border border-red-100 dark:border-red-800 flex flex-col items-center text-center">
                <h3 class="text-xl font-black mb-2">Failed to load content</h3>
                <p class="max-w-md text-sm opacity-80 mb-4 font-mono">${filename}</p>
                <div class="bg-white/50 dark:bg-black/20 p-4 rounded-xl font-mono text-xs mb-6 w-full max-w-sm text-left border dark:border-gray-700">
                    ${detail}
                </div>
                <button onclick="location.reload()" class="btn btn-primary px-6 py-2 rounded-xl shadow-lg">Retry Connection</button>
            </div>`;
    } finally {
        isLoadingContent.value = false;
    }
}

async function handleSearch() {
    if (!searchQuery.value.trim()) return;
    isLoadingContent.value = true;
    try {
        const res = await apiClient.get('/api/help/search', { params: { query: searchQuery.value } });
        helpContentHtml.value = await marked.parse(res.data);
        currentTopic.value = 'search';
    } finally {
        isLoadingContent.value = false;
    }
}

function selectTopic(item) {
    searchQuery.value = '';
    router.push({ query: { topic: item.filename, section: item.sectionId } });
}

// --- Lifecycle ---

onMounted(async () => {
    isLoadingIndex.value = true;
    try {
        const res = await apiClient.get('/api/help/index');
        helpIndex.value = parseIndex(res.data);
    } catch (e) {
        console.error("Index load failed:", e);
    } finally {
        isLoadingIndex.value = false;
    }

    const topic = route.query.topic || getDefaultFilename(userUiLevel.value);
    fetchTopic(topic, route.query.section);
});

watch(() => route.query.topic, (newTopic) => {
    if (newTopic && newTopic !== currentTopic.value) {
        fetchTopic(newTopic, route.query.section);
    }
});

watch(searchQuery, (newVal) => {
    if (!newVal && currentTopic.value === 'search') {
        fetchTopic(getDefaultFilename(userUiLevel.value));
    }
});
</script>

<template>
  <PageViewLayout title="Documentation & Help" :title-icon="IconBookOpen">
    <template #sidebar>
        <!-- User Context Info -->
        <div class="px-3 mb-6">
            <div class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-2xl border border-blue-100 dark:border-blue-800 shadow-sm transition-all hover:shadow-md">
                <div class="flex items-center gap-2 mb-2">
                    <IconInfo class="w-3.5 h-3.5 text-blue-500" />
                    <p class="text-[10px] font-black uppercase tracking-widest text-blue-600 dark:text-blue-400">Your Perspective</p>
                </div>
                <div class="flex items-center justify-between gap-2">
                    <p class="text-sm font-bold text-gray-800 dark:text-gray-100">
                        Level {{ userUiLevel }} Access
                    </p>
                    <span v-if="authStore.isAdmin" class="text-[9px] bg-red-500 text-white px-2 py-0.5 rounded-full font-black uppercase tracking-tighter shadow-sm">Admin</span>
                </div>
            </div>
        </div>

        <!-- Search Bar -->
        <div class="px-3 mb-6">
            <div class="relative group">
                <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                    <IconMagnifyingGlass class="h-4 w-4 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                </div>
                <input 
                    type="text" 
                    v-model="searchQuery" 
                    @keyup.enter="handleSearch"
                    placeholder="Search documentation..."
                    class="w-full bg-gray-100 dark:bg-gray-800 border-none rounded-2xl py-2.5 pl-10 pr-10 text-sm focus:ring-2 focus:ring-blue-500 transition-all shadow-inner"
                />
                <button v-if="searchQuery" @click="searchQuery = ''" class="absolute inset-y-0 right-0 pr-3.5 flex items-center group/btn">
                    <IconXMark class="h-4 w-4 text-gray-400 group-hover/btn:text-red-500 transition-colors" />
                </button>
            </div>
        </div>

        <!-- Topic List -->
        <div class="flex-grow overflow-y-auto px-1 custom-scrollbar">
            <div v-if="isLoadingIndex" class="space-y-4 p-4 animate-pulse">
                <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                <div class="h-12 bg-gray-100 dark:bg-gray-800 rounded-xl"></div>
                <div class="h-12 bg-gray-100 dark:bg-gray-800 rounded-xl"></div>
            </div>
            
            <div v-else class="space-y-6 pb-10">
                <div v-for="section in filteredIndex" :key="section.title">
                    <h4 class="px-4 text-[10px] font-black uppercase tracking-[0.25em] text-gray-400 dark:text-gray-500 mb-3">{{ section.title }}</h4>
                    <div class="space-y-1.5 px-1">
                        <button 
                            v-for="item in section.items" 
                            :key="item.title"
                            @click="selectTopic(item)"
                            class="w-full text-left px-3.5 py-3 rounded-xl transition-all group relative overflow-hidden flex flex-col gap-0.5 border border-transparent"
                            :class="currentTopic === item.filename ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20 border-blue-500' : 'text-gray-600 dark:text-gray-400 hover:bg-white dark:hover:bg-gray-800 hover:border-gray-200 dark:hover:border-gray-700 hover:shadow-sm'"
                        >
                            <div class="flex items-center justify-between">
                                <span class="font-bold text-sm truncate">{{ item.title }}</span>
                                <IconChevronRight class="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-all transform group-hover:translate-x-0.5" />
                            </div>
                            <p v-if="item.description" class="text-[10px] line-clamp-1 opacity-70 group-hover:opacity-100">{{ item.description }}</p>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </template>

    <template #main>
        <div ref="mainContentAreaRef" class="h-full overflow-y-auto custom-scrollbar bg-white dark:bg-gray-900 selection:bg-blue-100 dark:selection:bg-blue-900">
            <div class="max-w-4xl mx-auto px-6 py-12 md:px-12 lg:py-16">
                <div v-if="isLoadingContent" class="flex flex-col items-center justify-center py-24">
                    <IconAnimateSpin class="w-12 h-12 text-blue-500 animate-spin mb-4" />
                    <p class="text-gray-500 font-medium tracking-widest uppercase text-xs">Retrieving Documentation</p>
                </div>
                <article v-else class="prose prose-blue dark:prose-invert max-w-none 
                    prose-headings:font-black prose-headings:tracking-tight
                    prose-h1:text-5xl prose-h1:mb-10 prose-h1:pb-8 prose-h1:border-b-2 dark:prose-h1:border-gray-800
                    prose-h2:text-2xl prose-h2:mt-16 prose-h2:mb-8 prose-h2:pb-2 prose-h2:border-b dark:prose-h2:border-gray-800
                    prose-h3:text-xl prose-h3:mt-10 prose-h3:mb-6
                    prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
                    prose-pre:bg-gray-950 prose-pre:border prose-pre:border-gray-800 prose-pre:rounded-2xl prose-pre:shadow-2xl prose-pre:p-6
                    prose-img:rounded-3xl prose-img:shadow-2xl prose-img:border dark:prose-img:border-gray-800
                    prose-code:text-blue-600 dark:prose-code:text-blue-400 prose-code:bg-blue-50 dark:prose-code:bg-blue-900/30 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:font-mono prose-code:before:content-[''] prose-code:after:content-['']
                    animate-fade-in">
                    <div v-html="helpContentHtml"></div>
                </article>

                <!-- Footer -->
                <div class="mt-24 pt-10 border-t dark:border-gray-800 flex flex-col sm:flex-row justify-between items-center gap-6 text-[10px] font-black uppercase tracking-[0.25em] text-gray-400">
                    <p>© ParisNeo 2025 · Core System Docs</p>
                    <div class="flex gap-8">
                        <a href="https://github.com/ParisNeo/lollms" target="_blank" class="hover:text-blue-500 transition-all flex items-center gap-2 group">GitHub</a>
                        <a href="https://discord.gg/Mub9p6XF" target="_blank" class="hover:text-blue-500 transition-all flex items-center gap-2 group">Discord</a>
                    </div>
                </div>
            </div>
        </div>
    </template>
  </PageViewLayout>
</template>

<style scoped>
.animate-fade-in {
    animation: fadeIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(15px); }
    to { opacity: 1; transform: translateY(0); }
}
.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-200 dark:bg-gray-700 rounded-full; }
</style>
