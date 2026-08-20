<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useVoicesStore } from '../stores/voices';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
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
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconCopy from '../assets/icons/IconCopy.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';

const voicesStore = useVoicesStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const { voices, isLoading } = storeToRefs(voicesStore);
const { user } = storeToRefs(authStore);

// Capability Flags
const isTtsActive = computed(() => !!user.value?.tts_binding_model_name);
const isSttActive = computed(() => !!user.value?.stt_binding_model_name);
const hasBoth = computed(() => isTtsActive.value && isSttActive.value);
const hasNeither = computed(() => !isTtsActive.value && !isSttActive.value);

// Primary active workspace mode: 'tts' | 'stt' | 'translation'
const activeMode = ref('tts');

watch([isTtsActive, isSttActive], ([tts, stt]) => {
    if (tts && stt) {
        if (!['tts', 'stt', 'translation'].includes(activeMode.value)) activeMode.value = 'tts';
    } else if (tts) {
        activeMode.value = 'tts';
    } else if (stt) {
        activeMode.value = 'stt';
    }
}, { immediate: true });

// --- TTS State ---
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

// --- STT Transcription State ---
const isRecordingForStt = ref(false);
const isTranscribing = ref(false);
const transcribedText = ref('');
const sttMediaRecorder = ref(null);
const sttAudioChunks = ref([]);

// --- Speech-to-Speech Translation State ---
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

// --- TTS Voice Methods ---
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
            uiStore.addNotification('An audio file or microphone recording is required.', 'warning');
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
}

async function handleDeleteVoice(voice) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Voice: ${voice.alias}`,
        message: 'Are you sure you want to permanently delete this voice? This action cannot be undone.',
        confirmText: 'Delete',
        danger: true
    });
    if (confirmed.confirmed) {
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
        uiStore.copyToClipboard(transcribedText.value, 'Transcription copied!');
    }
}

function downloadTranscription() {
    if (!transcribedText.value) return;
    const blob = new Blob([transcribedText.value], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcription_${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
        uiStore.addNotification('Please provide audio by recording or uploading a file.', 'warning');
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
        uiStore.addNotification('Audio translation and synthesis completed!', 'success');
    } catch (e) {
        console.error(e);
    } finally {
        isProcessingS2S.value = false;
    }
}

function downloadS2SOutput() {
    if (!s2sResult.value?.audio_b64) return;
    const byteChars = atob(s2sResult.value.audio_b64);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: 'audio/wav' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `translated_voice_${Date.now()}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

onMounted(() => {
    if (isTtsActive.value) {
        voicesStore.fetchVoices();
    }
});
</script>

<template>
    <PageViewLayout title="Voices Studio" :title-icon="IconMicrophone">
        
        <!-- SIDEBAR -->
        <template #sidebar>
            <!-- Case 0: Neither TTS nor STT configured -->
            <div v-if="hasNeither" class="p-4 text-center text-xs text-gray-500 space-y-3">
                <p>No speech bindings are currently active.</p>
                <router-link to="/settings" class="btn btn-primary btn-sm w-full block">Configure Bindings</router-link>
            </div>

            <!-- Case 1: Active Services Navigation -->
            <div v-else class="h-full flex flex-col min-h-0 space-y-4">
                
                <!-- Multi-Service Tab Switcher (When Both are on) -->
                <div v-if="hasBoth" class="p-1 bg-gray-100 dark:bg-gray-800 rounded-xl flex shrink-0">
                    <button 
                        @click="activeMode = 'tts'" 
                        class="flex-1 py-1.5 text-[10px] font-black uppercase tracking-wider rounded-lg transition-all"
                        :class="activeMode === 'tts' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        TTS Voice
                    </button>
                    <button 
                        @click="activeMode = 'stt'" 
                        class="flex-1 py-1.5 text-[10px] font-black uppercase tracking-wider rounded-lg transition-all"
                        :class="activeMode === 'stt' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        STT Transcribe
                    </button>
                    <button 
                        @click="activeMode = 'translation'" 
                        class="flex-1 py-1.5 text-[10px] font-black uppercase tracking-wider rounded-lg transition-all"
                        :class="activeMode === 'translation' ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                        title="Speech-to-Speech Audio Translation"
                    >
                        Audio-to-Audio
                    </button>
                </div>

                <!-- TTS Sidebar List (When in TTS mode) -->
                <div v-if="isTtsActive && activeMode === 'tts'" class="flex-1 flex flex-col min-h-0">
                    <button @click="showAddForm" class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/50 transition-colors shrink-0">
                        <IconPlus class="w-5 h-5 shrink-0" />
                        <span>New Custom Voice</span>
                    </button>
                
                    <div class="mt-4 shrink-0">
                        <h3 class="text-xs font-bold uppercase tracking-wider text-gray-400 px-3">Voice Library ({{ voices.length }})</h3>
                    </div>
                    
                    <div class="overflow-y-auto custom-scrollbar grow mt-2 pr-1 space-y-1">
                        <div v-if="isLoading" class="p-4 text-center text-xs text-gray-400">Loading voices...</div>
                        <div v-else-if="voices.length === 0" class="p-4 text-center text-xs text-gray-400 italic">No custom voices saved.</div>
                        <ul v-else class="space-y-1">
                            <li v-for="voice in voices" :key="voice.id">
                                <div class="w-full text-left px-3 py-2 rounded-xl text-xs transition-all group flex justify-between items-center border"
                                     :class="{
                                         'bg-blue-50 dark:bg-blue-900/30 border-blue-500/40 text-blue-700 dark:text-blue-300 font-bold': selectedVoiceId === voice.id && !isAddFormVisible, 
                                         'border-transparent text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800': selectedVoiceId !== voice.id || isAddFormVisible
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

                <!-- STT Quick Summary / Status (When in STT Mode) -->
                <div v-else-if="isSttActive && activeMode === 'stt'" class="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-xl text-xs space-y-2">
                    <span class="font-bold uppercase tracking-wider text-[10px] text-primary block">STT Status</span>
                    <p class="text-gray-600 dark:text-gray-300">Speech-to-text is ready. Record live or upload an audio file for neural transcription.</p>
                </div>

                <!-- Translation Mode Summary -->
                <div v-else-if="hasBoth && activeMode === 'translation'" class="p-3 bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-900/40 rounded-xl text-xs space-y-2">
                    <span class="font-bold uppercase tracking-wider text-[10px] text-purple-600 dark:text-purple-400 block">⚡ Speech to Speech</span>
                    <p class="text-gray-600 dark:text-gray-300">Record or upload speech to translate languages and re-synthesize in real-time with cloned voices.</p>
                </div>
            </div>
        </template>

        <!-- MAIN VIEWPORT -->
        <template #main>
            <!-- ── NEITHER CONFIGURED FALLBACK ── -->
            <div v-if="hasNeither" class="h-full flex flex-col items-center justify-center text-center p-8">
                <div class="w-20 h-20 bg-gray-100 dark:bg-gray-800 rounded-3xl flex items-center justify-center mb-6 shadow-inner text-gray-300">
                    <IconMicrophone class="w-10 h-10" />
                </div>
                <h2 class="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tight mb-2">Voices Studio Inactive</h2>
                <p class="text-sm text-gray-500 max-w-md mb-8">
                    To use Voice Synthesis or Transcription, configure an active <strong>TTS</strong> or <strong>STT</strong> binding in system settings.
                </p>
                <router-link to="/settings" class="btn btn-primary px-8 py-3 rounded-2xl shadow-xl">
                    Configure Voice Bindings
                </router-link>
            </div>

            <!-- ── MODE 1: TTS VOICE SYNTHESIS & CUSTOMIZATION ── -->
            <div v-else-if="isTtsActive && activeMode === 'tts'" class="h-full flex flex-col overflow-hidden">
                <!-- Add Voice Form -->
                <div v-if="isAddFormVisible" class="p-6 h-full overflow-y-auto">
                    <div class="bg-white dark:bg-gray-800 p-6 rounded-2xl border dark:border-gray-700 shadow-xl space-y-6 max-w-3xl mx-auto">
                        <div class="flex items-center justify-between border-b dark:border-gray-700 pb-3">
                            <h3 class="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                                <span>🎙️</span>
                                <span>Add New Custom Voice Profile</span>
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
                                <h4 class="font-bold text-xs uppercase tracking-widest text-primary">Audio Reference Source</h4>
                                <p class="text-xs text-gray-500">Provide 5-15 seconds of clear, noise-free speech for neural cloning.</p>
                                <div class="flex flex-col sm:flex-row items-center gap-4 pt-1">
                                    <button type="button" @click="isRecording ? stopRecording() : startRecording()" class="btn btn-secondary w-full sm:w-auto" :class="{'bg-red-500 text-white hover:bg-red-600 animate-pulse': isRecording}">
                                        <IconStopCircle v-if="isRecording" class="w-4 h-4 mr-2" />
                                        <IconMicrophone v-else class="w-4 h-4 mr-2" />
                                        {{ isRecording ? 'Stop Recording' : 'Record from Microphone' }}
                                    </button>
                                    <span class="text-xs font-bold text-gray-400 uppercase">OR</span>
                                    <input type="file" @change="handleNewFileChange" class="input-field-file text-xs" accept="audio/wav,audio/mpeg,audio/x-wav,audio/ogg">
                                </div>
                                <div v-if="recordedAudioUrl" class="mt-3 p-3 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-600">
                                    <span class="text-[10px] font-bold text-gray-400 uppercase block mb-1">Audio Reference Preview</span>
                                    <audio :src="recordedAudioUrl" controls class="w-full h-8"></audio>
                                </div>
                            </div>
                            <div class="flex justify-end gap-3 pt-2">
                                <button type="button" @click="cancelAddForm" class="btn btn-secondary">Cancel</button>
                                <button type="submit" class="btn btn-primary" :disabled="isSubmittingNew || isRecording">
                                    <IconAnimateSpin v-if="isSubmittingNew" class="w-4 h-4 mr-2 animate-spin" />
                                    <span>{{ isSubmittingNew ? 'Processing Voice...' : 'Save Voice Profile' }}</span>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- Active Voice Editor -->
                <VoiceEditor v-else-if="selectedVoice" :key="selectedVoice.id" :voice-id="selectedVoice.id" :voice-data="selectedVoice" @updated="voicesStore.fetchVoices" />

                <!-- Empty Voice Selection Prompt -->
                <div v-else class="h-full flex flex-col items-center justify-center text-center p-8">
                    <div class="w-16 h-16 bg-blue-50 dark:bg-blue-900/30 text-blue-500 rounded-2xl flex items-center justify-center mb-4">
                        <IconSpeakerWave class="w-8 h-8" />
                    </div>
                    <h3 class="text-lg font-bold text-gray-900 dark:text-white uppercase tracking-tight">Voice Synthesis Studio</h3>
                    <p class="text-xs text-gray-500 max-w-sm mt-1 mb-6">
                        Select a voice profile from the sidebar to inspect waveforms and customize pitch, cadence, and spatial reverb.
                    </p>
                    <button @click="showAddForm" class="btn btn-primary btn-sm flex items-center gap-2">
                        <IconPlus class="w-4 h-4" />
                        <span>Create New Voice</span>
                    </button>
                </div>
            </div>

            <!-- ── MODE 2: STT TRANSCRIPTION STUDIO ── -->
            <div v-else-if="isSttActive && activeMode === 'stt'" class="p-6 h-full overflow-y-auto">
                <div class="max-w-4xl mx-auto space-y-6">
                    <div class="bg-white dark:bg-gray-800 p-6 rounded-2xl border dark:border-gray-700 shadow-md space-y-4">
                        <div class="flex items-center justify-between border-b dark:border-gray-700 pb-3">
                            <div>
                                <h3 class="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                                    <IconMicrophone class="w-5 h-5 text-blue-500" />
                                    <span>Speech-to-Text Neural Transcription</span>
                                </h3>
                                <p class="text-xs text-gray-500">Record from your microphone or upload audio files to transcribe into clean text.</p>
                            </div>
                        </div>

                        <!-- Action Controls -->
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <!-- Mic Stream -->
                            <div class="p-5 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700 flex flex-col items-center justify-center text-center space-y-3">
                                <span class="text-xs font-bold uppercase tracking-wider text-gray-400">Microphone Input</span>
                                <button @click="toggleSttRecording" class="btn btn-sm w-full py-2.5 flex items-center justify-center gap-2" :class="isRecordingForStt ? 'btn-danger animate-pulse' : 'btn-primary'" :disabled="isTranscribing">
                                    <IconStopCircle v-if="isRecordingForStt" class="w-4 h-4" />
                                    <IconMicrophone v-else class="w-4 h-4" />
                                    <span>{{ isRecordingForStt ? 'Stop & Transcribe' : 'Start Recording' }}</span>
                                </button>
                                <span v-if="isRecordingForStt" class="text-[10px] text-red-500 font-bold uppercase tracking-widest animate-pulse">Recording audio stream...</span>
                            </div>

                            <!-- File Upload -->
                            <div class="p-5 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700 flex flex-col items-center justify-center text-center space-y-3">
                                <span class="text-xs font-bold uppercase tracking-wider text-gray-400">Upload Audio File</span>
                                <label class="btn btn-secondary btn-sm w-full py-2.5 flex items-center justify-center gap-2 cursor-pointer" :class="{'opacity-50 pointer-events-none': isTranscribing}">
                                    <IconArrowUpTray class="w-4 h-4" />
                                    <span>Select Audio File</span>
                                    <input type="file" @change="handleSttFileUpload" class="hidden" accept="audio/*,.wav,.mp3,.ogg,.m4a">
                                </label>
                                <span class="text-[10px] text-gray-400">Supports WAV, MP3, OGG, M4A</span>
                            </div>
                        </div>

                        <!-- Progress State -->
                        <div v-if="isTranscribing" class="p-6 bg-blue-50/50 dark:bg-blue-900/20 rounded-xl border border-blue-100 dark:border-blue-900/40 text-center space-y-2 animate-in fade-in">
                            <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin mx-auto" />
                            <p class="text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-widest">Neural Transcription in progress...</p>
                        </div>

                        <!-- Output Viewer -->
                        <div v-if="transcribedText" class="space-y-3 pt-2 animate-in fade-in">
                            <div class="flex items-center justify-between">
                                <span class="text-xs font-black uppercase tracking-widest text-primary">Transcript Output</span>
                                <div class="flex gap-2">
                                    <button @click="copyTranscription" class="btn btn-secondary btn-xs flex items-center gap-1.5">
                                        <IconCopy class="w-3.5 h-3.5" /> Copy
                                    </button>
                                    <button @click="downloadTranscription" class="btn btn-secondary btn-xs flex items-center gap-1.5">
                                        <IconArrowDownTray class="w-3.5 h-3.5" /> Download .txt
                                    </button>
                                </div>
                            </div>
                            <div class="p-4 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-700 text-sm leading-relaxed whitespace-pre-wrap font-sans text-gray-800 dark:text-gray-200">
                                {{ transcribedText }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ── MODE 3: AUDIO-TO-AUDIO TRANSLATION STUDIO (BOTH ACTIVE) ── -->
            <div v-else-if="hasBoth && activeMode === 'translation'" class="p-6 h-full overflow-y-auto">
                <div class="max-w-4xl mx-auto space-y-6">
                    <div class="bg-white dark:bg-gray-800 p-6 rounded-2xl border dark:border-gray-700 shadow-md space-y-6">
                        <div class="border-b dark:border-gray-700 pb-3">
                            <h3 class="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                                <span class="text-xl">⚡</span>
                                <span>Speech-to-Speech & Real-Time Voice Translation</span>
                            </h3>
                            <p class="text-xs text-gray-500">Record or upload foreign speech to transcribe, translate via LLM, and synthesize back in your chosen cloned voice.</p>
                        </div>

                        <!-- 1. Input Audio Source -->
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
                            <span class="text-[10px] font-bold text-gray-400 uppercase">Input Audio Stream</span>
                            <audio :src="s2sSourceAudioUrl" controls class="w-full h-8"></audio>
                        </div>

                        <!-- 2. Target Configuration -->
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
                                <span class="text-xs font-medium text-gray-700 dark:text-gray-300">Translate Text via Neural LLM (uncheck for pure voice conversion/dubbing)</span>
                                <input type="checkbox" v-model="s2sTranslateText" class="h-4 w-4 rounded text-purple-600 focus:ring-purple-500">
                            </div>
                        </div>

                        <!-- 3. Pipeline Trigger -->
                        <div class="flex justify-end">
                            <button @click="executeAudioToAudio" :disabled="isProcessingS2S || !s2sSourceAudioBlob" class="btn btn-primary px-8 py-3 rounded-xl shadow-lg flex items-center gap-2">
                                <IconAnimateSpin v-if="isProcessingS2S" class="w-5 h-5 animate-spin" />
                                <IconSparkles v-else class="w-5 h-5" />
                                <span>{{ isProcessingS2S ? 'Running Neural Pipeline...' : 'Process Audio to Audio' }}</span>
                            </button>
                        </div>

                        <!-- 4. Result Showcase -->
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
                                <div class="flex items-center justify-between">
                                    <span class="text-xs font-black uppercase tracking-wider text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                                        <IconCheckCircle class="w-4 h-4" /> Synthesized Translated Audio Stream
                                    </span>
                                    <button @click="downloadS2SOutput" class="btn btn-secondary btn-xs flex items-center gap-1.5">
                                        <IconArrowDownTray class="w-3.5 h-3.5" /> Download (.wav)
                                    </button>
                                </div>
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