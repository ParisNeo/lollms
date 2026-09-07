<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useDiscussionsStore } from '../stores/discussions';
import { useUiStore } from '../stores/ui';
import apiClient from '../services/api';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import MessageContentRenderer from '../components/ui/MessageContentRenderer/MessageContentRenderer.vue';
import CodeMirrorComponent from '../components/ui/CodeMirrorComponent/index.vue';

// Icons
import IconFileText from '../assets/icons/IconFileText.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconCopy from '../assets/icons/IconCopy.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconEye from '../assets/icons/IconEye.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconPlayCircle from '../assets/icons/IconPlayCircle.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';

const route = useRoute();
const router = useRouter();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const { activeDiscussionArtefacts } = storeToRefs(discussionsStore);

const artefacts = ref([]);
const isLoading = ref(false);
const isSaving = ref(false);
const selectedArtefact = ref(null);
const activeViewMode = ref('editor'); // 'editor', 'preview'

const form = ref({
    title: '',
    type: 'document',
    content: ''
});

const isExecutableType = computed(() => {
    const t = (form.value.type || '').toLowerCase();
    const title = (form.value.title || '').toLowerCase();
    return t === 'html' || t === 'svg' || t === 'mermaid' || title.endsWith('.html') || title.endsWith('.svg');
});

const editorLanguage = computed(() => {
    const t = (form.value.type || '').toLowerCase();
    const title = (form.value.title || '').toLowerCase();
    if (t === 'html' || title.endsWith('.html')) return 'html';
    if (t === 'javascript' || t === 'js' || title.endsWith('.js')) return 'javascript';
    if (t === 'python' || t === 'py' || title.endsWith('.py')) return 'python';
    if (t === 'svg' || title.endsWith('.svg')) return 'xml';
    if (t === 'markdown' || title.endsWith('.md')) return 'markdown';
    if (t === 'json' || title.endsWith('.json')) return 'json';
    return 'markdown';
});

async function fetchAllGlobalArtefacts() {
    isLoading.value = true;
    try {
        const res = await apiClient.get('/api/artefacts/global');
        artefacts.value = Array.isArray(res.data) ? res.data : [];
        syncSelectionFromRoute();
    } catch (e) {
        if (discussionsStore.currentDiscussionId) {
            await discussionsStore.fetchArtefacts(discussionsStore.currentDiscussionId);
            artefacts.value = activeDiscussionArtefacts.value || [];
        }
    } finally {
        isLoading.value = false;
    }
}

function syncSelectionFromRoute() {
    const qId = route.query.artefactId;
    if (qId) {
        const found = artefacts.value.find(a => String(a.id || a.title) === String(qId));
        if (found) selectArtefact(found);
    } else if (artefacts.value.length > 0 && !selectedArtefact.value) {
        selectArtefact(artefacts.value[0]);
    }
}

function selectArtefact(item) {
    if (!item) return;
    selectedArtefact.value = item;
    form.value = {
        title: item.title || '',
        type: item.type || 'document',
        content: item.content || ''
    };
    router.replace({ query: { ...route.query, artefactId: item.id || item.title } });
}

function createNewArtefact() {
    selectedArtefact.value = null;
    form.value = {
        title: 'index.html',
        type: 'html',
        content: `<!DOCTYPE html>\n<html>\n<head>\n  <title>LoLLMs Interactive Canvas</title>\n  <style>\n    body { font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0f172a; color: #f8fafc; }\n    .card { padding: 2rem; border-radius: 1rem; background: #1e293b; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }\n    button { background: #3b82f6; color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 0.5rem; font-weight: bold; cursor: pointer; }\n  </style>\n</head>\n<body>\n  <div class="card">\n    <h2>LoLLMs Live Executable Artefact</h2>\n    <p>Edit HTML, CSS, JavaScript, SVG, or Mermaid with real-time runtime execution.</p>\n    <button onclick="alert('Hello from LoLLMs Artefact Runtime!')">Click Me</button>\n  </div>\n</body>\n</html>`
    };
    activeViewMode.value = 'editor';
}

async function saveArtefact() {
    if (!form.value.title.trim()) {
        uiStore.addNotification('Artefact title is required.', 'warning');
        return;
    }

    isSaving.value = true;
    try {
        if (selectedArtefact.value && selectedArtefact.value.id) {
            await apiClient.put(`/api/artefacts/${selectedArtefact.value.id}`, form.value);
            uiStore.addNotification('Artefact saved.', 'success');
        } else if (discussionsStore.currentDiscussionId) {
            await discussionsStore.createArtefactManual({
                discussionId: discussionsStore.currentDiscussionId,
                title: form.value.title,
                content: form.value.content,
                type: form.value.type
            });
            uiStore.addNotification('Artefact saved to active discussion.', 'success');
        } else {
            await apiClient.post('/api/artefacts/global', form.value);
            uiStore.addNotification('Artefact saved to global library.', 'success');
        }
        await fetchAllGlobalArtefacts();
    } catch (e) {
        uiStore.addNotification('Failed to save artefact.', 'error');
    } finally {
        isSaving.value = false;
    }
}

async function deleteCurrentArtefact() {
    if (!selectedArtefact.value) return;
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Artefact "${form.value.title}"?`,
        message: 'This document will be permanently deleted.',
        confirmText: 'Delete'
    });
    if (confirmed?.confirmed || confirmed === true) {
        if (selectedArtefact.value.id) {
            await apiClient.delete(`/api/artefacts/${selectedArtefact.value.id}`);
        } else if (discussionsStore.currentDiscussionId) {
            await discussionsStore.deleteArtefact(discussionsStore.currentDiscussionId, selectedArtefact.value.title);
        }
        await fetchAllGlobalArtefacts();
        if (artefacts.value.length > 0) selectArtefact(artefacts.value[0]);
        else createNewArtefact();
    }
}

async function copyContent() {
    if (!form.value.content) return;
    try {
        await navigator.clipboard.writeText(form.value.content);
        uiStore.addNotification('Copied to clipboard.', 'success');
    } catch (e) {
        uiStore.addNotification('Failed to copy.', 'error');
    }
}

function downloadArtefact() {
    if (!form.value.content) return;
    const blob = new Blob([form.value.content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = form.value.title || 'artefact.txt';
    link.click();
    URL.revokeObjectURL(url);
}

function handleExternalSelectEvent(event) {
    if (event.detail && event.detail.id) {
        const found = artefacts.value.find(a => String(a.id || a.title) === String(event.detail.id));
        if (found) selectArtefact(found);
    }
}

onMounted(() => {
    window.addEventListener('lollms:select-artefact', handleExternalSelectEvent);
    fetchAllGlobalArtefacts();
});

onUnmounted(() => {
    window.removeEventListener('lollms:select-artefact', handleExternalSelectEvent);
});

watch(() => route.query.artefactId, (newId) => {
    if (newId && String(newId) !== String(selectedArtefact.value?.id || selectedArtefact.value?.title)) {
        const found = artefacts.value.find(a => String(a.id || a.title) === String(newId));
        if (found) selectArtefact(found);
    }
});
</script>

<template>
    <PageViewLayout title="Artefacts Studio" :title-icon="IconFileText" :show-sidebar="false">
        <template #main>
            <div class="h-full flex flex-col overflow-hidden bg-bg-app">
                <!-- Master Top Toolbar -->
                <div class="shrink-0 px-6 py-3.5 border-b border-border-main bg-bg-card/70 backdrop-blur-sm flex items-center justify-between gap-4 flex-wrap">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-900/30 text-blue-600 flex items-center justify-center shrink-0 border border-blue-200 dark:border-blue-800">
                            <IconFileText class="w-4 h-4" />
                        </div>
                        <div class="flex items-center gap-3 min-w-0">
                            <input 
                                v-model="form.title" 
                                type="text" 
                                placeholder="Artefact Title..." 
                                class="input-field text-sm font-bold w-60 sm:w-80"
                            />
                            <select v-model="form.type" class="input-field text-xs w-36 hidden sm:block">
                                <option value="html">🌐 HTML Web App</option>
                                <option value="svg">🎨 SVG Graphic</option>
                                <option value="mermaid">📊 Mermaid Diagram</option>
                                <option value="markdown">📝 Markdown</option>
                                <option value="code">💻 Source Code</option>
                            </select>
                        </div>
                    </div>

                    <!-- Modes & Actions -->
                    <div class="flex items-center gap-2 shrink-0">
                        <div class="flex items-center p-1 bg-gray-100 dark:bg-gray-800 rounded-xl text-xs font-bold mr-2">
                            <button 
                                @click="activeViewMode = 'editor'" 
                                class="px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5"
                                :class="activeViewMode === 'editor' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-text-dim'"
                            >
                                <IconPencil class="w-3.5 h-3.5" />
                                <span>Code Editor</span>
                            </button>
                            <button 
                                @click="activeViewMode = 'preview'" 
                                class="px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5"
                                :class="activeViewMode === 'preview' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-text-dim'"
                            >
                                <component :is="isExecutableType ? IconPlayCircle : IconEye" class="w-3.5 h-3.5 text-emerald-500" />
                                <span>{{ isExecutableType ? 'Live Execution' : 'Render Preview' }}</span>
                            </button>
                        </div>

                        <button @click="createNewArtefact" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="New Artefact">
                            <IconPlus class="w-3.5 h-3.5" />
                            <span class="hidden md:inline">New</span>
                        </button>
                        <button @click="downloadArtefact" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Download file">
                            <IconArrowDownTray class="w-3.5 h-3.5" />
                            <span class="hidden md:inline">Download</span>
                        </button>
                        <button @click="copyContent" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Copy code">
                            <IconCopy class="w-3.5 h-3.5" />
                            <span class="hidden md:inline">Copy</span>
                        </button>
                        <button v-if="selectedArtefact" @click="deleteCurrentArtefact" class="btn btn-secondary btn-sm text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30" title="Delete Artefact">
                            <IconTrash class="w-3.5 h-3.5" />
                        </button>
                        <button @click="saveArtefact" class="btn btn-primary btn-sm flex items-center gap-1.5 shadow-sm" :disabled="isSaving">
                            <IconAnimateSpin v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                            <IconCheckCircle v-else class="w-3.5 h-3.5" />
                            <span>{{ isSaving ? 'Saving...' : 'Save' }}</span>
                        </button>
                    </div>
                </div>

                <!-- Full Width Studio Workspace (No duplicate middle list) -->
                <div class="grow flex flex-col overflow-hidden bg-bg-app p-4 sm:p-6">
                    <!-- Mode: CodeMirror Editor -->
                    <div v-if="activeViewMode === 'editor'" class="grow overflow-hidden flex flex-col">
                        <CodeMirrorComponent 
                            v-model="form.content" 
                            :language="editorLanguage"
                            class="h-full w-full rounded-2xl border border-border-main overflow-hidden shadow-xs"
                        />
                    </div>

                    <!-- Mode: Live Execution & Interactive Runner -->
                    <div v-else class="grow overflow-hidden rounded-2xl border border-border-main bg-bg-card shadow-sm flex flex-col">
                        <!-- HTML Sandboxed Live Runtime -->
                        <iframe 
                            v-if="form.type === 'html' || form.title.toLowerCase().endsWith('.html')" 
                            :srcdoc="form.content" 
                            sandbox="allow-scripts allow-forms allow-modals"
                            class="w-full h-full border-0 bg-white"
                        ></iframe>

                        <!-- SVG Vector Rendering -->
                        <div 
                            v-else-if="form.type === 'svg' || form.title.toLowerCase().endsWith('.svg')" 
                            v-html="form.content" 
                            class="w-full h-full flex items-center justify-center p-8 bg-white overflow-auto"
                        ></div>

                        <!-- Markdown / Code / Mermaid Formatted Viewer -->
                        <div v-else class="w-full h-full p-8 overflow-y-auto custom-scrollbar prose dark:prose-invert max-w-4xl mx-auto">
                            <MessageContentRenderer :content="form.content || '*Artefact is empty.*'" />
                        </div>
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