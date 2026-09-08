<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useVoicesStore } from '../stores/voices';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import { useDataStore } from '../stores/data';
import { useDiscussionsStore } from '../stores/discussions';

import PageViewLayout from '../components/layout/PageViewLayout.vue';
import VoiceEditor from '../components/voices/VoiceEditor.vue';

// Icons
import IconMicrophone from '../assets/icons/IconMicrophone.vue';
import IconSpeakerWave from '../assets/icons/IconSpeakerWave.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconStopCircle from '../assets/icons/IconStopCircle.vue';
import IconPlayCircle from '../assets/icons/IconPlayCircle.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconCopy from '../assets/icons/IconCopy.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';

const voicesStore = useVoicesStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const dataStore = useDataStore();
const discussionsStore = useDiscussionsStore();

const { voices, isLoading } = storeToRefs(voicesStore);
const { user } = storeToRefs(authStore);
const { availableTtsModels } = storeToRefs(dataStore);

// Active studio mode: 'generator' | 'library' | 'stt' | 'translation'
const activeMode = ref('generator');

// Capability Flags
const isTtsActive = computed(() => !!user.value?.tts_binding_model_name);
const isSttActive = computed(() => !!user.value?.stt_binding_model_name);
const hasNeither = computed(() => !isTtsActive.value && !isSttActive.value);

// --- Mode 1: Interactive TTS Speech Generator Console State ---
const synthText = ref('Welcome to LoLLMs Voices Studio. You can synthesize high-fidelity speech, craft voice cloning profiles, and transcribe audio.');
const synthSelectedVoiceId = ref(user.value?.active_voice_id || '');
const synthLanguage = ref(user.value?.ai_response_language && user.value.ai_response_language !== 'auto' ? user.value.ai_response_language : 'en');
const synthSpeed = ref(1.0);
const isSynthesizing = ref(false);
const synthAudioB64 = ref(null);
const synthAudioUrl = ref(null);

// --- Mode 2: Voice Cloning Library State ---
const selectedVoiceId = ref(null);
const isAddFormVisible = ref(false);
const newVoiceForm = ref({ alias: '', language: 'en', file: null });
const isSubmittingNew = ref(false);
const isRecording = ref(false);
const mediaRecorder = ref(null);
const audioChunks = ref([]);
const recordedAudioUrl = ref(null);
const recordedAudioBlob = ref(null);

const selectedVoice = computed(() => {
    if (!selectedVoiceId.value) return null;
    return voices.value.find(v => v.id === selectedVoiceId.value);
});

// --- Mode 3: STT Transcription State ---
const isRecordingForStt = ref(false);
const isTranscribing = ref(false);
const transcribedText = ref('');
const sttMediaRecorder = ref(null);
const sttAudioChunks = ref([]);

// --- Mode 4: Speech-to-Speech Translation State ---
const isRecordingForS2S = ref(false);
const isProcessingS2S = ref(false);
const s2sSourceAudioBlob = ref(null);
const s2sSourceAudioUrl = ref(null);
const s2sTargetLanguage = ref('en');
const s2sSelectedVoiceId = ref('');
const s2sTranslateText = ref(true);
const s2sResult = ref(null);
const s2sMediaRecorder = ref(null);
const s2sAudioChunks = ref([]);

const availableLanguages = [
    { code: 'en', name: 'English' },
    { code: 'fr', name: 'French' },
    { code: 'es', name: 'Spanish' },
    { code: 'de', name: 'German' },
    { code: 'it', name: 'Italian' },
    { code: 'pt', name: 'Portuguese' },
    { code: 'zh', name: 'Chinese' },
    { code: 'ja', name: 'Japanese' },
    { code: 'ko', name: 'Korean' },
    { code: 'ru', name: 'Russian' },
    { code: 'ar', name: 'Arabic' }
];

async function handleGenerateSpeech() {
    if (!synthText.value.trim()) {
        uiStore.addNotification('Please enter text to synthesize.', 'warning');
        return;
    }

    isSynthesizing.value = true;
    synthAudioB64.value = null;
    synthAudioUrl.value = null;

    try {
        const payload = {
            text: synthText.value.trim(),
            voice_id: synthSelectedVoiceId.value || null,
            language: synthLanguage.value || 'en',
            speed: synthSpeed.value
        };

        const result = await voicesStore.synthesizeSpeech(payload);
        if (result && result.audio_b64) {
            synthAudioB64.value = result.audio_b64;
            synthAudioUrl.value = `data:audio/wav;base64,${result.audio_b64}`;
            uiStore.addNotification('Speech generated successfully!', 'success');
        }
    } finally {
        isSynthesizing.value = false;
    }
}

function downloadSynthesizedAudio() {
    if (!synthAudioB64.value) return;
    const byteChars = atob(synthAudioB64.value);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: 'audio/wav' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `speech_synthesis_${Date.now()}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// --- Voice Library CRUD & Methods ---
function showAddForm() {
    selectedVoiceId.value = null;
    isAddFormVisible.value = true;
    newVoiceForm.value = { alias: '', language: 'en', file: null };
    recordedAudioUrl.value = null;
    recordedAudioBlob.value = null;
}

function cancelAddForm() {
    isAddFormVisible.value = false;
    stopRecording();
}

function handleNewFileChange(event) {
    const f = event.target.files[0];
    if (f) {
        newVoiceForm.value.file = f;
        recordedAudioUrl.value = URL.createObjectURL(f);
        recordedAudioBlob.value = f;
    }
}

async function startRecording() {
    if (navigator.mediaDevices?.getUserMedia) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder.value = new MediaRecorder(stream);
            audioChunks.value = [];
            mediaRecorder.value.ondataavailable = e => audioChunks.value.push(e.data);
            mediaRecorder.value.onstop = () => {
                recordedAudioBlob.value = new Blob(audioChunks.value, { type: 'audio/wav' });
                recordedAudioUrl.value = URL.createObjectURL(recordedAudioBlob.value);
            };
            mediaRecorder.value.start();
            isRecording.value = true;
        } catch (err) {
            uiStore.addNotification('Microphone access denied.', 'error');
        }
    }
}

function stopRecording() {
    if (mediaRecorder.value && isRecording.value) {
        mediaRecorder.value.stop();
        isRecording.value = false;
    }
}

async function handleAddNewVoice() {
    isSubmittingNew.value = true;
    try {
        const fileToUpload = newVoiceForm.value.file || recordedAudioBlob.value;
        if (!fileToUpload) {
            uiStore.addNotification('An audio reference file or microphone recording is required.', 'warning');
            return;
        }
        const formData = new FormData();
        formData.append('alias', newVoiceForm.value.alias);
        formData.append('language', newVoiceForm.value.language);
        formData.append('file', fileToUpload, "recorded_voice.wav");

        const newVoice = await voicesStore.uploadVoice(formData);
        if (newVoice) {
            cancelAddForm();
            selectVoice(newVoice.id);
        }
    } finally {
        isSubmittingNew.value = false;
    }
}

function selectVoice(voiceId) {
    isAddFormVisible.value = false;
    selectedVoiceId.value = voiceId;
    activeMode.value = 'library';
}

async function handleDeleteVoice(voice) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Voice: ${voice.alias}`,
        message: 'Are you sure you want to permanently delete this voice? This cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed?.confirmed || confirmed === true) {
        await voicesStore.deleteVoice(voice.id);
        if (selectedVoiceId.value === voice.id) {
            selectedVoiceId.value = null;
        }
    }
}

async function handleSetActiveVoice(voiceId) {
    await voicesStore.setActiveVoice(voiceId);
}

// --- STT Methods ---
async function startSttRecording() {
    if (navigator.mediaDevices?.getUserMedia) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            sttMediaRecorder.value = new MediaRecorder(stream);
            sttAudioChunks.value = [];
            sttMediaRecorder.value.ondataavailable = e => sttAudioChunks.value.push(e.data);
            sttMediaRecorder.value.onstop = async () => {
                isTranscribing.value = true;
                transcribedText.value = '';
                const audioBlob = new Blob(sttAudioChunks.value, { type: 'audio/wav' });
                try {
                    const text = await discussionsStore.transcribeAudio(audioBlob);
                    transcribedText.value = text;
                } finally {
                    isTranscribing.value = false;
                }
            };
            sttMediaRecorder.value.start();
            isRecordingForStt.value = true;
        } catch (err) {
            uiStore.addNotification('Microphone access denied.', 'error');
        }
    }
}

function stopSttRecording() {
    if (sttMediaRecorder.value && isRecordingForStt.value) {
        sttMediaRecorder.value.stop();
        isRecordingForStt.value = false;
    }
}

function toggleSttRecording() {
    if (isRecordingForStt.value) stopSttRecording();
    else startSttRecording();
}

async function handleSttFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    isTranscribing.value = true;
    transcribedText.value = '';
    try {
        const text = await discussionsStore.transcribeAudio(file);
        transcribedText.value = text;
    } finally {
        isTranscribing.value = false;
        event.target.value = '';
    }
}

function copyTranscription() {
    if (transcribedText.value) {
        navigator.clipboard.writeText(transcribedText.value);
        uiStore.addNotification('Transcription copied!', 'success');
    }
}

// --- Audio-to-Audio Translation Methods ---
async function startS2SRecording() {
    if (navigator.mediaDevices?.getUserMedia) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            s2sMediaRecorder.value = new MediaRecorder(stream);
            s2sAudioChunks.value = [];
            s2sMediaRecorder.value.ondataavailable = e => s2sAudioChunks.value.push(e.data);
            s2sMediaRecorder.value.onstop = () => {
                s2sSourceAudioBlob.value = new Blob(s2sAudioChunks.value, { type: 'audio/wav' });
                s2sSourceAudioUrl.value = URL.createObjectURL(s2sSourceAudioBlob.value);
            };
            s2sMediaRecorder.value.start();
            isRecordingForS2S.value = true;
        } catch (err) {
            uiStore.addNotification('Microphone access denied.', 'error');
        }
    }
}

function stopS2SRecording() {
    if (s2sMediaRecorder.value && isRecordingForS2S.value) {
        s2sMediaRecorder.value.stop();
        isRecordingForS2S.value = false;
    }
}

function toggleS2SRecording() {
    if (isRecordingForS2S.value) stopS2SRecording();
    else startS2SRecording();
}

function handleS2SFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    s2sSourceAudioBlob.value = file;
    s2sSourceAudioUrl.value = URL.createObjectURL(file);
    event.target.value = '';
}

async function executeAudioToAudio() {
    if (!s2sSourceAudioBlob.value) {
        uiStore.addNotification('Please record speech or upload an audio file.', 'warning');
        return;
    }
    isProcessingS2S.value = true;
    s2sResult.value = null;

    try {
        const formData = new FormData();
        formData.append('file', s2sSourceAudioBlob.value, 'speech_input.wav');
        if (s2sSelectedVoiceId.value) formData.append('voice_id', s2sSelectedVoiceId.value);
        formData.append('target_language', s2sTargetLanguage.value);
        formData.append('translate', s2sTranslateText.value ? 'true' : 'false');

        const result = await voicesStore.audioToAudioTranslate(formData);
        s2sResult.value = result;
        uiStore.addNotification('Speech translation and re-synthesis complete!', 'success');
    } catch (e) {
        console.error(e);
    } finally {
        isProcessingS2S.value = false;
    }
}

onMounted(() => {
    voicesStore.fetchVoices();
    dataStore.fetchAvailableTtsModels();
    dataStore.fetchAvailableSttModels();
});
</script>

<template>
    <PageViewLayout title="Voices Studio" :title-icon="IconMicrophone">
        
        <!-- SIDEBAR -->
        <template #sidebar>
            <div v-if="hasNeither" class="p-4 text-center text-xs text-gray-500 space-y-3">
                <p>No TTS or STT speech bindings are currently active.</p>
                <router-link to="/settings" class="btn btn-primary btn-sm w-full block">Configure Bindings</router-link>
            </div>

            <div v-else class="h-full flex flex-col min-h-0 space-y-4">
                <!-- Mode Switcher -->
                <div class="p-1 bg-gray-100 dark:bg-gray-800 rounded-xl flex flex-col gap-1 shrink-0">
                    <button 
                        @click="activeMode = 'generator'" 
                        class="py-2 px-3 text-xs font-bold rounded-lg transition-all flex items-center gap-2"
                        :class="activeMode === 'generator' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        <IconSpeakerWave class="w-4 h-4 text-blue-500" />
                        <span>TTS Speech Studio</span>
                    </button>
                    <button 
                        @click="activeMode = 'library'" 
                        class="py-2 px-3 text-xs font-bold rounded-lg transition-all flex items-center gap-2"
                        :class="activeMode === 'library' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        <span>🎙️</span>
                        <span>Voice Profiles ({{ voices.length }})</span>
                    </button>
                    <button 
                        v-if="isSttActive"
                        @click="activeMode = 'stt'" 
                        class="py-2 px-3 text-xs font-bold rounded-lg transition-all flex items-center gap-2"
                        :class="activeMode === 'stt' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        <IconMicrophone class="w-4 h-4 text-teal-500" />
                        <span>STT Transcribe</span>
                    </button>
                    <button 
                        v-if="isTtsActive && isSttActive"
                        @click="activeMode = 'translation'" 
                        class="py-2 px-3 text-xs font-bold rounded-lg transition-all flex items-center gap-2"
                        :class="activeMode === 'translation' ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        <IconSparkles class="w-4 h-4 text-purple-500" />
                        <span>Audio-to-Audio</span>
                    </button>
                </div>

                <!-- Voice Profiles List -->
                <div class="flex-1 flex flex-col min-h-0">
                    <button @click="showAddForm" class="w-full flex items-center space-x-3 text-left px-3 py-2 rounded-xl text-xs font-bold text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/40 transition-colors shrink-0">
                        <IconPlus class="w-4 h-4 shrink-0" />
                        <span>Add Voice Profile</span>
                    </button>
                    
                    <div class="overflow-y-auto custom-scrollbar grow mt-2 pr-1 space-y-1">
                        <div v-if="isLoading" class="p-4 text-center text-xs text-gray-400">Loading voices...</div>
                        <div v-else-if="voices.length === 0" class="p-4 text-center text-xs text-gray-400 italic">No custom voices saved.</div>
                        <ul v-else class="space-y-1">
                            <li v-for="voice in voices" :key="voice.id">
                                <div class="w-full text-left px-3 py-2 rounded-xl text-xs transition-all group flex justify-between items-center border"
                                     :class="{
                                         'bg-blue-50 dark:bg-blue-900/30 border-blue-500/40 text-blue-700 dark:text-blue-300 font-bold': selectedVoiceId === voice.id && activeMode === 'library' && !isAddFormVisible, 
                                         'border-transparent text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800': selectedVoiceId !== voice.id || activeMode !== 'library' || isAddFormVisible
                                     }">
                                    <button @click="selectVoice(voice.id)" class="grow text-left truncate flex items-center gap-2">
                                        <span>🎙️</span>
                                        <span class="truncate">{{ voice.alias }}</span>
                                    </button>
                                    <div class="flex items-center shrink-0 gap-1.5">
                                        <button 
                                            @click.stop="handleSetActiveVoice(voice.id)" 
                                            class="px-1.5 py-0.5 text-[9px] font-black uppercase rounded-md transition-colors"
                                            :class="user && user.active_voice_id === voice.id ? 'bg-emerald-500 text-white shadow-xs' : 'text-gray-400 hover:text-emerald-600 bg-gray-100 dark:bg-gray-800'"
                                            title="Set as global active speech voice"
                                        >
                                            {{ user && user.active_voice_id === voice.id ? 'Active' : 'Set' }}
                                        </button>
                                        <div class="flex items-center opacity-0 group-hover:opacity-100 transition-opacity ml-1">
                                            <button @click.stop="selectVoice(voice.id)" title="Edit" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md"><IconPencil class="w-3.5 h-3.5" /></button>
                                            <button @click.stop="handleDeleteVoice(voice)" title="Delete" class="p-1 hover:bg-red-100 dark:hover:bg-red-900/50 text-red-500 rounded-md"><IconTrash class="w-3.5 h-3.5" /></button>
                                        </div>
                                    </div>
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </template>

        <!-- MAIN VIEWPORT -->
        <template #main>
            <!-- Mode 0: Fallback -->
            <div v-if="hasNeither" class="h-full flex flex-col items-center justify-center text-center p-8">
                <div class="w-20 h-20 bg-gray-100 dark:bg-gray-800 rounded-3xl flex items-center justify-center mb-6 text-gray-400">
                    <IconMicrophone class="w-10 h-10" />
                </div>
                <h2 class="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tight mb-2">Voices Studio Inactive</h2>
                <p class="text-sm text-gray-500 max-w-md mb-8">
                    To use Text-to-Speech synthesis or transcription, configure an active <strong>TTS</strong> or <strong>STT</strong> binding in settings.
                </p>
                <router-link to="/settings" class="btn btn-primary px-8 py-3 rounded-2xl shadow-xl">
                    Configure Voice Bindings
                </router-link>
            </div>

            <!-- Mode 1: TTS SPEECH GENERATION STUDIO -->
            <div v-else-if="activeMode === 'generator'" class="p-6 h-full overflow-y-auto custom-scrollbar">
                <div class="max-w-4xl mx-auto space-y-6">
                    <div class="bg-white dark:bg-gray-800 p-6 rounded-3xl border border-gray-200 dark:border-gray-700 shadow-md space-y-6">
                        <div class="flex items-center justify-between border-b dark:border-gray-700 pb-4">
                            <div>
                                <h3 class="text-xl font-black text-gray-900 dark:text-white flex items-center gap-2">
                                    <IconSpeakerWave class="w-6 h-6 text-blue-500" />
                                    <span>Neural Text-to-Speech Console</span>
                                </h3>
                                <p class="text-xs text-gray-500 mt-0.5">Synthesize natural speech from text using your active TTS binding and custom cloned voice profiles.</p>
                            </div>
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-bold text-gray-400 font-mono">Engine: {{ user?.tts_binding_model_name || 'Active Binding' }}</span>
                            </div>
                        </div>

                        <!-- Text Input Area -->
                        <div class="space-y-2">
                            <label class="block text-xs font-bold uppercase tracking-wider text-gray-500">Text to Synthesize</label>
                            <textarea 
                                v-model="synthText" 
                                rows="5" 
                                class="input-field w-full text-sm leading-relaxed" 
                                placeholder="Type or paste any text to convert to high-fidelity spoken audio..."
                            ></textarea>
                        </div>

                        <!-- Synthesis Modifiers -->
                        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700">
                            <div>
                                <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Voice Profile</label>
                                <select v-model="synthSelectedVoiceId" class="input-field text-xs w-full">
                                    <option value="">Default AI Voice</option>
                                    <option v-for="v in voices" :key="v.id" :value="v.id">{{ v.alias }} ({{ v.language.toUpperCase() }})</option>
                                </select>
                            </div>

                            <div>
                                <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Language</label>
                                <select v-model="synthLanguage" class="input-field text-xs w-full">
                                    <option v-for="l in availableLanguages" :key="l.code" :value="l.code">{{ l.name }} ({{ l.code }})</option>
                                </select>
                            </div>

                            <div class="space-y-1">
                                <div class="flex justify-between text-xs font-bold">
                                    <span>Speech Cadence</span>
                                    <span class="font-mono text-blue-500">{{ synthSpeed.toFixed(2) }}x</span>
                                </div>
                                <input type="range" v-model.number="synthSpeed" min="0.5" max="2.0" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>
                        </div>

                        <!-- Generate Action Button -->
                        <div class="flex justify-end items-center gap-3">
                            <button @click="handleGenerateSpeech" :disabled="isSynthesizing || !synthText.trim()" class="btn btn-primary px-8 py-3 rounded-2xl shadow-lg flex items-center gap-2">
                                <IconAnimateSpin v-if="isSynthesizing" class="w-5 h-5 animate-spin" />
                                <IconSparkles v-else class="w-5 h-5" />
                                <span>{{ isSynthesizing ? 'Synthesizing Speech...' : 'Generate Spoken Audio' }}</span>
                            </button>
                        </div>

                        <!-- Audio Output Preview Player -->
                        <div v-if="synthAudioUrl" class="p-5 bg-blue-50/50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-900/40 rounded-2xl space-y-3 animate-in fade-in">
                            <div class="flex items-center justify-between">
                                <span class="text-xs font-black uppercase tracking-wider text-blue-600 dark:text-blue-400 flex items-center gap-2">
                                    <IconCheckCircle class="w-4 h-4 text-emerald-500" />
                                    <span>Generated Spoken Audio</span>
                                </span>
                                <button @click="downloadSynthesizedAudio" class="btn btn-secondary btn-xs flex items-center gap-1.5">
                                    <IconArrowDownTray class="w-3.5 h-3.5" />
                                    <span>Download .wav</span>
                                </button>
                            </div>
                            <audio :src="synthAudioUrl" controls class="w-full h-10 rounded-xl" autoplay></audio>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Mode 2: VOICE CLONING & CUSTOM PROFILES LIBRARY -->
            <div v-else-if="activeMode === 'library'" class="h-full flex flex-col overflow-hidden">
                <!-- Add New Voice Modal/Card -->
                <div v-if="isAddFormVisible" class="p-6 h-full overflow-y-auto">
                    <div class="bg-white dark:bg-gray-800 p-6 rounded-3xl border dark:border-gray-700 shadow-xl space-y-6 max-w-3xl mx-auto">
                        <div class="flex items-center justify-between border-b dark:border-gray-700 pb-3">
                            <h3 class="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                                <span>🎙️</span>
                                <span>Create New Voice Profile</span>
                            </h3>
                            <button @click="cancelAddForm" class="btn btn-secondary btn-xs">Cancel</button>
                        </div>
                        <form @submit.prevent="handleAddNewVoice" class="space-y-4">
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div><label class="label">Voice Alias / Name</label><input type="text" v-model="newVoiceForm.alias" class="input-field mt-1" placeholder="e.g., British Narrator" required></div>
                                <div>
                                    <label class="label">Language</label>
                                    <select v-model="newVoiceForm.language" class="input-field mt-1">
                                        <option v-for="l in availableLanguages" :key="l.code" :value="l.code">{{ l.name }} ({{ l.code }})</option>
                                    </select>
                                </div>
                            </div>
                            <div class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl border dark:border-gray-600 space-y-3">
                                <h4 class="font-bold text-xs uppercase tracking-widest text-primary">Reference Voice Sample</h4>
                                <p class="text-xs text-gray-500">Upload 5-15 seconds of clean, noise-free speech for zero-shot neural cloning.</p>
                                <div class="flex flex-col sm:flex-row items-center gap-4 pt-1">
                                    <button type="button" @click="isRecording ? stopRecording() : startRecording()" class="btn btn-secondary w-full sm:w-auto" :class="{'bg-red-500 text-white hover:bg-red-600 animate-pulse': isRecording}">
                                        <IconStopCircle v-if="isRecording" class="w-4 h-4 mr-2" />
                                        <IconMicrophone v-else class="w-4 h-4 mr-2" />
                                        {{ isRecording ? 'Stop Recording' : 'Record from Mic' }}
                                    </button>
                                    <span class="text-xs font-bold text-gray-400 uppercase">OR</span>
                                    <input type="file" @change="handleNewFileChange" class="input-field-file text-xs" accept="audio/*,.wav,.mp3,.ogg">
                                </div>
                                <div v-if="recordedAudioUrl" class="mt-3 p-3 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-600">
                                    <audio :src="recordedAudioUrl" controls class="w-full h-8"></audio>
                                </div>
                            </div>
                            <div class="flex justify-end gap-3 pt-2">
                                <button type="button" @click="cancelAddForm" class="btn btn-secondary">Cancel</button>
                                <button type="submit" class="btn btn-primary" :disabled="isSubmittingNew || isRecording">
                                    <IconAnimateSpin v-if="isSubmittingNew" class="w-4 h-4 mr-2 animate-spin" />
                                    <span>{{ isSubmittingNew ? 'Saving...' : 'Save Voice Profile' }}</span>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- Active Voice Inspector / Waveform Editor -->
                <VoiceEditor v-else-if="selectedVoice" :key="selectedVoice.id" :voice-id="selectedVoice.id" :voice-data="selectedVoice" @updated="voicesStore.fetchVoices" />

                <!-- Empty Voice Prompt -->
                <div v-else class="h-full flex flex-col items-center justify-center text-center p-8">
                    <div class="w-16 h-16 bg-blue-50 dark:bg-blue-900/30 text-blue-500 rounded-2xl flex items-center justify-center mb-4">
                        <IconSpeakerWave class="w-8 h-8" />
                    </div>
                    <h3 class="text-lg font-bold text-gray-900 dark:text-white uppercase tracking-tight">Voice Cloning Library</h3>
                    <p class="text-xs text-gray-500 max-w-sm mt-1 mb-6">
                        Select a voice profile from the sidebar to inspect waveforms and customize pitch, speed, and reverb.
                    </p>
                    <button @click="showAddForm" class="btn btn-primary btn-sm flex items-center gap-2">
                        <IconPlus class="w-4 h-4" />
                        <span>Create New Voice</span>
                    </button>
                </div>
            </div>

            <!-- Mode 3: STT TRANSCRIPTION STUDIO -->
            <div v-else-if="activeMode === 'stt'" class="p-6 h-full overflow-y-auto custom-scrollbar">
                <div class="max-w-4xl mx-auto space-y-6">
                    <div class="bg-white dark:bg-gray-800 p-6 rounded-3xl border dark:border-gray-700 shadow-md space-y-4">
                        <div class="flex items-center justify-between border-b dark:border-gray-700 pb-3">
                            <div>
                                <h3 class="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                                    <IconMicrophone class="w-5 h-5 text-teal-500" />
                                    <span>Speech-to-Text Transcription</span>
                                </h3>
                                <p class="text-xs text-gray-500">Record from your microphone or upload audio files to transcribe speech to text.</p>
                            </div>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="p-5 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700 flex flex-col items-center justify-center text-center space-y-3">
                                <span class="text-xs font-bold uppercase tracking-wider text-gray-400">Microphone Input</span>
                                <button @click="toggleSttRecording" class="btn btn-sm w-full py-2.5 flex items-center justify-center gap-2" :class="isRecordingForStt ? 'btn-danger animate-pulse' : 'btn-primary'" :disabled="isTranscribing">
                                    <IconStopCircle v-if="isRecordingForStt" class="w-4 h-4" />
                                    <IconMicrophone v-else class="w-4 h-4" />
                                    <span>{{ isRecordingForStt ? 'Stop & Transcribe' : 'Start Recording' }}</span>
                                </button>
                                <span v-if="isRecordingForStt" class="text-[10px] text-red-500 font-bold uppercase tracking-widest animate-pulse">Recording audio stream...</span>
                            </div>

                            <div class="p-5 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700 flex flex-col items-center justify-center text-center space-y-3">
                                <span class="text-xs font-bold uppercase tracking-wider text-gray-400">Upload Audio File</span>
                                <label class="btn btn-secondary btn-sm w-full py-2.5 flex items-center justify-center gap-2 cursor-pointer" :class="{'opacity-50 pointer-events-none': isTranscribing}">
                                    <IconArrowUpTray class="w-4 h-4" />
                                    <span>Select Audio File</span>
                                    <input type="file" @change="handleSttFileUpload" class="hidden" accept="audio/*,.wav,.mp3,.ogg,.m4a">
                                </label>
                                <span class="text-[10px] text-gray-400">Supports WAV, MP3, OGG, M4A</span>
                            </div>
                        </div>

                        <div v-if="isTranscribing" class="p-6 bg-teal-50/50 dark:bg-teal-900/20 rounded-xl border border-teal-100 dark:border-teal-900/40 text-center space-y-2 animate-in fade-in">
                            <IconAnimateSpin class="w-8 h-8 text-teal-500 animate-spin mx-auto" />
                            <p class="text-xs font-bold text-teal-600 dark:text-teal-400 uppercase tracking-widest">Neural Transcription in progress...</p>
                        </div>

                        <div v-if="transcribedText" class="space-y-3 pt-2 animate-in fade-in">
                            <div class="flex items-center justify-between">
                                <span class="text-xs font-black uppercase tracking-widest text-primary">Transcript Output</span>
                                <button @click="copyTranscription" class="btn btn-secondary btn-xs flex items-center gap-1.5">
                                    <IconCopy class="w-3.5 h-3.5" /> Copy Text
                                </button>
                            </div>
                            <div class="p-4 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-700 text-sm leading-relaxed whitespace-pre-wrap font-sans text-gray-800 dark:text-gray-200">
                                {{ transcribedText }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Mode 4: AUDIO-TO-AUDIO TRANSLATION -->
            <div v-else-if="activeMode === 'translation'" class="p-6 h-full overflow-y-auto custom-scrollbar">
                <div class="max-w-4xl mx-auto space-y-6">
                    <div class="bg-white dark:bg-gray-800 p-6 rounded-3xl border dark:border-gray-700 shadow-md space-y-6">
                        <div class="border-b dark:border-gray-700 pb-3">
                            <h3 class="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                                <span class="text-xl">⚡</span>
                                <span>Speech-to-Speech Translation</span>
                            </h3>
                            <p class="text-xs text-gray-500">Record or upload speech to transcribe, translate, and synthesize back in real-time.</p>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700 text-center space-y-3">
                                <span class="text-xs font-bold uppercase tracking-wider text-gray-400">Step 1: Record Voice</span>
                                <button @click="toggleS2SRecording" class="btn btn-sm w-full py-2.5 flex items-center justify-center gap-2" :class="isRecordingForS2S ? 'btn-danger animate-pulse' : 'btn-primary'" :disabled="isProcessingS2S">
                                    <IconStopCircle v-if="isRecordingForS2S" class="w-4 h-4" />
                                    <IconMicrophone v-else class="w-4 h-4" />
                                    <span>{{ isRecordingForS2S ? 'Stop Recording' : 'Record Speech' }}</span>
                                </button>
                            </div>

                            <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700 text-center space-y-3">
                                <span class="text-xs font-bold uppercase tracking-wider text-gray-400">Step 1: Or Upload Audio</span>
                                <label class="btn btn-secondary btn-sm w-full py-2.5 flex items-center justify-center gap-2 cursor-pointer" :class="{'opacity-50 pointer-events-none': isProcessingS2S}">
                                    <IconArrowUpTray class="w-4 h-4" />
                                    <span>Select Audio</span>
                                    <input type="file" @change="handleS2SFileUpload" class="hidden" accept="audio/*,.wav,.mp3">
                                </label>
                            </div>
                        </div>

                        <div v-if="s2sSourceAudioUrl" class="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700 space-y-1">
                            <span class="text-[10px] font-bold text-gray-400 uppercase">Input Audio</span>
                            <audio :src="s2sSourceAudioUrl" controls class="w-full h-8"></audio>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700">
                            <div>
                                <label class="label text-xs">Target Language</label>
                                <select v-model="s2sTargetLanguage" class="input-field mt-1 !text-xs">
                                    <option v-for="l in availableLanguages" :key="l.code" :value="l.code">{{ l.name }} ({{ l.code }})</option>
                                </select>
                            </div>
                            <div>
                                <label class="label text-xs">Target Cloned Voice</label>
                                <select v-model="s2sSelectedVoiceId" class="input-field mt-1 !text-xs">
                                    <option value="">Default AI Voice</option>
                                    <option v-for="v in voices" :key="v.id" :value="v.id">{{ v.alias }} ({{ v.language.toUpperCase() }})</option>
                                </select>
                            </div>
                            <div class="col-span-full flex items-center justify-between pt-2">
                                <span class="text-xs font-medium text-gray-700 dark:text-gray-300">Translate Text via Neural LLM (uncheck for pure voice conversion)</span>
                                <input type="checkbox" v-model="s2sTranslateText" class="h-4 w-4 rounded text-purple-600 focus:ring-purple-500">
                            </div>
                        </div>

                        <div class="flex justify-end">
                            <button @click="executeAudioToAudio" :disabled="isProcessingS2S || !s2sSourceAudioBlob" class="btn btn-primary px-8 py-3 rounded-xl shadow-lg flex items-center gap-2">
                                <IconAnimateSpin v-if="isProcessingS2S" class="w-5 h-5 animate-spin" />
                                <IconSparkles v-else class="w-5 h-5" />
                                <span>{{ isProcessingS2S ? 'Processing...' : 'Process Audio to Audio' }}</span>
                            </button>
                        </div>

                        <div v-if="s2sResult" class="space-y-4 pt-4 border-t dark:border-gray-700 animate-in fade-in">
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div class="p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-700 space-y-1">
                                    <span class="text-[9px] font-black uppercase text-gray-400">Transcribed Original</span>
                                    <p class="text-xs text-gray-700 dark:text-gray-300">{{ s2sResult.source_text }}</p>
                                </div>
                                <div class="p-3 bg-purple-50 dark:bg-purple-950/20 rounded-xl border border-purple-200 dark:border-purple-900/40 space-y-1">
                                    <span class="text-[9px] font-black uppercase text-purple-600 dark:text-purple-400">Translated Speech Text ({{ s2sResult.target_language.toUpperCase() }})</span>
                                    <p class="text-xs font-bold text-gray-900 dark:text-white">{{ s2sResult.translated_text }}</p>
                                </div>
                            </div>

                            <div v-if="s2sResult.audio_b64" class="p-4 bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/40 rounded-xl space-y-3">
                                <span class="text-xs font-black uppercase tracking-wider text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                                    <IconCheckCircle class="w-4 h-4" /> Synthesized Translated Audio Stream
                                </span>
                                <audio :src="`data:audio/wav;base64,${s2sResult.audio_b64}`" controls class="w-full h-10 rounded-xl"></audio>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>