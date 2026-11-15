<template>
    <Teleport to="body">
        <Transition
            enter-active-class="transition-opacity duration-200"
            enter-from-class="opacity-0"
            enter-to-class="opacity-100"
            leave-active-class="transition-opacity duration-150"
            leave-from-class="opacity-100"
            leave-to-class="opacity-0"
        >
            <div
                v-if="visible"
                class="fixed inset-0 z-[9999] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
                @click.self="cancel"
            >
                <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-md w-full border border-gray-200 dark:border-gray-800 overflow-hidden flex flex-col max-h-[90vh]">
                    <!-- Header -->
                    <div class="px-5 py-4 border-b border-gray-200 dark:border-gray-800 flex items-start justify-between gap-3 shrink-0">
                        <div>
                            <h3 class="text-sm font-black uppercase tracking-widest text-gray-800 dark:text-gray-100">{{ title }}</h3>
                            <p class="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">{{ description }}</p>
                        </div>
                        <button @click="cancel" class="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors" title="Close">
                            <IconXMark class="w-4 h-4" />
                        </button>
                    </div>

                    <!-- Body -->
                    <div class="p-5 space-y-4 overflow-y-auto custom-scrollbar">
                        <!-- Format picker -->
                        <div>
                            <label class="text-[10px] font-black uppercase tracking-widest text-gray-400 dark:text-gray-500 block mb-2">Format</label>
                            <div class="grid grid-cols-4 gap-2">
                                <button
                                    v-for="fmt in formats"
                                    :key="fmt.id"
                                    @click="format = fmt.id"
                                    class="flex flex-col items-center p-2 rounded-xl border transition-all"
                                    :class="format === fmt.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 ring-1 ring-blue-500 shadow-sm' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-600'"
                                >
                                    <span class="text-xl mb-1 leading-none">{{ fmt.emoji }}</span>
                                    <span class="text-[10px] font-black uppercase">{{ fmt.label }}</span>
                                    <span class="text-[8px] opacity-60 leading-tight text-center mt-0.5">{{ fmt.hint }}</span>
                                </button>
                            </div>
                        </div>

                        <!-- Quality (lossy formats only) -->
                        <div v-if="isLossy" class="space-y-1">
                            <div class="flex justify-between items-center">
                                <label class="text-[10px] font-black uppercase tracking-widest text-gray-400 dark:text-gray-500">Quality</label>
                                <span class="font-mono text-[10px] font-bold text-blue-600 dark:text-blue-400">{{ Math.round(quality * 100) }}%</span>
                            </div>
                            <input type="range" min="0.4" max="1" step="0.01" v-model.number="quality" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500" />
                        </div>

                        <!-- Filename -->
                        <div class="space-y-1">
                            <label class="text-[10px] font-black uppercase tracking-widest text-gray-400 dark:text-gray-500 block">File Name</label>
                            <div class="flex items-center gap-1">
                                <input
                                    v-model="filename"
                                    type="text"
                                    class="input-field w-full text-xs"
                                    placeholder="image"
                                    @keydown.enter="confirm"
                                />
                                <span class="text-[10px] font-mono font-bold text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-1.5 rounded-lg shrink-0">.{{ extension }}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="px-5 py-3 border-t border-gray-200 dark:border-gray-800 flex items-center justify-end gap-2 shrink-0">
                        <button @click="cancel" class="btn btn-secondary" :disabled="saving">Cancel</button>
                        <button @click="confirm" class="btn btn-primary flex items-center gap-2" :disabled="saving">
                            <IconAnimateSpin v-if="saving" class="w-4 h-4 animate-spin" />
                            <IconSave v-else class="w-4 h-4" />
                            <span>{{ saving ? 'Downloading…' : 'Download' }}</span>
                        </button>
                    </div>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { EXPORT_FORMATS } from '../../services/imageExport';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
    visible: { type: Boolean, default: false },
    defaultFilename: { type: String, default: 'image' },
    defaultFormat: { type: String, default: 'png' },
    title: { type: String, default: 'Download Image' },
    description: { type: String, default: 'Choose an output format for this download.' },
    saving: { type: Boolean, default: false }
});

const emit = defineEmits(['confirm', 'close']);

const formats = EXPORT_FORMATS;
const format = ref(props.defaultFormat);
const quality = ref(0.92);
const filename = ref(props.defaultFilename);

const extension = computed(() => formats.find(f => f.id === format.value)?.extension || 'png');
const isLossy = computed(() => !!formats.find(f => f.id === format.value)?.lossy);

// Reset internal state whenever the modal is (re)opened so each download
// starts from a clean default (previous choices don't leak between images).
watch(() => props.visible, (v) => {
    if (v) {
        format.value = props.defaultFormat;
        quality.value = 0.92;
        filename.value = props.defaultFilename;
    }
});

function confirm() {
    if (props.saving) return;
    emit('confirm', {
        format: format.value,
        quality: quality.value,
        filename: filename.value
    });
}

function cancel() {
    if (props.saving) return;
    emit('close');
}
</script>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>