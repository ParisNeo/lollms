<template>
  <div class="p-6 h-full overflow-y-auto custom-scrollbar">
    <div v-if="isLoadingAudio" class="flex items-center justify-center h-full">
      <IconAnimateSpin class="w-8 h-8 text-blue-500" />
    </div>
    <div v-else class="space-y-6">
      <form @submit.prevent="handleSaveChanges" class="space-y-6">
        <div class="flex items-start justify-between">
            <div>
                <h2 class="text-2xl font-bold">Voice Editor</h2>
                <p class="text-sm text-gray-500 dark:text-gray-400">Editing: {{ form.alias }}</p>
            </div>
            <div class="flex items-center gap-2">
                <button v-if="!isActiveVoice" type="button" @click="handleSetActive" class="btn btn-secondary btn-sm" :disabled="isSaving">Set as Active</button>
                <span v-else class="flex items-center gap-1.5 text-sm text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/50 px-3 py-1.5 rounded-full">
                    <IconCheckCircle class="w-5 h-5"/> Active
                </span>
                <button type="submit" class="btn btn-primary" :disabled="isSaving || !hasChanges">
                    <IconAnimateSpin v-if="isSaving" class="w-5 h-5 mr-2" />
                    {{ isSaving ? 'Saving...' : 'Save Changes' }}
                </button>
            </div>
        </div>

        <!-- Basic Info -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label for="alias" class="block text-sm font-medium">Alias</label><input type="text" id="alias" v-model="form.alias" class="input-field mt-1" required></div>
            <div><label for="language" class="block text-sm font-medium">Language</label><LanguageSelector v-model="form.language" id="language" :include-auto="false"/></div>
        </div>

        <!-- Audio Effects -->
        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-4">
            <h3 class="font-semibold">Audio Effects</h3>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                    <label class="block text-sm font-medium">Pitch: {{ form.pitch.toFixed(2) }}</label>
                    <input type="range" min="0.5" max="2.0" step="0.01" v-model.number="form.pitch" class="w-full">
                </div>
                <div>
                    <label class="block text-sm font-medium">Speed: {{ form.speed.toFixed(2) }}</label>
                    <input type="range" min="0.5" max="3.0" step="0.01" v-model.number="form.speed" class="w-full">
                </div>
                <div>
                    <label class="block text-sm font-medium">Gain (dB): {{ form.gain.toFixed(1) }}</label>
                    <input type="range" min="-20" max="20" step="0.1" v-model.number="form.gain" class="w-full">
                </div>
            </div>
            <div class="border-t dark:border-gray-600 pt-4">
                <details class="space-y-4">
                    <summary class="cursor-pointer text-sm font-medium">Reverb (Experimental)</summary>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                        <div>
                            <label class="block text-sm font-medium">Delay (ms): {{ form.reverb_params.delay }}</label>
                            <input type="range" min="0" max="200" step="1" v-model.number="form.reverb_params.delay" class="w-full">
                        </div>
                        <div>
                            <label class="block text-sm font-medium">Attenuation (dB): {{ form.reverb_params.attenuation.toFixed(1) }}</label>
                            <input type="range" min="0" max="20" step="0.1" v-model.number="form.reverb_params.attenuation" class="w-full">
                        </div>
                    </div>
                </details>
            </div>
            <div class="flex justify-end pt-4 border-t dark:border-gray-600">
                <button type="button" @click="handleApplyEffects" class="btn btn-secondary" :disabled="isApplyingEffects">
                    <IconAnimateSpin v-if="isApplyingEffects" class="w-4 h-4 mr-2" />
                    Apply Effects to Waveform
                </button>
            </div>
        </div>
      </form>
      
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
import { ref, watch, onMounted, computed } from 'vue';
import { useVoicesStore } from '../../stores/voices';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import AudioEditor from '../ui/AudioEditor.vue';
import LanguageSelector from '../ui/LanguageSelector.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';

const props = defineProps({
  voiceId: { type: String, required: true },
  voiceData: { type: Object, required: true }
});

const voicesStore = useVoicesStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const isLoadingAudio = ref(true);
const isSaving = ref(false);
const referenceAudioUrl = ref(null);
const currentAudioBlob = ref(null);
const originalAudioBlob = ref(null);
const isApplyingEffects = ref(false);
const isPreviewingSynth = ref(false);
const testText = ref('Hello, this is a test of my voice.');
const isSynthesizing = ref(false);

const form = ref({});
const pristineState = ref({});

const hasChanges = computed(() => JSON.stringify(form.value) !== JSON.stringify(pristineState.value));
const isActiveVoice = computed(() => authStore.user?.active_voice_id === props.voiceId);

const b64toUrl = (b64) => `data:audio/wav;base64,${b64}`;

const loadVoiceData = async () => {
    if (!props.voiceId) return;
    isLoadingAudio.value = true;
    isPreviewingSynth.value = false;
    try {
        referenceAudioUrl.value = await voicesStore.fetchVoiceAudio(props.voiceId);
        if (referenceAudioUrl.value) {
            const response = await fetch(referenceAudioUrl.value);
            const blob = await response.blob();
            currentAudioBlob.value = blob;
            originalAudioBlob.value = blob;
        }
    } finally {
        isLoadingAudio.value = false;
    }
};

watch(() => props.voiceData, (newData) => {
    if (newData) {
        const dataCopy = JSON.parse(JSON.stringify(newData));
        if (!dataCopy.reverb_params) {
            dataCopy.reverb_params = { delay: 0, attenuation: 0.0 };
        }
        form.value = dataCopy;
        pristineState.value = JSON.parse(JSON.stringify(dataCopy));
    }
}, { immediate: true, deep: true });


onMounted(loadVoiceData);

watch(() => props.voiceId, loadVoiceData);

async function handleTrim(trimData) {
    if (!currentAudioBlob.value) {
        uiStore.addNotification("No audio data available for trimming.", "warning");
        return;
    }

    isApplyingEffects.value = true;
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
            reverb_params: props.voiceData.reverb_params,
            trim_start: trimData.start,
            trim_end: trimData.end
        };

        const result = await voicesStore.applyEffects(payload);
        if (result && result.audio_b64) {
            const newUrl = b64toUrl(result.audio_b64);
            const blob = await (await fetch(newUrl)).blob();
            currentAudioBlob.value = blob;
            referenceAudioUrl.value = URL.createObjectURL(blob);
            isPreviewingSynth.value = true;
        }
        uiStore.addNotification("Trim applied. Use 'Set as Reference' to save.", "info");
    } catch(e) {
        console.error("Trim/Effects error:", e);
        uiStore.addNotification("Failed to apply trim.", "error");
    } finally {
        isApplyingEffects.value = false;
    }
}

async function handleApplyEffects() {
    if (!originalAudioBlob.value) {
        uiStore.addNotification("Original audio data not found.", "warning");
        return;
    }
    isApplyingEffects.value = true;
    try {
        const audioBase64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                const b64 = reader.result.split(',')[1];
                resolve(b64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(originalAudioBlob.value);
        });
        const payload = {
            audio_b64: audioBase64,
            pitch: form.value.pitch,
            speed: form.value.speed,
            gain: form.value.gain,
            reverb_params: form.value.reverb_params
        };
        const result = await voicesStore.applyEffects(payload);
        if (result && result.audio_b64) {
            const newUrl = b64toUrl(result.audio_b64);
            const blob = await (await fetch(newUrl)).blob();
            currentAudioBlob.value = blob;
            referenceAudioUrl.value = URL.createObjectURL(blob);
            isPreviewingSynth.value = true;
        }
        uiStore.addNotification("Effects applied. Use 'Set as Reference' to save.", "info");
    } catch(e) {
        console.error("Apply Effects error:", e);
        uiStore.addNotification("Failed to apply effects.", "error");
    } finally {
        isApplyingEffects.value = false;
    }
}

async function handleSynthesize() {
    if (!testText.value.trim()) return;
    isSynthesizing.value = true;
    try {
        const payload = { 
            text: testText.value, 
            voice_id: props.voiceId,
            language: form.value.language, 
            pitch: form.value.pitch,
            speed: form.value.speed,
            gain: form.value.gain,
            reverb_params: form.value.reverb_params
        };
        const result = await voicesStore.testVoice(payload);
        if (result && result.audio_b64) {
            const newUrl = b64toUrl(result.audio_b64);
            const blob = await (await fetch(newUrl)).blob();
            currentAudioBlob.value = blob;
            referenceAudioUrl.value = URL.createObjectURL(blob);
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

async function handleSaveChanges() {
    isSaving.value = true;
    try {
        const formData = new FormData();
        formData.append('alias', form.value.alias);
        formData.append('language', form.value.language);
        formData.append('pitch', form.value.pitch);
        formData.append('speed', form.value.speed);
        formData.append('gain', form.value.gain);
        formData.append('reverb_params_json', JSON.stringify(form.value.reverb_params));

        await voicesStore.updateVoice(props.voiceId, formData);
        pristineState.value = JSON.parse(JSON.stringify(form.value));
    } finally {
        isSaving.value = false;
    }
}

async function handleSetActive() {
    await voicesStore.setActiveVoice(props.voiceId);
}
</script>