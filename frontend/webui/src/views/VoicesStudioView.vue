<!-- [UPDATE] frontend/webui/src/views/VoicesStudioView.vue -->
<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useVoicesStore } from '../stores/voices';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import AudioEditor from '../components/ui/AudioEditor.vue'; // NEW
import IconMicrophone from '../assets/icons/IconMicrophone.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconPlayCircle from '../assets/icons/IconPlayCircle.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconCopy from '../assets/icons/IconCopy.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';

const voicesStore = useVoicesStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

const { voices, isLoading } = storeToRefs(voicesStore);
const { user } = storeToRefs(authStore);

// Form state for creating/editing a voice
const isFormVisible = ref(false);
const editingVoice = ref(null);
const form = ref({ alias: '', language: 'en', pitch: 1.0, speed: 1.0, gain: 0.0, reverb_delay: 0, reverb_attenuation: 0.0, file: null });
const isSubmitting = ref(false);

// State for the testing and editing section
const testText = ref({});
const generatedAudioData = ref({}); // { [voiceId]: { b64: string, url: string } }
const isTesting = ref({});
const effectsParams = ref({}); // { [voiceId]: { pitch, speed, ... } }
const isApplyingEffects = ref({});

const isEditMode = computed(() => !!editingVoice.value);

// Helper to convert base64 to a blob URL
function b64toUrl(b64Data) {
    const byteCharacters = atob(b64Data);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: 'audio/wav' });
    return URL.createObjectURL(blob);
}

// Form management
function showAddForm() { isFormVisible.value = true; editingVoice.value = null; form.value = { alias: '', language: 'en', pitch: 1.0, speed: 1.0, gain: 0.0, reverb_delay: 0, reverb_attenuation: 0.0, file: null }; }
function showEditForm(voice) { isFormVisible.value = true; editingVoice.value = { ...voice }; form.value = { alias: voice.alias, language: voice.language, pitch: voice.pitch, speed: voice.speed, gain: voice.gain, reverb_delay: voice.reverb_params?.delay || 0, reverb_attenuation: voice.reverb_params?.attenuation || 0.0, file: null }; }
function cancelForm() { isFormVisible.value = false; editingVoice.value = null; }
function handleFileChange(event) { form.value.file = event.target.files[0] || null; }

async function handleSubmit() {
    isSubmitting.value = true;
    try {
        const formData = new FormData();
        Object.entries(form.value).forEach(([key, value]) => {
            if (key !== 'file' && key !== 'reverb_delay' && key !== 'reverb_attenuation') formData.append(key, value);
        });
        const reverbParams = { delay: form.value.reverb_delay, attenuation: form.value.reverb_attenuation };
        formData.append('reverb_params_json', JSON.stringify(reverbParams));
        if (form.value.file) formData.append('file', form.value.file);

        if (isEditMode.value) {
            if (!form.value.file) { uiStore.addNotification('To apply new audio effects, you must re-upload the original audio file.', 'warning'); isSubmitting.value = false; return; }
            await voicesStore.updateVoice(editingVoice.value.id, formData);
        } else {
            if (!form.value.file) { uiStore.addNotification('An audio file is required to create a new voice.', 'warning'); isSubmitting.value = false; return; }
            await voicesStore.uploadVoice(formData);
        }
        cancelForm();
    } finally {
        isSubmitting.value = false;
    }
}

// Voice card actions
async function handleSetActive(voiceId) { await voicesStore.setActiveVoice(voiceId); }
async function handleDelete(voice) { const confirmed = await uiStore.showConfirmation({ title: `Delete Voice '${voice.alias}'?`, message: 'This action is permanent and cannot be undone.', confirmText: 'Delete' }); if (confirmed) await voicesStore.deleteVoice(voice.id); }
async function handleDuplicate(voiceId) { await voicesStore.duplicateVoice(voiceId); }

// Test & Edit actions
async function handleGenerateTestAudio(voice) {
    const text = testText.value[voice.id];
    if (!text || !text.trim()) { uiStore.addNotification('Please enter text to test the voice.', 'warning'); return; }
    isTesting.value[voice.id] = true;
    try {
        const result = await voicesStore.testVoice({ text, voice_id: voice.id });
        if (result && result.audio_b64) {
            generatedAudioData.value[voice.id] = { b64: result.audio_b64, url: b64toUrl(result.audio_b64) };
        }
    } finally {
        isTesting.value[voice.id] = false;
    }
}

async function handleApplyEffects(voiceId) {
    if (!generatedAudioData.value[voiceId]) return;
    isApplyingEffects.value[voiceId] = true;
    try {
        const params = effectsParams.value[voiceId];
        const result = await voicesStore.applyEffects({
            audio_b64: generatedAudioData.value[voiceId].b64,
            pitch: params.pitch,
            speed: params.speed,
            gain: params.gain,
            reverb_params: { delay: params.reverb_delay, attenuation: params.reverb_attenuation }
        });
        if (result && result.audio_b64) {
            generatedAudioData.value[voiceId] = { b64: result.audio_b64, url: b64toUrl(result.audio_b64) };
            uiStore.addNotification('Effects applied.', 'success');
        }
    } finally {
        isApplyingEffects.value[voiceId] = false;
    }
}

async function handleTrim(voiceId, { start, end }) {
    if (!generatedAudioData.value[voiceId]) return;
    isApplyingEffects.value[voiceId] = true;
    try {
        const params = effectsParams.value[voiceId];
        const result = await voicesStore.applyEffects({
            audio_b64: generatedAudioData.value[voiceId].b64,
            pitch: params.pitch, speed: params.speed, gain: params.gain,
            reverb_params: { delay: params.reverb_delay, attenuation: params.reverb_attenuation },
            trim_start: start, trim_end: end
        });
        if (result && result.audio_b64) {
            generatedAudioData.value[voiceId] = { b64: result.audio_b64, url: b64toUrl(result.audio_b64) };
            uiStore.addNotification('Audio trimmed.', 'success');
        }
    } finally {
        isApplyingEffects.value[voiceId] = false;
    }
}

function handleDownload(voiceId) {
    const audioData = generatedAudioData.value[voiceId];
    if (!audioData || !audioData.url) return;
    const a = document.createElement('a');
    a.href = audioData.url;
    a.download = `edited_voice_${voiceId.substring(0, 8)}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

async function handleSaveAsNew(voiceId) {
    const audioData = generatedAudioData.value[voiceId];
    if (!audioData) return;
    const result = await uiStore.showConfirmation({
        title: 'Save As New Voice',
        message: 'Enter an alias for this new voice:',
        inputType: 'text',
        inputValue: `${voices.value.find(v => v.id === voiceId)?.alias || 'New Voice'} (edited)`,
        confirmText: 'Save',
    });
    if (result.confirmed && result.value) {
        isSubmitting.value = true;
        try {
            const blob = await fetch(audioData.url).then(r => r.blob());
            const file = new File([blob], "edited_voice.wav", { type: "audio/wav" });
            const params = effectsParams.value[voiceId];
            
            const formData = new FormData();
            formData.append('alias', result.value);
            formData.append('language', voices.value.find(v => v.id === voiceId)?.language || 'en');
            formData.append('pitch', params.pitch);
            formData.append('speed', params.speed);
            formData.append('gain', params.gain);
            const reverbParams = { delay: params.reverb_delay, attenuation: params.reverb_attenuation };
            formData.append('reverb_params_json', JSON.stringify(reverbParams));
            formData.append('file', file);
            
            await voicesStore.uploadVoice(formData);
            generatedAudioData.value[voiceId] = null; // Clear editor
        } finally {
            isSubmitting.value = false;
        }
    }
}


watch(voices, (newVoices) => {
    newVoices.forEach(voice => {
        if (!effectsParams.value[voice.id]) {
            effectsParams.value[voice.id] = {
                pitch: voice.pitch, speed: voice.speed, gain: voice.gain,
                reverb_delay: voice.reverb_params?.delay || 0,
                reverb_attenuation: voice.reverb_params?.attenuation || 0.0
            };
        }
        if(!testText.value[voice.id]){
             testText.value[voice.id] = 'Hello, this is a test of my voice.';
        }
    });
}, { deep: true, immediate: true });

onMounted(() => {
    voicesStore.fetchVoices();
});
</script>

<template>
    <PageViewLayout title="Voices Studio" :title-icon="IconMicrophone">
        <template #main>
            <div class="p-4 sm:p-6 lg:p-8 space-y-8">
                <!-- ... existing form code ... -->
                <div v-if="isLoading" class="text-center p-8">Loading your voices...</div>
                <div v-else-if="voices.length === 0 && !isFormVisible" class="text-center p-8 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                    <p>You haven't uploaded any custom voices yet.</p>
                </div>
                <div v-else class="space-y-4">
                    <div v-for="voice in voices" :key="voice.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md">
                        <div class="flex justify-between items-start">
                            <!-- ... existing voice info and buttons ... -->
                        </div>
                        <div class="mt-4 pt-4 border-t dark:border-gray-700 space-y-4">
                            <h5 class="text-base font-semibold">Test & Edit Voice</h5>
                            <div class="space-y-2">
                                <label :for="`test-text-${voice.id}`" class="text-sm font-medium">Test Text</label>
                                <textarea :id="`test-text-${voice.id}`" v-model="testText[voice.id]" class="input-field w-full" rows="2" placeholder="Enter text to generate audio..."></textarea>
                                <div class="flex justify-end">
                                    <button @click="handleGenerateTestAudio(voice)" class="btn btn-secondary" :disabled="isTesting[voice.id]">
                                        <IconAnimateSpin v-if="isTesting[voice.id]" class="w-5 h-5 mr-2" />
                                        {{ isTesting[voice.id] ? 'Generating...' : 'Generate Test Audio' }}
                                    </button>
                                </div>
                            </div>

                            <div v-if="generatedAudioData[voice.id]" class="mt-4 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg space-y-4">
                                <h6 class="font-semibold">Audio Editor</h6>
                                <AudioEditor :audio-url="generatedAudioData[voice.id].url" @trimmed="args => handleTrim(voice.id, args)" />
                                <div v-if="effectsParams[voice.id]" class="space-y-4 pt-4">
                                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                         <div><label class="block text-xs font-medium">Pitch ({{effectsParams[voice.id].pitch.toFixed(2)}})</label><input type="range" v-model.number="effectsParams[voice.id].pitch" class="w-full" step="0.05" min="0.5" max="2.0"></div>
                                         <div><label class="block text-xs font-medium">Speed ({{effectsParams[voice.id].speed.toFixed(2)}}x)</label><input type="range" v-model.number="effectsParams[voice.id].speed" class="w-full" step="0.05" min="0.5" max="2.0"></div>
                                         <div><label class="block text-xs font-medium">Gain ({{effectsParams[voice.id].gain.toFixed(1)}} dB)</label><input type="range" v-model.number="effectsParams[voice.id].gain" class="w-full" step="0.5" min="-20" max="20"></div>
                                    </div>
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                         <div><label class="block text-xs font-medium">Reverb Delay ({{effectsParams[voice.id].reverb_delay}}ms)</label><input type="range" v-model.number="effectsParams[voice.id].reverb_delay" class="w-full" step="5" min="0" max="200"></div>
                                         <div><label class="block text-xs font-medium">Reverb Attenuation ({{effectsParams[voice.id].reverb_attenuation.toFixed(1)}} dB)</label><input type="range" v-model.number="effectsParams[voice.id].reverb_attenuation" class="w-full" step="0.5" min="0" max="20"></div>
                                    </div>
                                    <div class="flex justify-end">
                                        <button @click="handleApplyEffects(voice.id)" class="btn btn-secondary" :disabled="isApplyingEffects[voice.id]">
                                            <IconAnimateSpin v-if="isApplyingEffects[voice.id]" class="w-4 h-4 mr-2" />
                                            Apply Effects
                                        </button>
                                    </div>
                                </div>
                                <div class="flex justify-end gap-2 pt-4 border-t dark:border-gray-700">
                                    <button @click="handleDownload(voice.id)" class="btn btn-secondary"><IconArrowDownTray class="w-4 h-4 mr-2"/>Download</button>
                                    <button @click="handleSaveAsNew(voice.id)" class="btn btn-primary"><IconPlus class="w-4 h-4 mr-2"/>Save as New Voice</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>