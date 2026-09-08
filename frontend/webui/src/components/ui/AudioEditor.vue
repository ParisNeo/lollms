<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { useVoicesStore } from '../../stores/voices';
import { useUiStore } from '../../stores/ui';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';

// Icons
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconScissors from '../../assets/icons/IconScissors.vue';

const props = defineProps({
    voice: { type: Object, default: null },
    audioUrl: { type: String, default: null }
});

const emit = defineEmits(['trimmed', 'updated', 'close']);

const voicesStore = useVoicesStore();
const uiStore = useUiStore();

const waveformRef = ref(null);
let wavesurfer = null;
let regions = null;

const isPlaying = ref(false);
const duration = ref(0);
const currentTime = ref(0);

const trimRegion = ref({ start: 0, end: 0 });

async function loadAndRenderAudio() {
    if (!waveformRef.value) return;

    if (wavesurfer) {
        wavesurfer.destroy();
        wavesurfer = null;
    }

    let urlToLoad = props.audioUrl;
    if (!urlToLoad && props.voice?.id) {
        urlToLoad = await voicesStore.fetchVoiceAudio(props.voice.id);
    }

    if (!urlToLoad) return;

    wavesurfer = WaveSurfer.create({
        container: waveformRef.value,
        waveColor: '#94a3b8',
        progressColor: '#3b82f6',
        cursorColor: '#2563eb',
        barWidth: 2,
        barGap: 2,
        barRadius: 2,
        height: 80,
        responsive: true
    });

    regions = wavesurfer.registerPlugin(RegionsPlugin.create());

    wavesurfer.load(urlToLoad);

    wavesurfer.on('ready', () => {
        duration.value = wavesurfer.getDuration();
        trimRegion.value.start = 0;
        trimRegion.value.end = duration.value;

        regions.clearRegions();
        regions.addRegion({
            start: 0,
            end: duration.value,
            color: 'rgba(59, 130, 246, 0.2)',
            drag: true,
            resize: true
        });
    });

    wavesurfer.on('audioprocess', () => {
        currentTime.value = wavesurfer.getCurrentTime();
    });

    wavesurfer.on('finish', () => {
        isPlaying.value = false;
    });

    regions.on('region-updated', (region) => {
        trimRegion.value.start = region.start;
        trimRegion.value.end = region.end;
    });
}

onMounted(loadAndRenderAudio);

onUnmounted(() => {
    if (wavesurfer) {
        wavesurfer.destroy();
    }
});

watch(() => props.audioUrl, loadAndRenderAudio);
watch(() => props.voice?.id, loadAndRenderAudio);

function togglePlay() {
    if (!wavesurfer) return;
    wavesurfer.playPause();
    isPlaying.value = wavesurfer.isPlaying();
}

function handleEmitTrim() {
    emit('trimmed', {
        start: trimRegion.value.start,
        end: trimRegion.value.end
    });
}
</script>

<template>
    <div class="space-y-3">
        <div class="flex justify-between items-center text-xs text-gray-500 font-mono">
            <span>Audio Waveform Inspector</span>
            <span>{{ currentTime.toFixed(1) }}s / {{ duration.toFixed(1) }}s</span>
        </div>

        <div ref="waveformRef" class="w-full bg-white dark:bg-gray-800 rounded-xl p-2 border dark:border-gray-700"></div>

        <div class="flex items-center justify-between pt-1">
            <button type="button" @click="togglePlay" class="btn btn-primary btn-sm flex items-center gap-1.5">
                <IconStopCircle v-if="isPlaying" class="w-4 h-4" />
                <IconPlayCircle v-else class="w-4 h-4" />
                <span>{{ isPlaying ? 'Pause' : 'Play' }}</span>
            </button>

            <button type="button" @click="handleEmitTrim" class="btn btn-secondary btn-sm flex items-center gap-1.5">
                <IconScissors class="w-3.5 h-3.5 text-blue-500" />
                <span>Apply Selection Trim</span>
            </button>
        </div>
    </div>
</template>