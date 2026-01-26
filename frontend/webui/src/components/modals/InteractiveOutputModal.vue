<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('interactiveOutput'));

const title = computed(() => props.value?.title || 'Execution Results');
const results = computed(() => {
    const rawResults = props.value?.results;
    if (rawResults && Object.keys(rawResults).length > 0) return rawResults;
    
    // Fallback for direct content display (e.g. from ChatInput feature info)
    if (props.value?.content) {
        return { "Info": { "content": props.value.content } };
    }

    // Fallback for direct HTML content (e.g. from CodeBlock)
    if (props.value?.htmlContent) {
        return { "Preview": { "html_output": props.value.htmlContent } };
    }
    return {};
});

/**
 * Determines if a value should be rendered as a rich image.
 */
function isImage(key, value) {
    if (typeof value !== 'string') return false;
    return key.toLowerCase().includes('image') || key.toLowerCase().includes('_b64') || value.startsWith('data:image/');
}

/**
 * Determines if a value should be rendered as interactive HTML.
 */
function isHtml(key, value) {
    if (typeof value !== 'string') return false;
    const k = key.toLowerCase();
    if (k.includes('html') || k.includes('visualization') || k.includes('interactive') || k.includes('animation') || k.includes('plot')) return true;
    const trimmed = value.trim();
    return /^\s*<!doctype html>|^\s*<html/i.test(trimmed);
}

/**
 * Determines if a value should be rendered as Markdown.
 */
function isMarkdown(key, value) {
    if (typeof value !== 'string') return false;
    return key.toLowerCase().includes('text') || key.toLowerCase().includes('content') || key.toLowerCase().includes('summary') || key.toLowerCase().includes('markdown');
}

/**
 * Formats base64 data for <img> src if header is missing.
 */
function formatImageSrc(value) {
    if (value.startsWith('data:image/')) return value;
    // Assume PNG as default for raw base64 from nodes
    return `data:image/png;base64,${value}`;
}

function openHtmlFullscreen(content) {
    const blob = new Blob([content], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    // Clean up
    setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function downloadImage(b64, name) {
    const link = document.createElement('a');
    link.href = formatImageSrc(b64);
    link.download = `${name || 'generated_image'}.png`;
    link.click();
}

function openFullscreen(src) {
    uiStore.openImageViewer({ imageList: [{ src }], startIndex: 0 });
}

function copyToClipboard(text) {
    uiStore.copyToClipboard(text, 'Result copied to clipboard!');
}

function handleClose() {
    uiStore.closeModal('interactiveOutput');
}
</script>

<template>
    <GenericModal modalName="interactiveOutput" :title="title" maxWidthClass="max-w-6xl">
        <template #body>
            <div class="p-6 space-y-8 bg-gray-50 dark:bg-gray-900/50 min-h-[400px]">
                
                <div v-if="Object.keys(results).length === 0" class="flex flex-col items-center justify-center py-20 text-gray-400">
                    <IconInfo class="w-12 h-12 mb-4 opacity-20" />
                    <p class="text-lg font-medium">No results generated yet.</p>
                </div>

                <div v-else class="space-y-6">
                    <div v-for="(nodeResult, nodeId) in results" :key="nodeId" class="result-panel">
                        <!-- Node Header -->
                        <div class="px-4 py-3 bg-white dark:bg-gray-800 border-b dark:border-gray-700 flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <IconCheckCircle class="w-5 h-5 text-green-500" />
                                <span class="font-bold text-sm text-gray-700 dark:text-gray-200 uppercase tracking-wider">{{ nodeId }}</span>
                            </div>
                            <span class="text-[10px] font-mono text-gray-400">Node ID: {{ nodeId }}</span>
                        </div>

                        <!-- Result Content -->
                        <div class="p-4 space-y-4">
                            <div v-for="(value, key) in nodeResult" :key="key" class="space-y-2">
                                <div class="flex items-center gap-2">
                                    <span class="text-[10px] font-black uppercase text-blue-500 tracking-widest">{{ key }}</span>
                                    <div class="h-px flex-grow bg-gray-100 dark:bg-gray-700"></div>
                                </div>

                                <!-- IMAGE RENDERING -->
                                <div v-if="isImage(key, value)" class="image-result-container group">
                                    <div class="relative rounded-lg overflow-hidden border dark:border-gray-700 bg-gray-200 dark:bg-black">
                                        <img :src="formatImageSrc(value)" class="max-w-full h-auto mx-auto shadow-2xl" />
                                        
                                        <!-- Actions Overlay -->
                                        <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                                            <button @click="openFullscreen(formatImageSrc(value))" class="btn-img-action" title="Full Screen">
                                                <IconMaximize class="w-5 h-5" />
                                            </button>
                                            <button @click="downloadImage(value, key)" class="btn-img-action" title="Download">
                                                <IconArrowDownTray class="w-5 h-5" />
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <!-- HTML / INTERACTIVE RENDERING -->
                                <div v-else-if="isHtml(key, value)" class="html-result-container w-full h-[600px] border dark:border-gray-700 rounded-lg overflow-hidden bg-white shadow-sm relative">
                                    <iframe :srcdoc="value" class="w-full h-full" sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-modals" referrerpolicy="no-referrer"></iframe>
                                    <!-- Actions Overlay -->
                                    <div class="absolute top-2 right-2 flex gap-2 z-10">
                                        <button @click="openHtmlFullscreen(value)" class="p-2 bg-white/80 dark:bg-black/50 hover:bg-white dark:hover:bg-black text-gray-700 dark:text-gray-200 rounded-full shadow-sm backdrop-blur-sm transition-all border dark:border-gray-600" title="Open in New Tab">
                                            <IconMaximize class="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>

                                <!-- MARKDOWN / TEXT RENDERING -->
                                <div v-else-if="isMarkdown(key, value)" class="text-result-container prose dark:prose-invert max-w-none bg-white dark:bg-gray-800 p-6 rounded-xl shadow-inner border dark:border-gray-700">
                                    <MessageContentRenderer :content="value" />
                                    <div class="mt-4 flex justify-end">
                                        <button @click="copyToClipboard(value)" class="text-[10px] font-bold text-gray-400 hover:text-blue-500 uppercase tracking-widest transition-colors">Copy Raw Text</button>
                                    </div>
                                </div>

                                <!-- GENERIC / JSON FALLBACK -->
                                <div v-else class="p-3 bg-gray-100 dark:bg-gray-950 rounded font-mono text-xs overflow-x-auto border dark:border-gray-800">
                                    <pre class="text-gray-600 dark:text-gray-400">{{ JSON.stringify(value, null, 2) }}</pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex justify-between w-full px-4">
                <p class="text-xs text-gray-500 self-center">Results are updated in real-time during flow execution.</p>
                <button @click="handleClose" class="btn btn-primary px-8">Done</button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
.result-panel {
    @apply bg-white dark:bg-gray-800/50 rounded-2xl shadow-lg border dark:border-gray-700 overflow-hidden;
}

.btn-img-action {
    @apply p-3 bg-white dark:bg-gray-800 rounded-full shadow-xl hover:scale-110 transition-transform text-gray-700 dark:text-gray-200;
}

.text-result-container :deep(.think-block) {
    @apply my-2 border-l-4 border-blue-500/30 bg-blue-50/50 dark:bg-blue-900/10 rounded-r-lg;
}

.animate-fade-in-up {
    animation: fadeInUp 0.3s ease-out;
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
