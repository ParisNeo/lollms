<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import MermaidViewer from './InteractiveMermaid.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';

const uiStore = useUiStore();
const modalProps = computed(() => uiStore.modalData('interactiveOutput'));

const title = computed(() => modalProps.value?.title || 'Execution Results');
const results = computed(() => {
    const rawResults = modalProps.value?.results;
    if (rawResults && Object.keys(rawResults).length > 0) return rawResults;
    
    // Fallback for direct content display (e.g. from ChatInput feature info)
    if (modalProps.value?.content) {
        return { "Info": { "content": modalProps.value.content } };
    }

    // Fallback for direct HTML content (e.g. from CodeBlock)
    if (modalProps.value?.htmlContent) {
        return { "Preview": { "html_output": modalProps.value.htmlContent } };
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
    <GenericModal 
        modalName="interactiveOutput" 
        :title="title" 
        :maxWidthClass="modalProps?.fullScreen ? 'max-w-full h-full !p-0' : 'max-w-6xl'"
    >
        <template #body>
            <div 
                class="space-y-8 bg-gray-50 dark:bg-gray-900/50 min-h-[400px]"
                :class="modalProps?.fullScreen ? 'p-0 h-full flex flex-col' : 'p-6'"
            >
                
                <div v-if="Object.keys(results).length === 0" class="flex flex-col items-center justify-center py-20 text-gray-400">
                    <IconInfo class="w-12 h-12 mb-4 opacity-20" />
                    <p class="text-lg font-medium">No results generated yet.</p>
                </div>

                <div v-else :class="modalProps?.fullScreen ? 'flex-1 flex flex-col' : 'space-y-6'">
                    <div v-for="(nodeResult, nodeId) in results" :key="nodeId" 
                         :class="[
                             'result-panel',
                             modalProps?.fullScreen ? 'flex-1 flex flex-col !rounded-none !shadow-none border-none' : ''
                         ]">
                        <!-- Node Header -->
                        <div v-if="!modalProps?.fullScreen" class="px-4 py-3 bg-white dark:bg-gray-800 border-b dark:border-gray-700 flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <IconCheckCircle class="w-5 h-5 text-green-500" />
                                <span class="font-bold text-sm text-gray-700 dark:text-gray-200 uppercase tracking-wider">{{ nodeId }}</span>
                            </div>
                            <span class="text-[10px] font-mono text-gray-400">Node ID: {{ nodeId }}</span>
                        </div>

                        <!-- Result Content -->
                        <div 
                            class="space-y-4"
                            :class="modalProps?.fullScreen ? 'p-0 flex-1 flex flex-col' : 'p-4'"
                        >
                            <div v-for="(value, key) in nodeResult" :key="key" 
                                 :class="[
                                     'space-y-2',
                                     modalProps?.fullScreen ? 'flex-1 flex flex-col' : ''
                                 ]">
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

                                <!-- MERMAID RENDERING -->
                                <div v-else-if="modalProps?.contentType === 'mermaid' && modalProps?.sourceCode" class="w-full h-[600px] border dark:border-gray-700 rounded-lg overflow-hidden bg-white shadow-sm relative">
                                    <MermaidViewer 
                                        :mermaid-code="modalProps.sourceCode" 
                                        :message-id="modalProps.messageId"
                                    />
                                </div>

                                <!-- HTML / INTERACTIVE RENDERING -->
                                <div v-else-if="isHtml(key, value)" 
                                     :class="[
                                         'html-result-container w-full border dark:border-gray-700 rounded-lg overflow-hidden bg-white shadow-sm relative',
                                         modalProps?.fullScreen ? 'flex-1 !h-full !rounded-none !border-none' : 'h-[600px]'
                                     ]">
                                    <iframe :srcdoc="value" class="w-full h-full" sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-modals" referrerpolicy="no-referrer"></iframe>
                                    <!-- Actions Overlay -->
                                    <div class="absolute top-2 right-2 flex gap-2 z-10" v-if="!modalProps?.fullScreen">
                                        <button @click="openHtmlFullscreen(value)" class="p-2 bg-white/80 dark:bg-black/50 hover:bg-white dark:hover:bg-black text-gray-700 dark:text-gray-200 rounded-full shadow-sm backdrop-blur-sm transition-all border dark:border-gray-600" title="Open in New Tab">
                                            <IconMaximize class="w-4 h-4" />
                                        </button>
                                    </div>
                                    <!-- STANDALONE BUTTON: Only show in Fullscreen Modal mode -->
                                    <div v-if="modalProps?.fullScreen && Object.values(results)[0]?.html_output" class="absolute top-4 left-4 z-10">
                                        <button 
                                            @click="openHtmlFullscreen(Object.values(results)[0].html_output)"
                                            class="flex items-center gap-2 px-3 py-1 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all border border-blue-500/30"
                                            title="Pop out to separate browser window"
                                        >
                                            <IconMaximize class="w-3.5 h-3.5" />
                                            <span>Standalone Tab</span>
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
                                <div v-else class="relative group/json">
                                    <div class="absolute top-2 right-2 opacity-0 group-hover/json:opacity-100 transition-opacity z-10">
                                        <button 
                                            @click="copyToClipboard(JSON.stringify(value, null, 2))"
                                            class="p-1.5 bg-white dark:bg-gray-800 rounded-md shadow-sm border dark:border-gray-600 text-gray-500 hover:text-blue-500 transition-colors"
                                            title="Copy Data"
                                        >
                                            <IconCopy class="w-4 h-4" />
                                        </button>
                                    </div>
                                    <div class="p-3 bg-gray-100 dark:bg-gray-950 rounded font-mono text-xs overflow-x-auto border dark:border-gray-800">
                                        <pre class="text-gray-600 dark:text-gray-400">{{ JSON.stringify(value, null, 2) }}</pre>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #footer v-if="!modalProps?.fullScreen">
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
