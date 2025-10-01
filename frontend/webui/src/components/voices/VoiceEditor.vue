<template>
  <div class="p-6 h-full overflow-y-auto custom-scrollbar">
    <div v-if="isLoadingAudio" class="flex items-center justify-center h-full">
      <IconAnimateSpin class="w-8 h-8 text-blue-500" />
    </div>
    <div v-else class="space-y-6">
      <h2 class="text-2xl font-bold">Voice Editor: {{ voiceData.alias }}</h2>

      <!-- Editor Section -->
      <div class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-4">
        <h3 class="font-semibold">Audio Waveform</h3>
        
        <AudioEditor :audio-url="referenceAudioUrl" @trimmed="handleTrim" />
        
        <div class="flex items-center gap-3">
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
        <button @click="handleDuplicate" class="btn btn-secondary" :disabled="isSaving">
            <IconPlus class="w-4 h-4 mr-2"/>
            Duplicate Voice
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useVoicesStore } from '../../stores/voices';
import { useUiStore } from '../../stores/ui';
import AudioEditor from '../ui/AudioEditor.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';

const props = defineProps({
  voiceId: { type: String, required: true },
  voiceData: { type: Object, required: true }
});

const voicesStore = useVoicesStore();
const uiStore = useUiStore();

const isLoadingAudio = ref(true);
const isSaving = ref(false);
const referenceAudioUrl = ref(null);
const currentAudioBlob = ref(null);
const isPreviewingSynth = ref(false);
const testText = ref('Hello, this is a test of my voice.');
const isSynthesizing = ref(false);

const b64toUrl = (b64) => `data:audio/wav;base64,${b64}`;

const loadVoiceData = async () => {
    if (!props.voiceId) return;
    isLoadingAudio.value = true;
    isPreviewingSynth.value = false;
    try {
        referenceAudioUrl.value = await voicesStore.fetchVoiceAudio(props.voiceId);
        if (referenceAudioUrl.value) {
            const response = await fetch(referenceAudioUrl.value);
            currentAudioBlob.value = await response.blob();
        }
    } finally {
        isLoadingAudio.value = false;
    }
};

onMounted(loadVoiceData);

watch(() => props.voiceId, loadVoiceData);

async function handleTrim(trimData) {
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
            trim_start: trimData.start,
            trim_end: trimData.end
        };

        const result = await voicesStore.applyEffects(payload);
        if (result && result.audio_b64) {
            const newUrl = b64toUrl(result.audio_b64);
            const blob = await (await fetch(newUrl)).blob();
            currentAudioBlob.value = blob;
            referenceAudioUrl.value = URL.createObjectURL(blob); // This will trigger the AudioEditor to reload
            isPreviewingSynth.value = true;
        }
        uiStore.addNotification("Trim applied. Use 'Set as Reference' to save.", "info");
    } catch(e) {
        console.error("Trim/Effects error:", e);
        uiStore.addNotification("Failed to apply trim.", "error");
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
            const newUrl = b64toUrl(result.audio_b64);
            const blob = await (await fetch(newUrl)).blob();
            currentAudioBlob.value = blob;
            referenceAudioUrl.value = URL.createObjectURL(blob); // This will trigger the AudioEditor to reload
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

function handleDuplicate() { voicesStore.duplicateVoice(props.voiceId); }
</script>