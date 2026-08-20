<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue';
import { useVoicesStore } from '../../stores/voices';
import { useUiStore } from '../../stores/ui';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';

// Icons
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconScissors from '../../assets/icons/IconScissors.vue';

const props = defineProps({
    voice: { type: Object, required: true }
});

const emit = defineEmits(['updated', 'close']);

const voicesStore = useVoicesStore();
const uiStore = useUiStore();

const waveformRef = ref(null);
let wavesurfer = null;
let regions = null;

const isPlaying = ref(false);
const isProcessing = ref(false);
const isTesting = ref(false);
const testText = ref('Hello, this is a test of my customized voice on the LoLLMs platform.');
const testAudioUrl = ref(null);
const duration = ref(0);
const currentTime = ref(0);

// Parameters for non-destructive & destructive processing
const pitch = ref(props.voice.pitch || 1.0);
const speed = ref(props.voice.speed || 1.0);
const gain = ref(props.voice.gain || 0.0);
const reverbDelay = ref(props.voice.reverb_params?.delay || 0);
const reverbAttenuation = ref(props.voice.reverb_params?.attenuation || 0.0);

const trimRegion = ref({ start: 0, end: 0 });

onMounted(async () => {
    await initWaveSurfer();
});

onUnmounted(() => {
    if (wavesurfer) {
        wavesurfer.destroy();
    }
});

async function initWaveSurfer() {
    if (!waveformRef.value) return;

    if (wavesurfer) {
        wavesurfer.destroy();
    }

    const audioUrl = await voicesStore.fetchVoiceAudio(props.voice.id);
    if (!audioUrl) return;

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

    wavesurfer.load(audioUrl);

    wavesurfer.on('ready', () => {
        duration.value = wavesurfer.getDuration();
        trimRegion.value.end = duration.value;

        // Create default draggable trim region
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

function togglePlay() {
    if (!wavesurfer) return;
    wavesurfer.playPause();
    isPlaying.value = wavesurfer.isPlaying();
}

async function handleTestVoice() {
    if (!testText.value.trim()) return;
    isTesting.value = true;
    try {
        const response = await voicesStore.testVoice({
            voice_id: props.voice.id,
            text: testText.value,
            pitch: pitch.value,
            speed: speed.value,
            gain: gain.value,
            language: props.voice.language,
            reverb_params: {
                delay: reverbDelay.value,
                attenuation: reverbAttenuation.value
            }
        });

        if (response && response.audio_b64) {
            testAudioUrl.value = `data:audio/wav;base64,${response.audio_b64}`;
            uiStore.addNotification('Test audio generated successfully.', 'success');
        }
    } finally {
        isTesting.value = false;
    }
}

async function handleApplyAndSave() {
    isProcessing.value = true;
    try {
        const formData = new FormData();
        formData.append('alias', props.voice.alias);
        formData.append('language', props.voice.language);
        formData.append('pitch', pitch.value);
        formData.append('speed', speed.value);
        formData.append('gain', gain.value);
        formData.append('reverb_params_json', JSON.stringify({
            delay: reverbDelay.value,
            attenuation: reverbAttenuation.value
        }));

        await voicesStore.updateVoice(props.voice.id, formData);
        emit('updated');
        await initWaveSurfer();
    } finally {
        isProcessing.value = false;
    }
}
</script>

<template>
    <div class="p-6 bg-white dark:bg-gray-800 rounded-2xl border dark:border-gray-700 shadow-xl space-y-6">
        <!-- Header -->
        <div class="flex items-center justify-between border-b dark:border-gray-700 pb-4">
            <div>
                <h3 class="text-xl font-black text-gray-900 dark:text-gray-100 flex items-center gap-2">
                    <span>🎙️</span>
                    <span>{{ voice.alias }}</span>
                </h3>
                <p class="text-xs text-gray-500 font-mono mt-0.5">Language: {{ voice.language.toUpperCase() }}</p>
            </div>
            <button @click="$emit('close')" class="btn btn-secondary btn-sm">Close Editor</button>
        </div>

        <!-- Waveform Studio -->
        <div class="p-4 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-700/60 space-y-3">
            <div class="flex justify-between items-center text-xs text-gray-500 font-mono">
                <span>Waveform & Precision Trimmer</span>
                <span>{{ currentTime.toFixed(1) }}s / {{ duration.toFixed(1) }}s</span>
            </div>
            <div ref="waveformRef" class="w-full"></div>
            <div class="flex justify-center gap-2 pt-2">
                <button @click="togglePlay" class="btn btn-primary btn-sm px-6 flex items-center gap-2">
                    <IconStopCircle v-if="isPlaying" class="w-4 h-4" />
                    <IconPlayCircle v-else class="w-4 h-4" />
                    <span>{{ isPlaying ? 'Pause' : 'Play Reference' }}</span>
                </button>
            </div>
        </div>

        <!-- Audio Modifiers Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Pitch & Speed -->
            <div class="space-y-4 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700">
                <h4 class="text-xs font-black uppercase tracking-widest text-primary">Pitch & Cadence</h4>
                
                <div class="space-y-1">
                    <div class="flex justify-between text-xs font-bold">
                        <span>Pitch Shift</span>
                        <span class="font-mono text-blue-500">{{ pitch.toFixed(2) }}x</span>
                    </div>
                    <input type="range" v-model.number="pitch" min="0.5" max="1.5" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                </div>

                <div class="space-y-1">
                    <div class="flex justify-between text-xs font-bold">
                        <span>Speed (Cadence)</span>
                        <span class="font-mono text-blue-500">{{ speed.toFixed(2) }}x</span>
                    </div>
                    <input type="range" v-model.number="speed" min="0.5" max="2.0" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                </div>

                <div class="space-y-1">
                    <div class="flex justify-between text-xs font-bold">
                        <span>Gain (Volume Boost)</span>
                        <span class="font-mono text-blue-500">{{ gain > 0 ? `+${gain}` : gain }} dB</span>
                    </div>
                    <input type="range" v-model.number="gain" min="-10" max="10" step="0.5" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                </div>
            </div>

            <!-- Spatial Reverb -->
            <div class="space-y-4 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700">
                <h4 class="text-xs font-black uppercase tracking-widest text-primary">Acoustic & Reverb</h4>
                
                <div class="space-y-1">
                    <div class="flex justify-between text-xs font-bold">
                        <span>Reverb Delay</span>
                        <span class="font-mono text-blue-500">{{ reverbDelay }} ms</span>
                    </div>
                    <input type="range" v-model.number="reverbDelay" min="0" max="500" step="10" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                </div>

                <div class="space-y-1">
                    <div class="flex justify-between text-xs font-bold">
                        <span>Reverb Attenuation</span>
                        <span class="font-mono text-blue-500">{{ reverbAttenuation }} dB</span>
                    </div>
                    <input type="range" v-model.number="reverbAttenuation" min="0" max="20" step="1" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                </div>
            </div>
        </div>

        <!-- Interactive Voice Test Studio -->
        <div class="p-4 bg-blue-50/50 dark:bg-blue-900/10 rounded-xl border border-blue-100 dark:border-blue-900/30 space-y-3">
            <div class="flex justify-between items-center">
                <span class="text-xs font-black uppercase tracking-widest text-blue-600 dark:text-blue-400">Live Synthesis Test</span>
                <button @click="handleTestVoice" :disabled="isTesting" class="btn btn-primary btn-sm flex items-center gap-1.5">
                    <IconAnimateSpin v-if="isTesting" class="w-3.5 h-3.5 animate-spin" />
                    <IconSparkles v-else class="w-3.5 h-3.5" />
                    <span>Synthesize Sample</span>
                </button>
            </div>
            <textarea v-model="testText" rows="2" class="input-field w-full !text-xs" placeholder="Type text to synthesize with these acoustic parameters..."></textarea>
            
            <div v-if="testAudioUrl" class="mt-2 pt-2 border-t dark:border-gray-700">
                <audio :src="testAudioUrl" controls class="w-full h-8"></audio>
            </div>
        </div>

        <!-- Footer Actions -->
        <div class="flex justify-end gap-3 pt-2">
            <button @click="handleApplyAndSave" :disabled="isProcessing" class="btn btn-primary px-8">
                <IconAnimateSpin v-if="isProcessing" class="w-4 h-4 mr-2 animate-spin" />
                <span>Save Voice Parameters</span>
            </button>
        </div>
    </div>
</template>