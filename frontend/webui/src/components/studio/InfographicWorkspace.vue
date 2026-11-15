<template>
    <div class="h-full flex flex-col lg:flex-row min-h-0 overflow-hidden">
        <!-- ── LEFT: COMPOSER ── -->
        <aside class="w-full lg:w-[440px] shrink-0 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col overflow-hidden">
            <div class="grow overflow-y-auto custom-scrollbar p-4 space-y-4">

                <!-- Template picker -->
                <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Layout Template</label>
                    <div class="grid grid-cols-2 gap-2">
                        <button
                            v-for="t in templates"
                            :key="t.id"
                            @click="templateId = t.id"
                            class="p-2.5 rounded-xl border text-left transition-all"
                            :class="templateId === t.id
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 ring-1 ring-blue-500'
                                : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-600'"
                        >
                            <div class="text-xl mb-1 leading-none">{{ t.emoji }}</div>
                            <div class="text-[10px] font-black uppercase tracking-tight">{{ t.label }}</div>
                            <div class="text-[9px] opacity-70 leading-tight mt-0.5">{{ t.hint }}</div>
                        </button>
                    </div>
                </div>

                <!-- Content fields -->
                <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Content</label>
                    <input v-model="title" type="text" class="input-field !text-sm font-bold w-full" placeholder="Headline (e.g. 'Q4 Launch Event')" />
                    <input v-model="subtitle" type="text" class="input-field !text-xs w-full" placeholder="Subtitle (optional)" />
                    <textarea v-model="body" rows="3" class="input-field !text-xs w-full resize-none" placeholder="Body / supporting text (optional)"></textarea>
                    <input v-model="ctaText" type="text" class="input-field !text-xs w-full" placeholder="Call to action (e.g. 'Register Now')" />
                </div>

                <!-- Stat rows (data infographics only) -->
                <div v-if="needsStats" class="space-y-2 p-3 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700">
                    <div class="flex items-center justify-between">
                        <label class="text-[10px] font-black text-gray-500 uppercase tracking-widest">Data Points</label>
                        <button @click="addStat" class="p-1 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"><IconPlus class="w-3.5 h-3.5" /></button>
                    </div>
                    <div v-for="(s, i) in stats" :key="i" class="flex items-center gap-2">
                        <input v-model="s.value" type="text" class="input-field !text-xs !py-1 w-16 font-mono font-bold" placeholder="42%" />
                        <input v-model="s.label" type="text" class="input-field !text-xs !py-1 grow" placeholder="Metric name" />
                        <button @click="stats.splice(i, 1)" class="p-1 text-red-400 hover:text-red-500"><IconXMark class="w-3 h-3" /></button>
                    </div>
                </div>

                <!-- Color scheme -->
                <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Brand Accent Color</label>
                    <div class="flex items-center gap-2">
                        <div v-for="c in colorSchemes" :key="c.value"
                            @click="brandColor = c.value"
                            class="w-8 h-8 rounded-lg cursor-pointer border-2 transition-transform hover:scale-110"
                            :class="brandColor === c.value ? 'border-white ring-2 ring-blue-500 scale-110' : 'border-gray-200 dark:border-gray-700'"
                            :style="{ backgroundColor: c.value }"
                            :title="c.label"
                        ></div>
                        <input type="color" v-model="brandColor" class="w-8 h-8 rounded-lg cursor-pointer border border-gray-200 dark:border-gray-700" title="Custom color" />
                    </div>
                </div>

                <!-- Output size -->
                <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Output Canvas</label>
                    <select v-model="outputSize" class="input-field !text-xs w-full">
                        <optgroup v-for="g in outputSizeGroups" :key="g.label" :label="g.label">
                            <option v-for="s in g.items" :key="s.value" :value="s.value">{{ s.label }}</option>
                        </optgroup>
                    </select>
                </div>

                <!-- Typography strictness — directly controls the prompt contract -->
                <div class="space-y-1.5">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Typography Strictness</label>
                    <div class="flex items-center gap-0.5 bg-gray-100 dark:bg-gray-800 p-0.5 rounded-lg">
                        <button
                            v-for="o in typographyModes"
                            :key="o.id"
                            @click="typographyMode = o.id"
                            class="flex-1 py-1.5 text-[9px] font-black uppercase tracking-wider rounded-md transition-all"
                            :class="typographyMode === o.id ? 'bg-white dark:bg-gray-700 shadow-sm text-blue-600 dark:text-blue-400' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                            :title="o.hint"
                        >{{ o.label }}</button>
                    </div>
                    <p class="text-[9px] text-gray-500 leading-tight">{{ currentTypographyHint }}</p>
                </div>

                <!-- Extra instructions -->
                <div class="space-y-1.5">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Extra Style Notes</label>
                    <textarea v-model="extraInstructions" rows="2" class="input-field !text-xs w-full resize-none" placeholder="e.g. 'add a subtle gradient background', 'use geometric shapes'"></textarea>
                </div>

                <!-- Variations -->
                <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Variations</label>
                    <div class="flex items-center gap-1">
                        <button v-for="n in [1, 2, 4]" :key="n" @click="variations = n"
                            class="flex-1 py-1.5 text-xs font-black rounded-xl border transition-all"
                            :class="variations === n ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600' : 'border-gray-200 dark:border-gray-700 text-gray-500'"
                        >{{ n }}</button>
                    </div>
                </div>
            </div>

            <!-- Generate footer -->
            <div class="p-3 border-t border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 shrink-0">
                <button @click="generate" :disabled="isGenerating || !canGenerate" class="btn btn-primary w-full py-3 text-xs font-black uppercase tracking-widest flex items-center justify-center gap-2 shadow-xl shadow-blue-500/20">
                    <IconAnimateSpin v-if="isGenerating" class="w-4 h-4 animate-spin" />
                    <IconSparkles v-else class="w-4 h-4" />
                    <span>{{ isGenerating ? 'Generating…' : 'Generate ' + variations + ' Variation' + (variations > 1 ? 's' : '') }}</span>
                </button>
                <p v-if="!authStore.user?.tti_binding_model_name" class="text-[9px] text-red-500 font-bold text-center mt-1.5">⚠ Configure a TTI model in Settings first</p>
            </div>
        </aside>

        <!-- ── RIGHT: RESULTS ── -->
        <section class="grow flex flex-col min-h-0 overflow-hidden bg-gray-50 dark:bg-gray-950">
            <div class="shrink-0 px-4 py-2.5 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between bg-white/70 dark:bg-gray-900/70 backdrop-blur-md">
                <div>
                    <h2 class="text-xs font-black uppercase tracking-widest text-gray-700 dark:text-gray-200">Generated Posters</h2>
                    <p class="text-[10px] text-gray-500 dark:text-gray-400">{{ results.length }} output{{ results.length === 1 ? '' : 's' }} this session</p>
                </div>
                <button v-if="results.length" @click="results = []" class="text-[10px] font-bold text-red-500 uppercase hover:underline">Clear</button>
            </div>

            <div class="grow overflow-y-auto custom-scrollbar p-4">
                <!-- Empty state -->
                <div v-if="results.length === 0 && !isGenerating" class="h-full flex flex-col items-center justify-center text-gray-400 space-y-2">
                    <span class="text-5xl opacity-20">📊</span>
                    <p class="text-sm font-black uppercase tracking-widest text-gray-500">Pick a template to start</p>
                    <p class="text-xs text-center max-w-sm">Fill in your content, choose a size, and click Generate to create infographics, event posters, announcement cards, and more.</p>
                </div>

                <!-- Loading skeleton (only when nothing has landed yet — once the
                     first result arrives we switch to the results grid so the
                     user sees images appear incrementally) -->
                <div v-if="isGenerating && results.length === 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    <div v-for="i in variations" :key="'skel-'+i" class="aspect-square rounded-2xl bg-white dark:bg-gray-900 border-2 border-blue-200 dark:border-blue-900/50 flex flex-col items-center justify-center animate-pulse">
                        <IconAnimateSpin class="w-10 h-10 text-blue-500 animate-spin mb-3" />
                        <p class="text-[10px] font-black uppercase text-blue-500">Rendering…</p>
                    </div>
                </div>

                <!-- Result grid -->
                <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    <div v-for="img in results" :key="img.id" class="group relative rounded-2xl overflow-hidden border-2 border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-md hover:shadow-xl transition-all">
                        <AuthenticatedImage :src="`/api/image-studio/images/${img.id}/thumbnail?size=512`" class="w-full aspect-square object-contain bg-white" />
                        <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 to-transparent p-3 opacity-0 group-hover:opacity-100 transition-opacity">
                            <p class="text-white text-[10px] line-clamp-2 mb-2 font-serif italic">"{{ img.prompt }}"</p>
                            <div class="flex items-center gap-1">
                                <button @click="openEditor(img)" class="p-1.5 bg-white/15 hover:bg-purple-500 rounded-lg text-white backdrop-blur" title="Open in Layer Editor"><IconPencil class="w-3.5 h-3.5" /></button>
                                <button @click="download(img)" class="p-1.5 bg-white/15 hover:bg-emerald-500 rounded-lg text-white backdrop-blur" title="Download"><IconArrowDownTray class="w-3.5 h-3.5" /></button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <ImageFormatExportModal
            :visible="isDownloadOpen" :default-filename="downloadFilename" :saving="isDownloading"
            title="Download Poster" @confirm="confirmDownload" @close="isDownloadOpen = false"
        />
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useImageStore } from '../../stores/images';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { useAuthStore } from '../../stores/auth';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import ImageFormatExportModal from '../modals/ImageFormatExportModal.vue';
import { exportImageBlobAsFormat } from '../../services/imageExport';
import apiClient from '../../services/api';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

const emit = defineEmits(['request-edit']);
const imageStore = useImageStore();
const uiStore = useUiStore();
const dataStore = useDataStore();
const authStore = useAuthStore();
const { images } = storeToRefs(imageStore);

// ── Template catalogue ──
const templates = [
    {
        id: 'announcement', label: 'Announcement', emoji: '📣', hint: 'Bold social card',
        prompt: 'High-quality modern announcement poster, rigid editorial layout on a rectangular page. Layout grid: TOP band ~18% reserved for a small brand badge anchored left; MIDDLE band ~52% holds a large centred headline block spanning 2 to 3 lines; BOTTOM band ~30% holds one line of subtext plus a single rounded pill CTA button. Canvas: flat solid brand-tinted background with only a very subtle diagonal gradient wash — no pattern, no photograph, no illustration, no icons, no clipart inside the background. Composition: symmetric centre axis, generous whitespace, strict grid alignment, print-ready poster proportions.'
    },
    {
        id: 'data', label: 'Data Infographic', emoji: '📊', hint: 'Big stats focus',
        prompt: 'Data infographic poster, structural editorial layout with a strict 12-column grid. Layout grid: TOP 12% header banner with title and small category label; MIDDLE 55% horizontal row of three evenly sized stat cards; BOTTOM 33% footer with 1-2 lines of context plus source citation line. Each stat card: giant tabular-lining numeral occupying 10-15% of canvas height, one small uppercase metric label beneath, and one single thin-stroke flat-line icon per card (no photographs, no 3D renders). Background: off-white with a subtle dot-grid; brand accent applied only to numerals and thin rule lines. Composition: uniform card padding, aligned baselines, print-quality vector precision.'
    },
    {
        id: 'event', label: 'Event Poster', emoji: '🎨', hint: 'Date & location',
        prompt: 'Vibrant event poster, editorial layout. Layout grid: UPPER 55% reserved for a bold flat-vector hero illustration band (deliberately simplified, 3-5 colours); MIDDLE 30% holds the title block plus one dedicated date and location text line; BOTTOM 15% holds a small sponsor row of tiny text logos. Composition: strong left-right balance, one dominant accent block anchoring the composition, generous outer margins, print-safe page proportions. All decorative elements must be geometric shapes and flat colour blocks — no photograph, no realistic render, no stock imagery.'
    },
    {
        id: 'product', label: 'Product Highlight', emoji: '💼', hint: 'Feature callouts',
        prompt: 'Premium product-highlight layout, editorial composition. Layout grid: CENTRE 50% holds a large hero product cut-out floating on a soft neutral background with a subtle soft drop shadow beneath it; a row of three feature callouts with single minimal thin-stroke icons arranged evenly around the hero — one above, two flanking; TOP small brand mark; BOTTOM CTA row. Palette: muted neutral greys and off-white with brand accent only on the CTA and feature icons. Composition: ample whitespace, strict vertical rhythm, sleek print-ready poster.'
    },
    {
        id: 'timeline', label: 'Timeline', emoji: '🕐', hint: 'Step-by-step',
        prompt: 'Horizontal timeline infographic, flat vector execution on a landscape page. A single horizontal rail runs through the vertical middle with five evenly spaced circular milestone nodes; each node has a small numbered badge, a compact two-word label above the rail, and one line of body copy below; a thin bottom footer with source line and small brand mark. Composition: strict grid spacing between nodes, uniform stroke weights, monochrome rail with brand accent only on the active node. No sketchy lines, no watercolour texture, no hands, no photographs.'
    },
    {
        id: 'quote', label: 'Quote Card', emoji: '💬', hint: 'Big typography',
        prompt: 'Elegant pull-quote card, minimalist editorial composition. Layout grid: TOP third holds one large decorative opening quotation-mark glyph; MIDDLE 50% holds a large centred pull-quote in a high-contrast display serif set on 3-4 balanced lines; BOTTOM 20% holds an attribution line in small-caps sans plus one tiny brand mark. Background: warm neutral paper tone with a very subtle paper grain (no illustration, no pattern, no photograph). Composition: letterpress-style wide margins, razor-sharp glyph edges, refined typographic hierarchy.'
    },
    {
        id: 'award', label: 'Award Certificate', emoji: '🏆', hint: 'Formal badge',
        prompt: 'Formal award certificate, symmetric landscape layout. An ornate baroque border of thin interlocking scrollwork frames the page; CENTRE-TOP holds a large title block in elegant mixed display-serif and small blackletter; CENTRE-MIDDLE holds the recipient name line and one award description line; BOTTOM holds a gold-foil seal above two signature rows; a thin rule separates the title from the recipient line. Background: cream parchment tone. Composition: dead-centre symmetric alignment, embossed-finish details, classic print typography. Only the picture-border is decorative — nothing else on the page may be ornamental.'
    },
    {
        id: 'carousel', label: 'Carousel Slide', emoji: '🎯', hint: 'LinkedIn page',
        prompt: 'Single LinkedIn carousel slide, editorial layout. Layout grid: TOP third holds a bold two-line title; MIDDLE holds a short paragraph of body copy plus one deliberately minimal flat-line illustration accent kept subordinate to the typography; BOTTOM row holds a page-number badge ("Page X of Y") on the right and a small brand mark on the left. Background: solid brand colour, or very subtle two-tone diagonal gradient. Composition: corporate-but-modern typography, strict grid, no photograph, no illustration heavy enough to compete with the title.'
    },
];

const colorSchemes = [
    { label: 'Corporate Blue', value: '#3B82F6' },
    { label: 'Creative Purple', value: '#8B5CF6' },
    { label: 'Fresh Green', value: '#10B981' },
    { label: 'Energetic Orange', value: '#F97316' },
    { label: 'Vibrant Pink', value: '#EC4899' },
    { label: 'Premium Dark', value: '#111827' },
    { label: 'Sunny Yellow', value: '#EAB308' },
    { label: 'Coral Red', value: '#EF4444' },
];

const outputSizeGroups = [
    {
        label: 'Social Media',
        items: [
            { label: 'Instagram Square (1:1)', value: '1024x1024' },
            { label: 'Instagram Story (9:16)', value: '768x1344' },
            { label: 'LinkedIn Landscape (16:9)', value: '1344x768' },
            { label: 'Twitter / X Header', value: '1536x640' },
            { label: 'Pinterest Tall (2:3)', value: '832x1216' },
        ]
    },
    {
        label: 'Print (ISO A-Series)',
        items: [
            { label: 'A5 Portrait', value: '896x1280' },
            { label: 'A4 Portrait', value: '1088x1536' },
            { label: 'A3 Portrait', value: '1248x1760' },
            { label: 'A4 Landscape', value: '1536x1088' },
            { label: 'A3 Landscape', value: '1760x1248' },
        ]
    },
    {
        label: 'US Standard Print',
        items: [
            { label: 'Letter Portrait', value: '1088x1408' },
            { label: 'Letter Landscape', value: '1408x1088' },
            { label: 'Legal Portrait', value: '896x1472' },
        ]
    }
];

// ── Content state ──
const templateId = ref('announcement');
const title = ref('');
const subtitle = ref('');
const body = ref('');
const ctaText = ref('');
const brandColor = ref('#3B82F6');
const extraInstructions = ref('');
const outputSize = ref('1024x1024');
const variations = ref(2);
const stats = ref([{ value: '', label: '' }]);

const needsStats = computed(() => templateId.value === 'data' || templateId.value === 'timeline');

// Typography strictness mode — mirrors how the prompt is authored below.
// `strict`  → render ONLY the exact provided strings, refuse invented text.
// `adaptive`→ interpretive typography allowed (when copy is decorative).
// `minimal` → emit no text at all (pure graphic layout with placeholder rules).
const typographyModes = [
    { id: 'strict',   label: 'Strict',   hint: 'Render ONLY the exact provided text. No extra words, no pseudo-text, no invented letters. Best for infographics with real copy.' },
    { id: 'adaptive', label: 'Adaptive', hint: 'Interpretive typography allowed — useful when the copy is decorative and may be paraphrased by the model.' },
    { id: 'minimal',  label: 'No Text',  hint: 'No text at all. Pure graphical layout with placeholder ruled lines only.' }
];
const typographyMode = ref('strict');
const currentTypographyHint = computed(() => typographyModes.find(m => m.id === typographyMode.value)?.hint || '');

// Expanded negative prompt — a curated 50+ token anti-hallucination gate that
// targets both the failure modes visible in generated posters: scrambled
// glyphs/pseudo-text, and random decorative icons/doodles that the model
// invents when not explicitly forbidden.
const NEGATIVE_PROMPT = [
    // Text hallucination & pseudo-text
    'gibberish text', 'pseudo-text', 'fake language', 'random letters',
    'scrambled characters', 'mangled glyphs', 'hieroglyphics', 'nonsense symbols',
    'misspelled text', 'incorrect spelling', 'doubled letters', 'extra words',
    'made-up words', 'invented slogans', 'hallucinated captions', 'wrong alphabet',
    'wrong script', 'blurred text', 'warped letters', 'overlapping text',
    'cut-off text', 'crooked baseline', 'ai text artifacts', 'unreadable typography',
    'decorative pseudo-lettering', 'ornamental letterforms', 'illegible script',
    // Graphic hallucination
    'random doodles', 'hallucinated icons', 'unrelated clipart', 'unrelated illustration',
    'cluttered decorations', 'extraneous graphics', 'chaotic layout', 'messy composition',
    'busy patterned background', 'photo collage', 'unrelated logos', 'unwanted charts',
    'unwanted icons', 'stray shapes', 'overlapping elements', 'stock-photo cliché',
    // Quality
    'blurry', 'low resolution', 'pixelated', 'jpeg artifacts', 'compression banding',
    'watermark', 'signature text', 'ugly', 'amateur', 'bad kerning',
    'bad leading', 'unbalanced composition', 'bad anatomy', 'deformed faces'
].join(', ');

const canGenerate = computed(() =>
    typographyMode.value === 'minimal' || !!(title.value.trim() || body.value.trim())
);

function addStat() { stats.value.push({ value: '', label: '' }); }

// ── Structured prompt builder ──
// A freeform comma-separated prompt is the single biggest cause of hallucinated
// text and random decorative icons in diffusion-generated posters. This builder
// emits a contract-style prompt with labelled sections:
//   1. ARTEFACT + LAYOUT      (per-template grid description)
//   2. EXACT TEXT CONTENT     (every string the model is allowed to render)
//   3. TYPOGRAPHY DIRECTIVE   (mode-dependent rendering rules)
//   4. COLOUR SYSTEM          (single source of colour truth)
//   5. QUALITY SIGNALS        (target render tier)
//   6. ART DIRECTION          (only explicit user overrides)
//   7. STRICT CONSTRAINTS     (final gate — must-follow contract)
// Sections separated by blank lines so text encoders register them as distinct
// clauses rather than one giant run-on.
function buildPrompt() {
    const tpl = templates.find(t => t.id === templateId.value) || templates[0];
    const sections = [];

    // 1. Artefact + layout
    sections.push(tpl.prompt);

    // 2. Exact text content — the ONLY strings the model is licensed to draw.
    if (typographyMode.value !== 'minimal') {
        const textBlocks = [];
        if (title.value.trim())    textBlocks.push(`HEADLINE — render exactly: "${title.value.trim()}"`);
        if (subtitle.value.trim()) textBlocks.push(`SUBTITLE — render exactly: "${subtitle.value.trim()}"`);
        if (body.value.trim())     textBlocks.push(`BODY COPY — render exactly: "${body.value.trim()}"`);
        if (ctaText.value.trim())  textBlocks.push(`CTA BUTTON — render exactly: "${ctaText.value.trim()}"`);
        if (needsStats.value) {
            stats.value
                .filter(s => s.value || s.label)
                .forEach((s, i) => textBlocks.push(
                    `STAT ${i + 1} — large value "${s.value || '—'}", small label "${s.label || 'metric'}"`
                ));
        }
        if (textBlocks.length) {
            sections.push(
                'EXACT TEXT CONTENT (render verbatim inside the specified layout regions; every character must match; do not add any other words):\n'
                + textBlocks.join('\n')
            );
        }
    }

    // 3. Typography directive (mode-dependent)
    if (typographyMode.value === 'strict') {
        sections.push('TYPOGRAPHY: professional print-grade type hierarchy; letter-perfect glyphs; correct kerning and even leading; crisp anti-aliased edges; high-DPI clarity; every character must match the provided strings verbatim using the standard Latin alphabet.');
    } else if (typographyMode.value === 'adaptive') {
        sections.push('TYPOGRAPHY: expressive editorial typography with clean hierarchy; crisp anti-aliased edges; high-DPI clarity; paraphrase gracefully if exact rendering is not possible.');
    } else {
        sections.push('TYPOGRAPHY: NO TEXT. Represent copy regions with ruled placeholder lines only — no letters, no numbers, no punctuation marks, no glyphs, no pseudo-text.');
    }

    // 4. Colour system
    sections.push(`COLOUR SYSTEM: dominant brand accent ${brandColor.value}; harmonised neutral palette; AAA text-on-background contrast; unified colour story across every element.`);

    // 5. Quality signals
    sections.push('QUALITY: award-winning graphic-design portfolio piece; Behance editorial standard; vector-line precision; deliberate use of whitespace; dignified minimalism; no overdraw, no texture noise, no lens filter simulation.');

    // 6. Additional art direction (only explicit user input)
    if (extraInstructions.value.trim()) {
        sections.push(`ADDITIONAL ART DIRECTION: ${extraInstructions.value.trim()}`);
    }

    // 7. Final strict gate
    if (typographyMode.value === 'strict') {
        sections.push('STRICT CONSTRAINTS — MUST FOLLOW: render ONLY the exact text strings listed above and nothing else; do not invent words; do not add pseudo-Latin; do not hallucinate glyphs; do not duplicate text; do not scramble letters; do not add watermarks, captions, signatures or unrelated slogans; every character must match the provided strings verbatim; if a string cannot be rendered exactly, render no text at all.');
    } else if (typographyMode.value === 'minimal') {
        sections.push('STRICT CONSTRAINTS — NO TEXT: absolutely no letters, numbers, punctuation marks, glyphs or pseudo-text anywhere on the canvas; only placeholder rules and graphical layout elements.');
    } else {
        sections.push('CONSTRAINTS: no gibberish pseudo-text; no scrambled characters; no unrelated slogans; no watermarks; no signature text; no hallucinated lettering; no invented decorative icons.');
    }

    return sections.join('\n\n');
}

// ── Generation ──
const isGenerating = ref(false);
const results = ref([]);

async function generate() {
    if (!authStore.user?.tti_binding_model_name) {
        uiStore.addNotification('Configure a TTI model in Settings before generating.', 'warning');
        return;
    }
    isGenerating.value = true;
    // Snapshot existing image IDs so newly generated images are detected by
    // IDENTITY, not by comparing `created_at` to a client-side timestamp.
    // The old `new Date(i.created_at) >= sessionStart` filter broke whenever
    // the server's serialized timestamp didn't line up with the client clock
    // (timezone offsets, clock drift) — the images were generated and already
    // visible in the gallery, but the workspace kept them filtered out and
    // spun the skeleton until the timeout.
    const beforeIds = new Set((images.value || []).map(i => i.id));
    try {
        const task = await imageStore.generateImage({
            prompt: buildPrompt(),
            negative_prompt: NEGATIVE_PROMPT,
            model: authStore.user.tti_binding_model_name,
            size: outputSize.value,
            n: variations.value
        });
        if (task?.id) {
            await waitForResults(variations.value, beforeIds);
        }
    } finally {
        isGenerating.value = false;
    }
}

function waitForResults(expectedCount, beforeIds) {
    return new Promise(resolve => {
        let elapsed = 0;
        let resolved = false;
        // Assign partial results to the grid as soon as any new image arrives
        // so the user never stares at a static skeleton while a second image
        // is still rendering.
        const commit = (items) => {
            if (items.length > 0) results.value = items.slice(0, 12);
        };
        const finish = (items) => {
            if (resolved) return;
            resolved = true;
            commit(items);
            clearInterval(interval);
            resolve();
        };
        const interval = setInterval(() => {
            const fresh = (images.value || []).filter(i => !beforeIds.has(i.id));
            if (fresh.length >= expectedCount) { finish(fresh); return; }
            if (fresh.length > 0) commit(fresh);
            elapsed += 250;
            if (elapsed > 180000) finish(fresh); // safety timeout 3 min
        }, 250);
    });
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
    if (!img) return 'poster';
    return (img.prompt || 'poster').trim().slice(0, 40).replace(/[^\w\s-]/g, '').replace(/\s+/g, '_') || 'poster';
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