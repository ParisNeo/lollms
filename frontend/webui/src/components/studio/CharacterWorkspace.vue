<template>
    <div class="h-full flex flex-col lg:flex-row min-h-0 overflow-hidden">
        <!-- ── LEFT: CHARACTER SHEET ── -->
        <aside class="w-full lg:w-[420px] shrink-0 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col overflow-hidden">
            <div class="grow overflow-y-auto custom-scrollbar p-4 space-y-4">

                <!-- Character identity -->
                <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Character Sheet</label>
                    <input v-model="character.name" type="text" class="input-field !text-sm font-bold w-full" placeholder="Character name (e.g. 'Sir Aldric')" />
                    <textarea v-model="character.description" rows="3" class="input-field !text-xs w-full resize-none" placeholder="Appearance, personality, clothing, key features..."></textarea>
                </div>

                <!-- Style presets -->
                <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Visual Style</label>
                    <div class="grid grid-cols-2 gap-1.5">
                        <button
                            v-for="style in visualStyles"
                            :key="style.id"
                            @click="character.style = style.id"
                            class="p-2 rounded-lg border text-left transition-all"
                            :class="character.style === style.id
                                ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 ring-1 ring-purple-500'
                                : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-purple-300'"
                        >
                            <div class="text-base mb-0.5 leading-none">{{ style.emoji }}</div>
                            <div class="text-[10px] font-black uppercase tracking-tight">{{ style.label }}</div>
                        </button>
                    </div>
                </div>

                <!-- Mode tabs (what to generate) -->
                <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Generation Mode</label>
                    <div class="grid grid-cols-2 gap-1.5">
                        <button
                            v-for="m in modes"
                            :key="m.id"
                            @click="activeMode = m.id"
                            class="p-2 rounded-lg border text-left transition-all"
                            :class="activeMode === m.id
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 ring-1 ring-blue-500'
                                : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-blue-300'"
                        >
                            <div class="text-base mb-0.5 leading-none">{{ m.emoji }}</div>
                            <div class="text-[10px] font-black uppercase tracking-tight">{{ m.label }}</div>
                        </button>
                    </div>
                </div>

                <!-- Pose/expression selector (contextual per mode) -->
                <div v-if="['poses', 'expressions'].includes(activeMode)" class="space-y-2">
                    <div class="flex items-center justify-between">
                        <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">
                            {{ activeMode === 'poses' ? 'Poses' : 'Expressions' }} ({{ selectedVariants.size }}/{{ currentVariants.length }})
                        </label>
                        <button @click="toggleAllVariants" class="text-[9px] font-bold text-blue-500 uppercase hover:underline">
                            {{ selectedVariants.size === currentVariants.length ? 'None' : 'All' }}
                        </button>
                    </div>
                    <div class="grid grid-cols-3 gap-1">
                        <button
                            v-for="v in currentVariants"
                            :key="v.id"
                            @click="toggleVariant(v.id)"
                            class="p-1.5 rounded-lg border text-center transition-all"
                            :class="selectedVariants.has(v.id)
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                                : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-gray-300'"
                        >
                            <div class="text-sm leading-none">{{ v.emoji }}</div>
                            <div class="text-[8px] font-bold uppercase tracking-tight mt-0.5">{{ v.label }}</div>
                        </button>
                    </div>
                </div>

                <!-- Tile / asset settings -->
                <div v-if="['tiles', 'assets3d'].includes(activeMode)" class="space-y-2 p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700">
                    <label class="text-[10px] font-black text-gray-500 uppercase tracking-widest block">
                        {{ activeMode === 'tiles' ? 'Tile Size' : 'Asset Type' }}
                    </label>
                    <select v-if="activeMode === 'tiles'" v-model="tileSize" class="input-field !text-xs w-full">
                        <option value="32x32">32×32 (Retro RPG)</option>
                        <option value="64x64">64×64 (Modern Pixel)</option>
                        <option value="128x128">128×128 (Detailed)</option>
                        <option value="256x256">256×256 (HD Tile)</option>
                        <option value="512x512">512×512 (Icon / Portrait)</option>
                    </select>
                    <select v-else v-model="asset3dType" class="input-field !text-xs w-full">
                        <option value="glb">GLB character model</option>
                        <option value="pose">Pose rig prompt</option>
                        <option value="material">Material/texture set</option>
                        <option value="turntable">Turntable angle sheet</option>
                        <option value="reference">Multi-angle reference sheet</option>
                    </select>
                </div>

                <!-- Extra style notes -->
                <div class="space-y-1.5">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Extra Notes</label>
                    <textarea v-model="extraNotes" rows="2" class="input-field !text-xs w-full resize-none" placeholder="e.g. 'add a subtle scar over left eye', 'wear a red cape'"></textarea>
                </div>
            </div>

            <!-- Generate button -->
            <div class="p-3 border-t border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 shrink-0">
                <button @click="generate" :disabled="isGenerating || !canGenerate" class="btn btn-primary w-full py-3 text-xs font-black uppercase tracking-widest flex items-center justify-center gap-2 !bg-purple-600 hover:!bg-purple-700 shadow-xl shadow-purple-500/20">
                    <IconAnimateSpin v-if="isGenerating" class="w-4 h-4 animate-spin" />
                    <IconSparkles v-else class="w-4 h-4" />
                    <span>{{ isGenerating ? 'Generating…' : generateButtonLabel }}</span>
                </button>
            </div>
        </aside>

        <!-- ── RIGHT: RESULT GALLERY & ACTION BAR ── -->
        <section class="grow flex flex-col min-h-0 bg-gray-50 dark:bg-gray-950 overflow-hidden">
            <div class="shrink-0 px-4 py-2.5 border-b border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/70 backdrop-blur-md flex items-center justify-between gap-3">
                <div class="min-w-0">
                    <h2 class="text-xs font-black uppercase tracking-widest text-gray-700 dark:text-gray-200 truncate">
                        {{ character.name || 'Untitled Character' }}
                    </h2>
                    <p class="text-[10px] text-gray-500 dark:text-gray-400 truncate">{{ sessionResults.length }} asset{{ sessionResults.length === 1 ? '' : 's' }} this session</p>
                </div>
                <div class="flex items-center gap-1 shrink-0">
                    <button v-if="sessionResults.length" @click="exportTileSheet" class="btn btn-secondary btn-xs h-7 flex items-center gap-1" title="Export all as a tile sheet">
                        <IconSquares2x2 class="w-3 h-3" />
                        <span class="text-[10px] font-bold">Sheet</span>
                    </button>
                    <button v-if="sessionResults.length" @click="sessionResults = []" class="text-[10px] font-bold text-red-500 uppercase hover:underline">Clear</button>
                </div>
            </div>

            <div class="grow overflow-y-auto custom-scrollbar p-4">
                <!-- Empty -->
                <div v-if="sessionResults.length === 0 && !isGenerating" class="h-full flex flex-col items-center justify-center text-gray-400 space-y-2">
                    <span class="text-6xl opacity-20">🎭</span>
                    <p class="text-sm font-black uppercase tracking-widest text-gray-500">Build your character</p>
                    <p class="text-xs max-w-md text-center">Define appearance, pick a style, choose a mode (portraits, poses, expressions, tiles, 3D assets), and generate a reusable asset set.</p>
                </div>

                <!-- Loading (only when no results have landed yet — once the
                     first asset arrives we switch to the results grid) -->
                <div v-if="isGenerating && sessionResults.length === 0" class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
                    <div v-for="i in expectedCount" :key="'skel-'+i" class="aspect-square rounded-2xl bg-white dark:bg-gray-900 border-2 border-purple-200 dark:border-purple-900/50 flex items-center justify-center animate-pulse">
                        <IconAnimateSpin class="w-8 h-8 text-purple-500 animate-spin" />
                    </div>
                </div>

                <!-- Results grid -->
                <div v-else class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
                    <div v-for="(img, idx) in sessionResults" :key="img.id"
                        class="group relative rounded-2xl overflow-hidden border-2 border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-md hover:shadow-xl transition-all"
                    >
                        <AuthenticatedImage :src="`/api/image-studio/images/${img.id}/thumbnail?size=520`" class="w-full aspect-square object-cover" />
                        <span class="absolute top-1.5 left-1.5 bg-black/60 backdrop-blur text-white text-[9px] font-mono font-black px-1.5 py-0.5 rounded">#{{ idx + 1 }}</span>
                        <div class="absolute inset-0 bg-gradient-to-t from-black/90 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-2 gap-1">
                            <p class="text-white text-[9px] line-clamp-2 font-serif italic mb-1">"{{ img.prompt }}"</p>
                            <div class="flex items-center gap-1">
                                <button @click="openEditor(img)" class="p-1.5 bg-white/15 hover:bg-purple-500 rounded text-white backdrop-blur"><IconPencil class="w-3 h-3" /></button>
                                <button @click="download(img)" class="p-1.5 bg-white/15 hover:bg-emerald-500 rounded text-white backdrop-blur"><IconArrowDownTray class="w-3 h-3" /></button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 3D Export panel -->
                <div v-if="activeMode === 'assets3d' && sessionResults.length > 0" class="mt-4 p-3 rounded-xl bg-purple-50/60 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-900/40">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-[10px] font-black uppercase text-purple-700 dark:text-purple-300 tracking-wider">3D Asset Prompt</span>
                        <button @click="copy3dPrompt" class="text-[9px] font-bold text-purple-600 hover:underline uppercase">Copy</button>
                    </div>
                    <pre class="text-[9px] font-mono text-purple-800 dark:text-purple-200 whitespace-pre-wrap bg-white/60 dark:bg-gray-900/60 p-2 rounded-lg max-h-40 overflow-y-auto custom-scrollbar">{{ threeDPromptText }}</pre>
                </div>
            </div>
        </section>

        <ImageFormatExportModal
            :visible="isDownloadOpen" :default-filename="downloadFilename" :saving="isDownloading"
            title="Download Asset" @confirm="confirmDownload" @close="isDownloadOpen = false"
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
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconSquares2x2 from '../../assets/icons/IconSquares2x2.vue';

const emit = defineEmits(['request-edit']);
const imageStore = useImageStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const { images } = storeToRefs(imageStore);

// ── Character state ──
const character = ref({ name: '', description: '', style: 'painterly' });
const extraNotes = ref('');

const visualStyles = [
    { id: 'painterly', emoji: '🎨', label: 'Painterly' },
    { id: 'anime',     emoji: '🌸', label: 'Anime' },
    { id: 'realistic', emoji: '📷', label: 'Realistic' },
    { id: 'pixelart',  emoji: '🟦', label: 'Pixel Art' },
    { id: 'comic',     emoji: '💥', label: 'Comic' },
    { id: '3d',        emoji: '🧊', label: '3D / CGI' },
];

const modes = [
    { id: 'portrait',   emoji: '👤', label: 'Portraits' },
    { id: 'fullbody',   emoji: '🧍', label: 'Full Body' },
    { id: 'poses',      emoji: '🏃', label: 'Poses' },
    { id: 'expressions',emoji: '😊', label: 'Expressions' },
    { id: 'tiles',      emoji: '🎮', label: 'Game Tiles' },
    { id: 'assets3d',   emoji: '🧊', label: '3D / Assets' },
];

const activeMode = ref('portrait');

// ── Poses / expressions ──
const poses = [
    { id: 'idle',     emoji: '🧍', label: 'Idle',     prompt: 'relaxed idle stance, weight on one leg, arms at sides, chest facing camera' },
    { id: 'walk',     emoji: '🚶', label: 'Walk',     prompt: 'mid-walk cycle, one leg forward, opposite arm swing, natural momentum' },
    { id: 'run',      emoji: '🏃', label: 'Run',      prompt: 'full sprint cycle, aggressive forward lean, arms pumping, determined face' },
    { id: 'attack',   emoji: '⚔️', label: 'Attack',   prompt: 'powerful attack stance, weapon raised, dynamic weight transfer, fierce expression' },
    { id: 'block',    emoji: '🛡️', label: 'Block',    prompt: 'defensive guard stance, forearms crossed, braced against impact' },
    { id: 'cast',     emoji: '✨', label: 'Cast',     prompt: 'spellcasting pose, arms extended forward, fingers splayed, glowing magic aura' },
    { id: 'victory',  emoji: '🏆', label: 'Victory',  prompt: 'triumphant victory pose, weapon raised high, head lifted, confident stance' },
    { id: 'defeat',   emoji: '💀', label: 'Defeat',   prompt: 'defeated kneeling pose, head bowed, arms limp, exhausted body language' },
    { id: 'jump',     emoji: '⬆️', label: 'Jump',     prompt: 'mid-air jumping pose, legs tucked, arms extended, dynamic motion energy' },
];

const expressions = [
    { id: 'neutral',   emoji: '😐', label: 'Neutral',   prompt: 'neutral expression, relaxed brows, calm set mouth, default portrait framing' },
    { id: 'happy',     emoji: '😊', label: 'Happy',     prompt: 'genuine happy expression, warm smile, crinkled eyes, radiant joy' },
    { id: 'angry',     emoji: '😠', label: 'Angry',     prompt: 'furious angry expression, narrowed brows, clenched jaw, glaring eyes' },
    { id: 'sad',       emoji: '😢', label: 'Sad',       prompt: 'melancholic sad expression, downturned mouth, glossy tired eyes' },
    { id: 'surprised', emoji: '😲', label: 'Surprised', prompt: 'wide-eyed surprised expression, raised brows, slightly parted mouth' },
    { id: 'determined',emoji: '😤', label: 'Determined',prompt: 'determined confident expression, focused gaze, set jaw, fierce resolve' },
    { id: 'smirk',     emoji: '😏', label: 'Smirk',     prompt: 'cocky knowing smirk, one lifted brow corner, confident half-smile' },
    { id: 'pained',    emoji: '😖', label: 'Pained',    prompt: 'pained gritted-teeth expression, wincing brows, tense features' },
];

const currentVariants = computed(() => activeMode.value === 'poses' ? poses : activeMode.value === 'expressions' ? expressions : []);
const selectedVariants = ref(new Set(['idle']));

function toggleVariant(id) {
    const s = selectedVariants.value;
    if (s.has(id)) s.delete(id); else s.add(id);
    selectedVariants.value = new Set(s);
}
function toggleAllVariants() {
    if (selectedVariants.value.size === currentVariants.value.length) {
        selectedVariants.value = new Set();
    } else {
        selectedVariants.value = new Set(currentVariants.value.map(v => v.id));
    }
}

// ── Tile / asset settings ──
const tileSize = ref('64x64');
const asset3dType = ref('glb');

// ── Prompt builder ──
function stylePrefix() {
    const map = {
        painterly: 'digital painting, expressive brushwork, rich painterly shading, illustration masterpiece',
        anime:     'anime illustration, crisp cel-shading, expressive eyes, vibrant clean lineart',
        realistic: 'photorealistic, ultra-detailed, natural lighting, lifelike textures, photographic quality',
        pixelart:  'pixel art sprite, retro 16-bit aesthetic, limited color palette, clean pixel-perfect shapes',
        comic:     'comic book illustration, bold black ink linework, flat vibrant colors, halftone shading',
        '3d':      'polished 3D render, CGI quality, PBR materials, raytraced lighting, Octane quality',
    };
    return map[character.value.style] || map.painterly;
}

function characterPrefix() {
    const name = character.value.name ? `${character.value.name}, ` : '';
    const desc = character.value.description || 'a character';
    const notes = extraNotes.value.trim() ? `, ${extraNotes.value.trim()}` : '';
    return `${name}${desc}${notes}`;
}

function buildPrompt() {
    const base = `${stylePrefix()}, ${characterPrefix()}`;
    if (activeMode.value === 'portrait') {
        return `${base}, close-up head-and-shoulders portrait, centered composition, soft studio lighting, transparent or simple background, highly detailed face`;
    }
    if (activeMode.value === 'fullbody') {
        return `${base}, full-body turnaround front view, straight A-pose, arms slightly out, feet shoulder-width apart, neutral expression, clean solid background, entire body visible head to feet`;
    }
    if (activeMode.value === 'poses') return null; // batched
    if (activeMode.value === 'expressions') return null; // batched
    if (activeMode.value === 'tiles') {
        const size = tileSize.value.split('x')[0];
        return `${base}, isometric game tile sprite, top-down view, ${size}×${size} tile format, seamless edges, vibrant readable silhouette, transparent background, centered composition, pixel-clean detail`;
    }
    if (activeMode.value === 'assets3d') {
        const kind = {
            glb:          'full 3D character model reference sheet, front + side + back views',
            pose:         'reference pose sheet with T-pose, A-pose and rig-ready gestures',
            material:     'PBR material reference sheet, closeups of skin, fabric, metal, fur textures',
            turntable:    'turntable angle sheet, 8 evenly rotated views around the character',
            reference:    'multi-angle reference model sheet, front, side, back, 3/4 perspective views'
        }[asset3dType.value];
        return `${base}, ${kind}, clean solid background, technical illustration style, uniform lighting, professional 3D asset reference document`;
    }
    return base;
}

// ── Generation batch ──
const isGenerating = ref(false);
const sessionResults = ref([]);
const sessionStart = ref(null);

const expectedCount = computed(() => {
    if (['poses', 'expressions'].includes(activeMode.value)) return selectedVariants.value.size || 1;
    if (activeMode.value === 'tiles') return 1;
    return 1;
});

const canGenerate = computed(() => {
    if (!character.value.name.trim() && !character.value.description.trim()) return false;
    if (['poses', 'expressions'].includes(activeMode.value) && selectedVariants.value.size === 0) return false;
    return true;
});

const generateButtonLabel = computed(() => {
    if (['poses', 'expressions'].includes(activeMode.value)) {
        return `Generate ${selectedVariants.value.size} ${activeMode.value === 'poses' ? 'Pose' : 'Expression'}${selectedVariants.value.size === 1 ? '' : 's'}`;
    }
    if (activeMode.value === 'tiles') return 'Generate Tile';
    if (activeMode.value === 'assets3d') return 'Generate 3D Reference';
    return `Generate ${activeMode.value === 'portrait' ? 'Portrait' : 'Full Body'}`;
});

async function generate() {
    if (!authStore.user?.tti_binding_model_name) {
        uiStore.addNotification('Configure a TTI model first.', 'warning');
        return;
    }
    isGenerating.value = true;
    // Snapshot existing IDs to detect new images by identity (see the same
    // rationale in InfographicWorkspace — `created_at`-vs-Date comparisons
    // are not reliable across server/client timezone or clock drift).
    const beforeIds = new Set((images.value || []).map(i => i.id));

    try {
        if (['poses', 'expressions'].includes(activeMode.value)) {
            const list = activeMode.value === 'poses' ? poses : expressions;
            const selected = list.filter(v => selectedVariants.value.has(v.id));
            for (const variant of selected) {
                const prompt = `${stylePrefix()}, ${characterPrefix()}, ${variant.prompt}, full body view if pose, centered composition, clean background`;
                await imageStore.generateImage({
                    prompt,
                    negative_prompt: 'blurry, deformed anatomy, inconsistent character, extra limbs, bad proportions, low quality',
                    model: authStore.user.tti_binding_model_name,
                    size: '1024x1024',
                    n: 1
                });
            }
        } else {
            const sizeValue = activeMode.value === 'tiles' ? tileSize.value : '1024x1024';
            await imageStore.generateImage({
                prompt: buildPrompt(),
                negative_prompt: 'blurry, deformed anatomy, inconsistent character, extra limbs, ugly, low resolution',
                model: authStore.user.tti_binding_model_name,
                size: sizeValue,
                n: 1
            });
        }
        await waitForBatch(expectedCount.value, beforeIds);
    } finally {
        isGenerating.value = false;
    }
}

function waitForBatch(count, beforeIds) {
    return new Promise(resolve => {
        let elapsed = 0;
        let resolved = false;
        // Merge any new images into the top of the sessionResults array as
        // soon as they land so a 9-pose batch appears incrementally instead
        // of holding a static skeleton until the last one finishes.
        const merge = (items) => {
            if (items.length === 0) return;
            const existingIds = new Set(sessionResults.value.map(i => i.id));
            const fresh = items.filter(i => !existingIds.has(i.id));
            if (fresh.length > 0) sessionResults.value = [...fresh, ...sessionResults.value];
        };
        const finish = (items) => {
            if (resolved) return;
            resolved = true;
            merge(items);
            if (items.length > 0) {
                uiStore.addNotification(`Generated ${items.length} asset${items.length === 1 ? '' : 's'}.`, 'success', 2000);
            }
            clearInterval(interval);
            resolve();
        };
        const interval = setInterval(() => {
            const fresh = (images.value || []).filter(i => !beforeIds.has(i.id));
            if (fresh.length >= count) { finish(fresh); return; }
            if (fresh.length > 0) merge(fresh);
            elapsed += 250;
            if (elapsed > 180000) finish(fresh); // safety timeout 3 min
        }, 250);
    });
}

// ── 3D prompt text ──
const threeDPromptText = computed(() => {
    if (!character.value.name) return '';
    return `# Character 3D Asset Brief — ${character.value.name}\n\nBase: ${characterPrefix()}\nStyle: ${character.value.style}\n\n## Reference Views\n- 8× turntable at 45° increments\n- T-pose and A-pose sheets\n- Close-up face, hands, and signature props\n- Material reference: skin, fabric, metal, fur\n\n## Render Guidelines\n- Style: ${character.value.style}\n- Lighting: neutral 3-point studio, soft key + fill\n- Background: transparent or neutral grey\n- Camera: orthographic for reference, perspective for hero shot\n\n## Target Formats\n- FBX / GLB with embedded textures\n- PBR: base color, roughness, metallic, normal, AO\n- LOD0 (full), LOD1 (½), LOD2 (¼)`;
});

function copy3dPrompt() {
    if (threeDPromptText.value) {
        navigator.clipboard.writeText(threeDPromptText.value);
        uiStore.addNotification('3D prompt copied.', 'success', 1500);
    }
}

// ── Tile sheet export ──
async function exportTileSheet() {
    if (sessionResults.value.length === 0) return;
    uiStore.addNotification('Opening each tile — use batch ZIP from gallery.', 'info', 2500);
}

// ── Actions ──
function openEditor(img) {
    if (!img?.id) return;
    emit('request-edit', img.id);
}

const isDownloadOpen = ref(false);
const isDownloading = ref(false);
const downloadTarget = ref(null);
const downloadFilename = computed(() => {
    const img = downloadTarget.value;
    if (!img) return 'character';
    const n = character.value.name ? character.value.name.replace(/\s+/g, '_') : 'character';
    return `${n}_${img.id.slice(0, 6)}`;
});

function download(img) { downloadTarget.value = img; isDownloadOpen.value = true; }

async function confirmDownload({ format, quality, filename }) {
    if (!downloadTarget.value) return;
    isDownloading.value = true;
    try {
        const res = await apiClient.get(`/api/image-studio/images/${downloadTarget.value.id}/file`, { responseType: 'blob' });
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