<script setup>
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import JsonRenderer from '../ui/JsonRenderer.vue';

const props = defineProps({
    store: { type: Object, required: true }
});

const dataStore = useDataStore();
const uiStore = useUiStore();

const canvasRef = ref(null);
const isLoading = ref(false);
const dataLake = ref({ points: [], documents: [], total_chunks: 0, reduction_method: 'PCA' });
const reductionMethod = ref('pca');

const searchTerm = ref('');
const activeDocumentFilter = ref(null);
const selectedPoint = ref(null);
const hoveredPoint = ref(null);
const showLabels = ref(true);

const transform = ref({ x: 0, y: 0, scale: 1 });
const isDragging = ref(false);
const dragStart = ref({ x: 0, y: 0 });

const filteredPoints = computed(() => {
    let list = dataLake.value.points || [];
    if (activeDocumentFilter.value) {
        list = list.filter(p => p.document_id === activeDocumentFilter.value);
    }
    if (searchTerm.value.trim()) {
        const query = searchTerm.value.toLowerCase().trim();
        list = list.filter(p => 
            p.document_name.toLowerCase().includes(query) ||
            p.full_text.toLowerCase().includes(query)
        );
    }
    return list;
});

async function loadDataLake() {
    if (!props.store?.id) return;
    isLoading.value = true;
    try {
        const res = await dataStore.fetchDataLakeData(props.store.id, reductionMethod.value);
        dataLake.value = res || { points: [], documents: [], total_chunks: 0, reduction_method: 'PCA' };
        resetView();
    } catch (e) {
        console.error("Failed to load data lake:", e);
        uiStore.addNotification("Could not load embedding data lake.", "error");
    } finally {
        isLoading.value = false;
        nextTick(() => renderCanvas());
    }
}

function resetView() {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    transform.value = {
        x: rect.width / 2,
        y: rect.height / 2,
        scale: Math.min(rect.width, rect.height) * 0.42
    };
    renderCanvas();
}

function renderCanvas() {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    if (canvas.width !== rect.width * dpr || canvas.height !== rect.height * dpr) {
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
    }

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const isDark = uiStore.currentTheme === 'dark';

    ctx.strokeStyle = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';
    ctx.lineWidth = 1;

    const { x: cx, y: cy, scale } = transform.value;

    ctx.beginPath();
    ctx.moveTo(0, cy);
    ctx.lineTo(rect.width, cy);
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, rect.height);
    ctx.stroke();

    for (let r = 0.25; r <= 1.0; r += 0.25) {
        ctx.beginPath();
        ctx.arc(cx, cy, r * scale, 0, Math.PI * 2);
        ctx.stroke();
    }

    const points = filteredPoints.value;
    const searchActive = !!searchTerm.value.trim();

    if (activeDocumentFilter.value || searchActive) {
        const all = dataLake.value.points || [];
        ctx.fillStyle = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)';
        all.forEach(p => {
            const screenX = cx + p.x * scale;
            const screenY = cy + p.y * scale;
            ctx.beginPath();
            ctx.arc(screenX, screenY, 3, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    points.forEach(p => {
        const screenX = cx + p.x * scale;
        const screenY = cy + p.y * scale;

        const isHovered = hoveredPoint.value?.id === p.id;
        const isSelected = selectedPoint.value?.id === p.id;

        const radius = isSelected ? 8 : (isHovered ? 7 : 4.5);

        if (isHovered || isSelected) {
            ctx.beginPath();
            ctx.arc(screenX, screenY, radius + 4, 0, Math.PI * 2);
            ctx.fillStyle = isSelected ? 'rgba(59, 130, 246, 0.3)' : 'rgba(255, 255, 255, 0.25)';
            ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(screenX, screenY, radius, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.fill();
        ctx.lineWidth = isSelected ? 2.5 : 1;
        ctx.strokeStyle = isSelected ? '#ffffff' : (isDark ? '#0f172a' : '#ffffff');
        ctx.stroke();
    });

    if (showLabels.value && !activeDocumentFilter.value) {
        dataLake.value.documents.forEach(doc => {
            const screenX = cx + doc.centroid.x * scale;
            const screenY = cy + doc.centroid.y * scale;

            ctx.font = 'bold 10px Inter, sans-serif';
            const metrics = ctx.measureText(doc.name);
            const padding = 4;

            ctx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.85)' : 'rgba(255, 255, 255, 0.85)';
            ctx.strokeStyle = doc.color;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.roundRect(
                screenX - metrics.width / 2 - padding,
                screenY - 14 - padding,
                metrics.width + padding * 2,
                16 + padding,
                6
            );
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = isDark ? '#f1f5f9' : '#0f172a';
            ctx.textAlign = 'center';
            ctx.fillText(doc.name, screenX, screenY - 4);
        });
    }

    ctx.restore();
}

function handleMouseDown(e) {
    isDragging.value = true;
    dragStart.value = { x: e.clientX, y: e.clientY };
}

function handleMouseMove(e) {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();

    if (isDragging.value) {
        const dx = e.clientX - dragStart.value.x;
        const dy = e.clientY - dragStart.value.y;
        transform.value.x += dx;
        transform.value.y += dy;
        dragStart.value = { x: e.clientX, y: e.clientY };
        renderCanvas();
        return;
    }

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const { x: cx, y: cy, scale } = transform.value;

    let closest = null;
    let minDistance = 12;

    filteredPoints.value.forEach(p => {
        const screenX = cx + p.x * scale;
        const screenY = cy + p.y * scale;
        const dist = Math.hypot(screenX - mouseX, screenY - mouseY);
        if (dist < minDistance) {
            minDistance = dist;
            closest = { ...p, screenX, screenY };
        }
    });

    if (closest !== hoveredPoint.value) {
        hoveredPoint.value = closest;
        renderCanvas();
    }
}

function handleMouseUp() {
    isDragging.value = false;
}

function handleClick(e) {
    if (hoveredPoint.value) {
        selectedPoint.value = hoveredPoint.value;
    } else {
        selectedPoint.value = null;
    }
    renderCanvas();
}

function handleWheel(e) {
    e.preventDefault();
    const canvas = canvasRef.value;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    const newScale = Math.max(50, Math.min(5000, transform.value.scale * zoomFactor));

    transform.value.x = mouseX - (mouseX - transform.value.x) * (newScale / transform.value.scale);
    transform.value.y = mouseY - (mouseY - transform.value.y) * (newScale / transform.value.scale);
    transform.value.scale = newScale;

    renderCanvas();
}

function toggleDocumentSolo(docId) {
    if (activeDocumentFilter.value === docId) {
        activeDocumentFilter.value = null;
    } else {
        activeDocumentFilter.value = docId;
    }
    renderCanvas();
}

function openStandaloneVisualizer() {
    if (!props.store?.id) return;
    const url = `/api/store/${props.store.id}/data-lake/export-html?method=${reductionMethod.value}`;
    window.open(url, '_blank');
}

function copyText(text) {
    navigator.clipboard.writeText(text);
    uiStore.addNotification("Chunk text copied.", "success");
}

watch([reductionMethod, () => props.store?.id], () => {
    loadDataLake();
});

watch([searchTerm, showLabels], () => {
    renderCanvas();
});

watch(() => uiStore.currentTheme, () => {
    nextTick(() => renderCanvas());
});

onMounted(() => {
    loadDataLake();
    window.addEventListener('resize', renderCanvas);
});

onUnmounted(() => {
    window.removeEventListener('resize', renderCanvas);
});
</script>

<template>
    <div class="h-full flex flex-col overflow-hidden bg-white dark:bg-gray-950 relative select-none">
        <header class="px-5 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex flex-wrap items-center justify-between gap-4 shrink-0 z-20">
            <div class="flex items-center gap-3">
                <div class="flex items-center gap-1.5">
                    <span class="text-xs font-black uppercase text-gray-500 tracking-wider">Projection:</span>
                    <select v-model="reductionMethod" class="input-field !py-1 !px-2.5 text-xs font-bold bg-white dark:bg-gray-800">
                        <option value="pca">PCA (Fast SVD)</option>
                        <option value="tsne">t-SNE (Manifold Clustering)</option>
                    </select>
                </div>

                <div class="h-4 w-px bg-gray-300 dark:bg-gray-700"></div>

                <label class="flex items-center gap-1.5 text-xs font-bold text-gray-500 cursor-pointer">
                    <input type="checkbox" v-model="showLabels" class="rounded text-blue-600">
                    <span>Cluster Labels</span>
                </label>
            </div>

            <div class="flex items-center gap-2 grow max-w-xs">
                <div class="relative w-full">
                    <input 
                        type="text" 
                        v-model="searchTerm" 
                        placeholder="Search text in lake..." 
                        class="input-field !py-1 !pl-8 !pr-7 text-xs w-full bg-white dark:bg-gray-800"
                    />
                    <IconMagnifyingGlass class="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <button v-if="searchTerm" @click="searchTerm = ''" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                        <IconXMark class="w-3 h-3" />
                    </button>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <button @click="openStandaloneVisualizer" class="btn btn-secondary btn-sm h-8 flex items-center gap-1 text-blue-600 dark:text-blue-400" title="Open Standalone Interactive Visualizer">
                    <IconGlobeAlt class="w-3.5 h-3.5" />
                    <span class="hidden sm:inline">Interactive HTML</span>
                </button>
                <button @click="loadDataLake(true)" class="btn btn-secondary btn-sm h-8" title="Force Recompute 2D Vectors">
                    <IconRefresh class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
                    <span class="hidden sm:inline">Refresh</span>
                </button>
                <button @click="resetView" class="btn btn-secondary btn-sm h-8" title="Center View">
                    <IconMaximize class="w-3.5 h-3.5" />
                    <span>Fit</span>
                </button>
            </div>
        </header>

        <div class="grow flex flex-row overflow-hidden relative">
            <div class="grow h-full relative overflow-hidden cursor-crosshair">
                <canvas 
                    ref="canvasRef"
                    class="absolute inset-0 w-full h-full"
                    @mousedown="handleMouseDown"
                    @mousemove="handleMouseMove"
                    @mouseup="handleMouseUp"
                    @click="handleClick"
                    @wheel="handleWheel"
                ></canvas>

                <div 
                    v-if="hoveredPoint && !isDragging"
                    class="absolute pointer-events-none z-30 bg-white/95 dark:bg-gray-900/95 backdrop-blur-md p-3.5 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 max-w-xs transition-opacity duration-150"
                    :style="{ left: hoveredPoint.screenX + 'px', top: hoveredPoint.screenY + 'px', transform: 'translate(-50%, -120%)' }"
                >
                    <div class="flex items-center gap-2 pb-1.5 border-b dark:border-gray-800 mb-2">
                        <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: hoveredPoint.color }"></span>
                        <span class="font-bold text-xs truncate text-gray-900 dark:text-white">{{ hoveredPoint.document_name }}</span>
                        <span class="text-[9px] font-mono text-gray-400">#{{ hoveredPoint.chunk_index }}</span>
                    </div>
                    <p class="text-[11px] text-gray-600 dark:text-gray-300 line-clamp-3 leading-relaxed italic">
                        "{{ hoveredPoint.text_snippet }}"
                    </p>
                    <span class="block mt-2 text-[9px] font-bold text-blue-500 uppercase tracking-wider">Click to Inspect Chunk</span>
                </div>

                <div v-if="!isLoading && dataLake.total_chunks === 0" class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center p-6">
                    <IconFileText class="w-12 h-12 text-gray-300 dark:text-gray-700 mb-3" />
                    <h4 class="text-sm font-bold text-gray-600 dark:text-gray-300 uppercase tracking-wider">No Chunks Embedded Yet</h4>
                    <p class="text-xs text-gray-400 mt-1 max-w-xs">Upload documents into this DataStore to see them projected into the 2D Data Lake.</p>
                </div>

                <div v-if="isLoading" class="absolute inset-0 bg-white/70 dark:bg-gray-950/70 backdrop-blur-sm z-40 flex flex-col items-center justify-center">
                    <IconAnimateSpin class="w-8 h-8 text-blue-600 animate-spin mb-2" />
                    <span class="text-xs font-black uppercase text-gray-700 dark:text-gray-300 tracking-widest">Projecting 2D Vectors...</span>
                </div>
            </div>

            <aside class="w-64 shrink-0 border-l border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/40 flex flex-col z-10 overflow-hidden">
                <div class="p-3 border-b dark:border-gray-800 flex items-center justify-between">
                    <div>
                        <h4 class="text-xs font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Documents</h4>
                        <p class="text-[10px] text-gray-400">{{ dataLake.total_chunks }} chunks total</p>
                    </div>
                    <button v-if="activeDocumentFilter" @click="activeDocumentFilter = null" class="text-[10px] font-bold text-blue-500 hover:underline">
                        Show All
                    </button>
                </div>

                <div class="grow overflow-y-auto custom-scrollbar p-2 space-y-1.5">
                    <div 
                        v-for="doc in dataLake.documents" 
                        :key="doc.id"
                        @click="toggleDocumentSolo(doc.id)"
                        class="flex items-center justify-between p-2 rounded-xl text-xs cursor-pointer transition-all border"
                        :class="activeDocumentFilter === doc.id ? 'bg-white dark:bg-gray-800 border-blue-500 shadow-sm font-bold' : 'border-transparent hover:bg-white dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300 opacity-80 hover:opacity-100'"
                    >
                        <div class="flex items-center gap-2 min-w-0 pr-2">
                            <span class="w-3 h-3 rounded-full shrink-0 shadow-xs" :style="{ backgroundColor: doc.color }"></span>
                            <span class="truncate" :title="doc.name">{{ doc.name }}</span>
                        </div>
                        <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-gray-200/60 dark:bg-gray-700/60 text-gray-600 dark:text-gray-300 shrink-0">
                            {{ doc.chunk_count }}
                        </span>
                    </div>
                </div>
            </aside>

            <Transition
                enter-active-class="transition-all duration-300 ease-out"
                enter-from-class="translate-x-full"
                enter-to-class="translate-x-0"
                leave-active-class="transition-all duration-200 ease-in"
                leave-from-class="translate-x-0"
                leave-to-class="translate-x-full"
            >
                <aside v-if="selectedPoint" class="w-80 lg:w-96 shrink-0 h-full border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col z-30 shadow-2xl p-5 space-y-4 overflow-y-auto custom-scrollbar absolute right-0 inset-y-0">
                    <div class="flex items-center justify-between border-b dark:border-gray-800 pb-3">
                        <div class="flex items-center gap-2">
                            <span class="w-3.5 h-3.5 rounded-full" :style="{ backgroundColor: selectedPoint.color }"></span>
                            <h4 class="font-black text-sm uppercase tracking-wider text-gray-800 dark:text-gray-200">Chunk Inspector</h4>
                        </div>
                        <button @click="selectedPoint = null" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg">✕</button>
                    </div>

                    <div>
                        <span class="text-[10px] font-bold uppercase text-gray-400">Document</span>
                        <div class="font-bold text-sm text-gray-900 dark:text-white mt-0.5">{{ selectedPoint.document_name }}</div>
                    </div>

                    <div class="flex items-center justify-between text-xs p-2.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl border dark:border-gray-700/60 font-mono">
                        <span>Chunk Index: <b>#{{ selectedPoint.chunk_index }}</b></span>
                        <span>Length: <b>{{ selectedPoint.full_text.length }} chars</b></span>
                    </div>

                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <span class="text-[10px] font-bold uppercase text-gray-400">Full Text Content</span>
                            <button @click="copyText(selectedPoint.full_text)" class="text-xs text-blue-500 hover:underline flex items-center gap-1">
                                <IconCopy class="w-3.5 h-3.5" /> Copy
                            </button>
                        </div>
                        <div class="p-3 bg-gray-50 dark:bg-gray-950 rounded-xl border dark:border-gray-800 text-xs font-mono max-h-64 overflow-y-auto custom-scrollbar leading-relaxed whitespace-pre-wrap text-gray-800 dark:text-gray-200">
                            {{ selectedPoint.full_text }}
                        </div>
                    </div>

                    <div v-if="selectedPoint.metadata && Object.keys(selectedPoint.metadata).length > 0">
                        <span class="text-[10px] font-bold uppercase text-gray-400 block mb-1">Metadata</span>
                        <JsonRenderer :json="selectedPoint.metadata" class="p-2.5 bg-gray-50 dark:bg-gray-950 rounded-xl border dark:border-gray-800 text-[10px]" />
                    </div>
                </aside>
            </Transition>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>