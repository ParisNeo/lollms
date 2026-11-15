<template>
    <div class="h-full flex flex-col bg-gray-50 dark:bg-gray-950 overflow-hidden">
        <!-- ── HUB HEADER ── -->
        <header class="shrink-0 border-b border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl">
            <div class="flex items-center justify-between gap-3 px-3 sm:px-4 py-2.5">
                <!-- Left: title -->
                <div class="flex items-center gap-2 min-w-0">
                    <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-lg shrink-0">
                        <IconSparkles class="w-5 h-5 text-white" />
                    </div>
                    <div class="min-w-0">
                        <h1 class="text-xs font-black uppercase tracking-widest text-gray-800 dark:text-gray-100 truncate">Custom Studios</h1>
                        <p class="text-[10px] text-gray-500 dark:text-gray-400 truncate">Specialized workflow environments</p>
                    </div>
                </div>

                <!-- Center: mode tabs -->
                <div class="flex items-center gap-0.5 bg-gray-100 dark:bg-gray-800 p-1 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-x-auto no-scrollbar">
                    <button
                        v-for="m in modes"
                        :key="m.id"
                        @click="activeMode = m.id"
                        class="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-black uppercase tracking-wider rounded-xl transition-all whitespace-nowrap shrink-0"
                        :class="activeMode === m.id
                            ? 'bg-white dark:bg-gray-700 shadow-sm ring-1 ring-black/5 ' + modeColorClasses[m.color]
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'"
                    >
                        <span class="text-sm">{{ m.emoji }}</span>
                        <span>{{ m.label }}</span>
                    </button>
                </div>

                <!-- Right: exit -->
                <button @click="returnToImageStudio" class="btn btn-secondary btn-sm h-8 px-3 rounded-xl flex items-center gap-1.5 shrink-0" title="Return to Image Studio">
                    <IconArrowLeft class="w-3.5 h-3.5" />
                    <span class="hidden sm:inline text-xs font-bold">Exit</span>
                </button>
            </div>
        </header>

        <!-- ── ACTIVE WORKSPACE ── -->
        <!--
            The three workspaces are cached in <KeepAlive> so switching between
            them preserves your in-progress form data. The Layer Editor is
            intentionally NOT cached — it mounts fresh each time so the editors
            (undo history, layer stack, teleported toolbar) can't leak into
            other tabs.

            Workspaces emit `request-edit` with an image id when their "Edit"
            button is clicked. The hub switches to the Editor tab and passes
            that id down as `props.id`, where ImageEditorView picks it up via
            its `watch(props.id)` — same entry point the router normally uses.
        -->
        <main class="grow overflow-hidden">
            <template v-if="activeMode === 'editor'">
                <ImageEditorView :id="editorImageId" />
            </template>
            <template v-else>
                <KeepAlive>
                    <InfographicWorkspace v-if="activeMode === 'infographic'" @request-edit="openInEditor" />
                    <RestorationWorkspace v-else-if="activeMode === 'restoration'" @request-edit="openInEditor" />
                    <CharacterWorkspace v-else-if="activeMode === 'character'" @request-edit="openInEditor" />
                </KeepAlive>
            </template>
        </main>
    </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUiStore } from '../stores/ui';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import InfographicWorkspace from '../components/studio/InfographicWorkspace.vue';
import RestorationWorkspace from '../components/studio/RestorationWorkspace.vue';
import CharacterWorkspace from '../components/studio/CharacterWorkspace.vue';
import ImageEditorView from './ImageEditorView.vue';

const router = useRouter();
const uiStore = useUiStore();

const modes = [
    { id: 'infographic', label: 'Infographic Studio', emoji: '📊', color: 'blue' },
    { id: 'restoration', label: 'Restoration Lab',    emoji: '🔧', color: 'emerald' },
    { id: 'character',   label: 'Character Forge',    emoji: '🎭', color: 'purple' },
    { id: 'editor',      label: 'Layer Editor',       emoji: '✏️', color: 'amber' },
];

// Static class map so Tailwind's JIT compiler can see these literals (dynamic
// `text-${color}-600` strings get purged).
const modeColorClasses = {
    blue:    'text-blue-600 dark:text-blue-400',
    emerald: 'text-emerald-600 dark:text-emerald-400',
    purple:  'text-purple-600 dark:text-purple-400',
    amber:   'text-amber-600 dark:text-amber-400',
};

const activeMode = ref('infographic');
// `null` = blank canvas; an image id = load that image into the editor.
// Persists across tab switches so returning to the Editor tab reopens the
// last image you were working on.
const editorImageId = ref(null);

function openInEditor(imageId) {
    editorImageId.value = imageId || null;
    activeMode.value = 'editor';
}

// ImageEditorView sets the global page title to empty on mount (its toolbar
// teleports into the title slot, replacing it). When we leave the editor tab
// the title slot reverts to whatever `pageTitle` currently holds — which
// would be empty. Restore a sensible title whenever the editor is not active.
function syncHubPageTitle() {
    if (activeMode.value !== 'editor') {
        uiStore.setPageTitle({ title: 'Custom Studios', icon: null });
    }
}
watch(activeMode, syncHubPageTitle);

onMounted(() => {
    syncHubPageTitle();
});

function returnToImageStudio() {
    router.push('/image-studio');
}
</script>

<style scoped>
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>