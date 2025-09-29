<!-- [UPDATE] frontend/webui/src/components/voices/VoiceEditor.vue -->
<script setup>
import { ref, watch, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useVoicesStore } from '../../stores/voices';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/plugins/regions'

import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconScissors from '../../assets/icons/IconScissors.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

const props = defineProps({
  voiceId: {
    type: String,
    required: true
  },
  voiceData: {
    type: Object,
    required: true
  }
});

const voicesStore = useVoicesStore();
const uiStore = useUiStore();
const authStore = useAuthStore(); 

const voice = computed(() => voicesStore.voices.find(v => v.id === props.voiceId));
const isLoadingAudio = ref(false);
const isSaving = ref(false);

// --- WaveSurfer State ---
const waveformId = `waveform-${props.voiceId}`;
const wavesurfer = ref(null);
const isWaveformReady = ref(false);
const isPlaying = ref(false);
const wsRegions = ref(null);

// --- Audio Data State ---
const referenceAudioUrl = ref(null);
const currentAudioBlob = ref(null);
const isPreviewingSynth = ref(false);

// --- Synthesis State ---
const testText = ref('Hello, this is a test of my voice.');
const isSynthesizing = ref(false);

const b64toUrl = (b64) => `data:audio/wav;base64,${b64}`;

const initWaveSurfer = async () => {
  await nextTick()

  if (wavesurfer.value) {
    destroyWaveSurfer()
  }

  const container = document.getElementById(waveformId)
  if (!container) {
    console.error('Waveform container not found:', waveformId)
    return
  }

  console.log('Initializing WaveSurfer v7 for container:', waveformId)

  try {
    wavesurfer.value = new WaveSurfer({
      container: container,
      waveColor: '#A8B5C7',
      progressColor: '#3B82F6',
      cursorColor: '#1E40AF',
      barWidth: 3,
      barRadius: 3,
      height: 128,
      normalize: true,
    })

    // Register Regions plugin (v7 syntax)
    wsRegions.value = wavesurfer.value.registerPlugin(
      RegionsPlugin.create({
        dragSelection: { color: 'rgba(0, 100, 255, 0.1)' }
      })
    )

    wavesurfer.value.on('ready', () => {
      console.log('WaveSurfer ready, duration:', wavesurfer.value.getDuration())
      isWaveformReady.value = true
    })

    wavesurfer.value.on('play', () => { isPlaying.value = true })
    wavesurfer.value.on('pause', () => { isPlaying.value = false })
    wavesurfer.value.on('finish', () => { isPlaying.value = false })

    await loadVoiceData()
  } catch (error) {
    console.error('Failed to initialize WaveSurfer:', error)
    uiStore.addNotification('Failed to initialize waveform viewer', 'error')
  }
}

const destroyWaveSurfer = () => {
    if (wavesurfer.value) {
        wavesurfer.value.destroy();
        wavesurfer.value = null;
        wsRegions.value = null;
    }
};

const loadVoiceData = async () => {
    if (!props.voiceId || !voice.value || !wavesurfer.value) {
        console.log('Cannot load voice data:', { voiceId: props.voiceId, hasVoice: !!voice.value, hasWavesurfer: !!wavesurfer.value });
        wavesurfer.value?.empty();
        return;
    }
    
    isLoadingAudio.value = true;
    isWaveformReady.value = false;
    isPreviewingSynth.value = false;
    
    try {
        const response = await fetch(`/api/voices-studio/${props.voiceId}/audio`, {
             headers: { 'Authorization': `Bearer ${authStore.token}` } 
        });
        
        if (!response.ok) throw new Error("Failed to fetch voice audio");

        const audioBlob = await response.blob();
        console.log('Audio blob loaded:', audioBlob.size, 'bytes');
        
        referenceAudioUrl.value = URL.createObjectURL(audioBlob);
        currentAudioBlob.value = audioBlob;
            
        await new Promise(r => setTimeout(r, 50));
        
        if (wavesurfer.value) {
            await wavesurfer.value.loadBlob(audioBlob);
            wavesurfer.value.on('ready', () => {
                console.log('✅ WaveSurfer waveform is ready');
                console.log('Duration:', wavesurfer.value.getDuration());
            });
            console.log('Audio loaded into WaveSurfer');
        }
        
        if (wsRegions.value) {
             wsRegions.value.clearRegions();
        }
        
    } catch (e) {
        console.error("Audio Load Error:", e);
        uiStore.addNotification('Failed to load audio file for waveform.', 'error');
    } finally {
        isLoadingAudio.value = false;
    }
};

onMounted(() => {
    console.log('VoiceEditor mounted');
    initWaveSurfer();
});

onBeforeUnmount(() => {
    console.log('VoiceEditor unmounting');
    destroyWaveSurfer();
});

// Watch for external voice ID change and reload data
watch(() => props.voiceId, async () => {
    console.log('Voice ID changed to:', props.voiceId);
    await initWaveSurfer();
});

function playPause() {
    if (wavesurfer.value?.isPlaying()) {
        wavesurfer.value.pause();
    } else if (isWaveformReady.value) {
        wavesurfer.value.play();
    } else if (referenceAudioUrl.value && !isLoadingAudio.value) {
         const audio = new Audio(referenceAudioUrl.value);
         audio.play();
    }
}

async function handleTrim() {
    const regions = wsRegions.value?.getRegions();
    if (!regions || regions.length === 0) {
        uiStore.addNotification("Please create a selection on the waveform to trim.", "warning");
        return;
    }
    const region = regions[0];
    
    if (!currentAudioBlob.value) {
        uiStore.addNotification("No audio data available for trimming.", "warning");
        return;
    }

    isSaving.value = true;
    try {
        const audioBase64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                const b64 = reader.result.split(',')[1];
                resolve(b64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(currentAudioBlob.value);
        });

        const payload = {
            audio_b64: audioBase64,
            pitch: props.voiceData.pitch, speed: props.voiceData.speed, gain: props.voiceData.gain,
            reverb_params: { delay: props.voiceData.reverb_delay, attenuation: props.voiceData.reverb_attenuation },
            trim_start: region.start,
            trim_end: region.end
        };

        const result = await voicesStore.applyEffects(payload);

        if (result && result.audio_b64) {
            const blob = await (await fetch(b64toUrl(result.audio_b64))).blob();
            currentAudioBlob.value = blob;
            wavesurfer.value?.loadBlob(blob);
            isPreviewingSynth.value = true;
        }

        wsRegions.value?.clearRegions();
        uiStore.addNotification("Trim applied to waveform. Use 'Set as Reference' to save.", "info");

    } catch(e) {
        console.error("Trim/Effects error:", e);
        uiStore.addNotification("Failed to apply trim. Ensure pydub is installed on the server.", "error");
    } finally {
        isSaving.value = false;
    }
}

async function handleSynthesize() {
    if (!testText.value.trim()) return;
    isSynthesizing.value = true;
    try {
        const payload = { 
            text: testText.value, 
            voice_id: props.voiceId,
            language: props.voiceData.language, 
            pitch: props.voiceData.pitch,
            speed: props.voiceData.speed,
            gain: props.voiceData.gain,
            reverb_params: { delay: props.voiceData.reverb_delay, attenuation: props.voiceData.reverb_attenuation }
        };
        const result = await voicesStore.testVoice(payload);
        if (result && result.audio_b64) {
            const blob = await (await fetch(b64toUrl(result.audio_b64))).blob();
            currentAudioBlob.value = blob;
            wavesurfer.value?.loadBlob(blob);
            isPreviewingSynth.value = true;
        }
    } finally {
        isSynthesizing.value = false;
    }
}

async function handleSetAsReference() {
    if (!currentAudioBlob.value) {
        uiStore.addNotification("No preview audio to set as reference.", "warning");
        return;
    }
    isSaving.value = true;
    try {
        await voicesStore.replaceVoiceAudio(props.voiceId, currentAudioBlob.value);
        isPreviewingSynth.value = false;
        await loadVoiceData();
        uiStore.addNotification("New audio successfully set as voice reference.", "success");
    } finally {
        isSaving.value = false;
    }
}

function handleSave() { voicesStore.updateVoice(props.voiceId, props.voiceData); }
function handleDuplicate() { voicesStore.duplicateVoice(props.voiceId); }
</script>

<template>
  <div class="p-6 h-full overflow-y-auto custom-scrollbar">
    <div v-if="isLoadingAudio" class="flex items-center justify-center h-full">
      <IconAnimateSpin class="w-8 h-8 text-blue-500" />
    </div>
    <div v-else class="space-y-6">
      <h2 class="text-2xl font-bold">Generate & Test Voice</h2>

      <!-- Editor Section -->
      <div class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-4">
        <h3 class="font-semibold">Audio Waveform ({{ voice?.alias }})</h3>
        
        <div class="relative">
            <!-- WaveSurfer Container with explicit sizing -->
            <div :id="waveformId" class="w-full bg-gray-200 dark:bg-gray-800 rounded-md" style="min-height: 128px; height: 128px;"></div>
            
            <!-- Play Button Overlay -->
            <button @click="playPause" 
                    class="absolute top-1/2 left-4 transform -translate-y-1/2 p-3 rounded-full bg-white dark:bg-gray-900 shadow-lg text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors z-10"
                    :disabled="!isWaveformReady && !referenceAudioUrl"
                    :title="isPlaying ? 'Pause' : 'Play'">
                <IconStopCircle v-if="isPlaying" class="w-6 h-6" />
                <IconPlayCircle v-else class="w-6 h-6" />
            </button>
        </div>
        
        <div class="flex items-center gap-3">
            <button @click="wsRegions?.enableDragSelection({ color: 'rgba(0, 100, 255, 0.1)' })" class="btn btn-secondary btn-sm" title="Enable region selection for trimming" :disabled="!isWaveformReady">
                <IconScissors class="w-4 h-4 mr-1" /> Add Trim Region
            </button>
             <button @click="handleTrim" class="btn btn-secondary btn-sm" title="Apply trim" :disabled="isSaving || !isWaveformReady">
                <IconScissors class="w-4 h-4 mr-1" /> Trim
            </button>
            
            <div class="flex-grow"></div>
            <button v-if="isPreviewingSynth" @click="handleSetAsReference" class="btn btn-warning btn-sm" :disabled="isSaving" title="Set the current audio as the new reference for this voice">
                 <IconCheckCircle class="w-4 h-4 mr-1" /> Set as Reference
            </button>
        </div>
      </div>
      
      <!-- Synthesis Test -->
      <div class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-4">
        <h3 class="font-semibold">Synthesize Test</h3>
        <textarea v-model="testText" class="input-field w-full" rows="3" placeholder="Enter text to synthesize with this voice..."></textarea>
        <div class="flex justify-end">
            <button @click="handleSynthesize" class="btn btn-secondary" :disabled="isSynthesizing">
                <IconAnimateSpin v-if="isSynthesizing" class="w-5 h-5 mr-2" />
                {{ isSynthesizing ? 'Synthesizing...' : 'Synthesize & Preview' }}
            </button>
        </div>
      </div>
      
      <!-- Footer Actions -->
      <div class="flex justify-end gap-3 pt-4 border-t dark:border-gray-700">
        <button @click="handleSave" class="btn btn-primary" :disabled="isSaving">
          <IconSave class="w-4 h-4 mr-2" />
          Save Changes
        </button>
        <button @click="handleDuplicate" class="btn btn-secondary" :disabled="isSaving">
            <IconPlus class="w-4 h-4 mr-2"/>
            Duplicate Voice
        </button>
      </div>

    </div>
  </div>
</template>