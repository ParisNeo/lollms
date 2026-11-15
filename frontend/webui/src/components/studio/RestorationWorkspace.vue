<template>
    <div class="h-full flex flex-col lg:flex-row min-h-0 overflow-hidden">
        <!-- ── LEFT: RESTORATION CONTROL PANEL ── -->
        <aside class="w-full lg:w-[400px] shrink-0 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col overflow-hidden">
            <div class="grow overflow-y-auto custom-scrollbar p-4 space-y-4">

                <!-- Source drop zone -->
                <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Source Image</label>
                    <label
                        class="block rounded-xl border-2 border-dashed cursor-pointer transition-colors p-4 text-center"
                        :class="sourceImage ? 'border-emerald-400 bg-emerald-50/50 dark:bg-emerald-950/20' : 'border-gray-300 dark:border-gray-700 hover:border-emerald-400 hover:bg-emerald-50/30 dark:hover:bg-emerald-950/10'"
                    >
                        <IconArrowUpTray class="w-6 h-6 mx-auto mb-1 text-gray-400" />
                        <p class="text-[10px] font-bold text-gray-600 dark:text-gray-400">{{ sourceImage ? 'Replace Source' : 'Drop or click to upload' }}</p>
                        <input type="file" accept="image/*" class="hidden" @change="handleSourceUpload" />
                    </label>

                    <div v-if="sourceImage" class="flex items-center gap-2 p-2 rounded-lg bg-gray-50 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700">
                        <AuthenticatedImage :src="`/api/image-studio/images/${sourceImage.id}/thumbnail?size=128`" class="w-12 h-12 rounded-lg object-cover shrink-0" />
                        <div class="grow min-w-0">
                            <p class="text-[10px] font-bold truncate">{{ sourceImage.prompt || 'Source' }}</p>
                            <p class="text-[9px] font-mono text-gray-500">{{ sourceImage.width }}×{{ sourceImage.height }}</p>
                        </div>
                        <button @click="sourceImage = null" class="p-1 text-red-400"><IconXMark class="w-3.5 h-3.5" /></button>
                    </div>
                </div>

                <!-- Preset operations -->
                <div class="space-y-2">
                    <div class="flex items-center justify-between">
                        <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Restoration Preset</label>
                        <button v-if="selectedOperations.size" @click="selectedOperations.clear(); trigger = selectedOperations.size" class="text-[9px] font-bold text-red-500 uppercase hover:underline">Clear</button>
                    </div>
                    <div class="grid grid-cols-2 gap-1.5">
                        <button
                            v-for="op in operations"
                            :key="op.id"
                            @click="toggleOperation(op.id)"
                            class="p-2 rounded-xl border text-left transition-all"
                            :class="selectedOperations.has(op.id)
                                ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 ring-1 ring-emerald-500'
                                : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:border-emerald-300'"
                        >
                            <div class="text-base mb-0.5 leading-none">{{ op.emoji }}</div>
                            <div class="text-[10px] font-black uppercase tracking-tight">{{ op.label }}</div>
                            <div class="text-[8px] opacity-60 leading-tight mt-0.5">{{ op.hint }}</div>
                        </button>
                    </div>
                </div>

                <!-- Strength -->
                <div class="space-y-1.5 p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700">
                    <div class="flex justify-between items-center">
                        <label class="text-[10px] font-black text-gray-500 uppercase tracking-widest">Restoration Strength</label>
                        <span class="font-mono text-[10px] font-bold text-emerald-600 dark:text-emerald-400">{{ strength.toFixed(2) }}</span>
                    </div>
                    <input v-model.number="strength" type="range" min="0.15" max="1" step="0.05" class="w-full h-1.5 accent-emerald-500" />
                    <div class="flex justify-between text-[8px] font-mono text-gray-400">
                        <span>0.15 (Preserve)</span>
                        <span>1.00 (Full Restore)</span>
                    </div>
                </div>

                <!-- Additional prompt -->
                <div class="space-y-1.5">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Additional Instructions</label>
                    <textarea v-model="extraPrompt" rows="2" class="input-field !text-xs w-full resize-none" placeholder="e.g. 'remove coffee stain from corner', 'straighten o';"></textarea>
                </div>

                <!-- Output size (optional resize) -->
                <div class="space-y-1.5">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Output Size (optional resize)</label>
                    <div class="grid grid-cols-2 gap-1.5">
                        <select v-model="outW" class="input-field !text-xs !py-1">
                            <option :value="null">Original W</option>
                            <option v-for="w in [512, 1024, 1536, 2048, 3072]" :key="w" :value="w">{{ w }}px</option>
                        </select>
                        <select v-model="outH" class="input-field !text-xs !py-1">
                            <option :value="null">Original H</option>
                            <option v-for="h in [512, 1024, 1536, 2048, 3072]" :key="h" :value="h">{{ h }}px</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Action footer -->
            <div class="p-3 border-t border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 shrink-0">
                <button @click="processRestoration" :disabled="isProcessing || !sourceImage || !hasSelection" class="btn btn-primary w-full py-3 text-xs font-black uppercase tracking-widest flex items-center justify-center gap-2 !bg-emerald-600 hover:!bg-emerald-700 shadow-xl shadow-emerald-500/20">
                    <IconAnimateSpin v-if="isProcessing" class="w-4 h-4 animate-spin" />
                    <IconWrenchScrewdriver v-else class="w-4 h-4" />
                    <span>{{ isProcessing ? 'Processing…' : 'Restore Image' }}</span>
                </button>
                <p v-if="!hasSelection" class="text-[9px] text-gray-500 font-bold text-center mt-1.5">Select at least one preset operation</p>
            </div>
        </aside>

        <!-- ── RIGHT: SPLIT BEFORE/AFTER ── -->
        <section class="grow flex flex-col min-h-0 bg-gray-100 dark:bg-gray-950 overflow-hidden">
            <div class="shrink-0 px-4 py-2.5 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between bg-white/70 dark:bg-gray-900/70 backdrop-blur-md">
                <div>
                    <h2 class="text-xs font-black uppercase tracking-widest text-gray-700 dark:text-gray-200">Before / After Viewer</h2>
                    <p class="text-[10px] text-gray-500 dark:text-gray-400">Drag the divider to compare</p>
                </div>
                <div class="flex items-center gap-1">
                    <button v-if="resultImage" @click="openEditor" class="btn btn-secondary btn-xs h-7 flex items-center gap-1">
                        <IconPencil class="w-3 h-3" />
                        <span class="text-[10px] font-bold">Edit</span>
                    </button>
                    <button v-if="resultImage" @click="downloadResult" class="btn btn-secondary btn-xs h-7 flex items-center gap-1">
                        <IconArrowDownTray class="w-3 h-3" />
                        <span class="text-[10px] font-bold">Export</span>
                    </button>
                </div>
            </div>

            <div class="grow flex items-center justify-center p-4 overflow-hidden">
                <!-- Empty -->
                <div v-if="!sourceImage" class="text-center text-gray-400 space-y-2">
                    <span class="text-6xl opacity-20 block">🔧</span>
                    <p class="text-sm font-black uppercase tracking-widest text-gray-500">Upload a source image</p>
                    <p class="text-xs max-w-sm">Restore old photos, remove scratches, clean scans, colorize black-and-white images, or upscale to higher resolution.</p>
                </div>

                <!-- Compare viewer -->
                <div v-else class="relative max-w-full max-h-full rounded-2xl overflow-hidden shadow-2xl border-2 border-gray-300 dark:border-gray-700">
                    <!-- AFTER (background / right side) -->
                    <AuthenticatedImage
                        v-if="resultImage"
                        :src="`/api/image-studio/images/${resultImage.id}/file`"
                        class="block max-w-full max-h-[70vh] object-contain bg-white"
                    />
                    <AuthenticatedImage
                        v-else
                        :src="`/api/image-studio/images/${sourceImage.id}/file`"
                        class="block max-w-full max-h-[70vh] object-contain bg-white opacity-40"
                    />

                    <!-- BEFORE (clipped overlay / left) with drag divider -->
                    <div
                        class="absolute inset-0 overflow-hidden"
                        :style="{ width: `${splitPct}%` }"
                    >
                        <AuthenticatedImage
                            :src="`/api/image-studio/images/${sourceImage.id}/file`"
                            class="block max-w-full max-h-[70vh] object-contain bg-white"
                            :style="{ width: containerWidth ? containerWidth + 'px' : '100%' }"
                        />
                    </div>

                    <!-- Divider handle -->
                    <div
                        @mousedown.prevent="startDrag"
                        class="absolute inset-y-0 w-1 bg-white shadow-lg cursor-col-resize hover:bg-emerald-500 transition-colors"
                        :style="{ left: `calc(${splitPct}% - 2px)` }"
                    >
                        <div class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 left-1/2 w-8 h-8 rounded-full bg-white shadow-xl flex items-center justify-center border-2 border-emerald-500 text-emerald-600 text-xs font-black">
                            ⇔
                        </div>
                    </div>

                    <!-- Labels -->
                    <div class="absolute top-2 left-2 bg-black/70 backdrop-blur text-white text-[9px] font-black uppercase px-2 py-1 rounded-md tracking-widest pointer-events-none">Before</div>
                    <div class="absolute top-2 right-2 bg-emerald-600 text-white text-[9px] font-black uppercase px-2 py-1 rounded-md tracking-widest pointer-events-none" v-if="resultImage">After</div>

                    <!-- Processing overlay -->
                    <div v-if="isProcessing" class="absolute inset-0 bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center text-white">
                        <IconAnimateSpin class="w-10 h-10 animate-spin mb-3" />
                        <p class="text-[10px] font-black uppercase tracking-widest">AI Restoring…</p>
                    </div>
                </div>
            </div>
        </section>

        <ImageFormatExportModal
            :visible="isDownloadOpen" :default-filename="downloadFilename" :saving="isDownloading"
            title="Download Restored Image" @confirm="confirmDownload" @close="isDownloadOpen = false"
        />
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useImageStore } from '../../stores/images';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import ImageFormatExportModal from '../modals/ImageFormatExportModal.vue';
import { exportImageBlobAsFormat } from '../../services/imageExport';
import apiClient from '../../services/api';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

const emit = defineEmits(['request-edit']);
const imageStore = useImageStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const { images } = storeToRefs(imageStore);

// ── Restoration catalogue ──
const operations = [
    { id: 'despeckle',   emoji: '🧽', label: 'Despeckle',        hint: 'Dust & noise',    prompt: 'professionally despeckled, removed dust spots and print noise, ultra clean uniform background, 600 DPI clarity' },
    { id: 'deskew',      emoji: '📐', label: 'Deskew',           hint: 'Straighten',      prompt: 'perfectly deskewed leveled scan, straight horizontal baselines, square-cropped edges, geometric alignment' },
    { id: 'scratches',   emoji: '🩹', label: 'Heal Scratches',   hint: 'Crease repair',   prompt: 'seamless scratch, hair, and crease repair, damage-free restoration, pristine recovered surface' },
    { id: 'yellowed',    emoji: '📜', label: 'De-Yellow',        hint: 'Whiten paper',    prompt: 'removed yellowing, brown spots and foxing, pure clean white surfaces, deacidified archival tone' },
    { id: 'faded',       emoji: '🖋️', label: 'Fade Recovery',    hint: 'Boost ink',       prompt: 'restored faded ink and washed-out contrast, deepened low-opacity lettering, sharpened legibility' },
    { id: 'moiré',       emoji: '🌊', label: 'Remove Moiré',     hint: 'Descreen',        prompt: 'removed moiré interference patterns, descreened halftone print, clean digital reconstruction' },
    { id: 'colorcast',   emoji: '🎨', label: 'Neutralize Cast',  hint: 'White balance',   prompt: 'neutralized color cast, corrected cyan/blue/yellow tint, accurate natural paper tone, calibrated white balance' },
    { id: 'binarize',    emoji: '⚫', label: 'Binarize',         hint: 'OCR-ready',       prompt: 'clean binarized black-and-white conversion, crisp solid black ink on pure white, ready for OCR' },
    { id: 'colorize',    emoji: '🌈', label: 'Colorize B&W',     hint: 'Bring to life',   prompt: 'natural historical colorization, authentic human skin tones, realistic clothing pigments, vibrant balanced color depth' },
    { id: 'upscale',     emoji: '💎', label: 'Upscale 2×',       hint: 'Super-resolution', prompt: 'ultra-detailed super-resolution upscale, 8K pristine sharpness, recovered micro-detail, noise-free texture' },
    { id: 'denoise',     emoji: '🧼', label: 'Denoise',          hint: 'Clean sensor',    prompt: 'ultra clean denoising, grain removal, pristine smooth gradients, artifact elimination, studio sensor fidelity' },
    { id: 'sharpen',     emoji: '🔍', label: 'Sharpen',          hint: 'Tack sharp',      prompt: 'tack sharp contrast, crisp high-definition line recovery, well-resolved edges, ultra-focused' },
];

const selectedOperations = ref(new Set());
const strength = ref(0.65);
const extraPrompt = ref('');
const outW = ref(null);
const outH = ref(null);

const hasSelection = computed(() => selectedOperations.value.size > 0);

function toggleOperation(id) {
    const s = selectedOperations.value;
    if (s.has(id)) s.delete(id); else s.add(id);
    trigger.value = s.size; // force reactivity on Set mutation
}
const trigger = ref(0);

// ── Source management ──
const sourceImage = ref(null);
const resultImage = ref(null);
const isProcessing = ref(false);

async function handleSourceUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
        await imageStore.uploadImages([file]);
        // Newest image from the store is our source
        const fresh = images.value.find(i => i.filename?.includes(file.name) || true);
        sourceImage.value = images.value[0];
        resultImage.value = null;
        uiStore.addNotification('Source uploaded.', 'success', 1500);
    } catch (e) {
        uiStore.addNotification('Upload failed.', 'error');
    }
}

// ── Build prompt ──
function buildPrompt() {
    const parts = ['photorealistic restoration master'];
    Array.from(selectedOperations.value).forEach(id => {
        const op = operations.find(o => o.id === id);
        if (op) parts.push(op.prompt);
    });
    if (extraPrompt.value.trim()) parts.push(extraPrompt.value.trim());
    return parts.join('. ');
}

// ── Process via editImage (img2img) ──
async function processRestoration() {
    if (!sourceImage.value || !hasSelection.value) return;
    isProcessing.value = true;
    const model = authStore.user?.iti_binding_model_name || authStore.user?.tti_binding_model_name;
    if (!model) { uiStore.addNotification('Configure a TTI model.', 'warning'); isProcessing.value = false; return; }

    // Compute target dimensions
    let w = outW.value || sourceImage.value.width || 1024;
    let h = outH.value || sourceImage.value.height || 1024;

    // Snapshot existing IDs (including the source) and detect the restoration
    // result by IDENTITY — server clock drift / timezone mismatch made the
    // previous `new Date(i.created_at) >= started` comparison unreliable, so
    // the viewer could stay in its "processing…" overlay even after the image
    // had already landed in the store.
    const beforeIds = new Set((images.value || []).map(i => i.id));
    if (sourceImage.value?.id) beforeIds.add(sourceImage.value.id);

    try {
        const task = await imageStore.editImage({
            prompt: buildPrompt(),
            negative_prompt: 'blurry, distorted, artifacts, dirty, watermarked, low resolution, deformation',
            model,
            image_ids: [sourceImage.value.id],
            width: w,
            height: h,
            strength: strength.value
        });
        if (task?.id) {
            await waitForResult(beforeIds);
        }
    } catch (e) {
        uiStore.addNotification('Restoration failed.', 'error');
    } finally {
        isProcessing.value = false;
    }
}

function waitForResult(beforeIds) {
    return new Promise(resolve => {
        let elapsed = 0;
        let resolved = false;
        const finish = (img) => {
            if (resolved) return;
            resolved = true;
            if (img) {
                resultImage.value = img;
                uiStore.addNotification('Restoration complete!', 'success', 2000);
            }
            clearInterval(interval);
            resolve();
        };
        const interval = setInterval(() => {
            const fresh = (images.value || []).find(i => !beforeIds.has(i.id));
            if (fresh) { finish(fresh); return; }
            elapsed += 250;
            if (elapsed > 180000) finish(null); // safety timeout 3 min
        }, 250);
    });
}

// ── Split viewer ──
const splitPct = ref(50);
const isDragging = ref(false);
const containerWidth = ref(0);

function startDrag(e) {
    isDragging.value = true;
    window.addEventListener('mousemove', onDrag);
    window.addEventListener('mouseup', stopDrag);
}
function onDrag(e) {
    if (!isDragging.value) return;
    const rect = e.currentTarget?.getBoundingClientRect?.() || { left: 0, width: window.innerWidth };
    const target = document.querySelector('.relative.max-w-full') || { getBoundingClientRect: () => ({ left: 0, width: window.innerWidth }) };
    const r = target.getBoundingClientRect();
    splitPct.value = Math.max(2, Math.min(98, ((e.clientX - r.left) / r.width) * 100));
}
function stopDrag() {
    isDragging.value = false;
    window.removeEventListener('mousemove', onDrag);
    window.removeEventListener('mouseup', stopDrag);
}

// ── Actions ──
function openEditor() {
    if (resultImage.value?.id) emit('request-edit', resultImage.value.id);
}

const isDownloadOpen = ref(false);
const isDownloading = ref(false);
const downloadFilename = computed(() => {
    const img = resultImage.value;
    if (!img) return 'restored';
    return (img.prompt || 'restored').trim().slice(0, 40).replace(/[^\w\s-]/g, '').replace(/\s+/g, '_') || 'restored';
});

function downloadResult() { if (resultImage.value) isDownloadOpen.value = true; }

async function confirmDownload({ format, quality, filename }) {
    if (!resultImage.value) return;
    isDownloading.value = true;
    try {
        const res = await apiClient.get(`/api/image-studio/images/${resultImage.value.id}/file`, { responseType: 'blob' });
        const { filename: saved } = await exportImageBlobAsFormat(res.data, { format, quality, filename });
        uiStore.addNotification(`Downloaded ${saved}`, 'success', 2000);
        isDownloadOpen.value = false;
    } catch (e) {
        uiStore.addNotification('Download failed.', 'error');
    } finally {
        isDownloading.value = false;
    }
}
</script>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>