<template>
    <PageViewLayout title="Voices Studio" :title-icon="IconMicrophone">
        <template #sidebar>
            <div class="h-full flex flex-col min-h-0">
                <button @click="showAddForm" class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/50 transition-colors flex-shrink-0">
                    <IconPlus class="w-5 h-5 flex-shrink-0" />
                    <span>New Voice</span>
                </button>
            
                <div class="mt-4 flex-shrink-0">
                    <h3 class="text-sm font-semibold uppercase text-gray-500 dark:text-gray-400 px-3">Your Voices</h3>
                </div>
                
                <div class="overflow-y-auto custom-scrollbar flex-grow mt-2">
                    <div v-if="isLoading" class="p-4 text-center">Loading...</div>
                    <ul v-else class="space-y-1">
                        <li v-for="voice in voices" :key="voice.id">
                            <div class="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors group flex justify-between items-center"
                                 :class="{'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': selectedVoiceId === voice.id && !isAddFormVisible, 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700': selectedVoiceId !== voice.id || isAddFormVisible}">
                                <button @click="selectVoice(voice.id)" class="flex-grow text-left truncate">
                                    {{ voice.alias }}
                                </button>
                                 <div class="flex items-center flex-shrink-0">
                                    <span v-if="user && user.active_voice_id === voice.id" class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300">Active</span>
                                    <div class="flex items-center opacity-0 group-hover:opacity-100 transition-opacity ml-2">
                                        <button @click="selectVoice(voice.id)" title="Edit" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md"><IconPencil class="w-4 h-4" /></button>
                                        <button @click="handleDeleteVoice(voice)" title="Delete" class="p-1 hover:bg-red-100 dark:hover:bg-red-900/50 text-red-500 rounded-md"><IconTrash class="w-4 h-4" /></button>
                                    </div>
                                </div>
                            </div>
                        </li>
                    </ul>
                </div>
            </div>
        </template>
        <template #main>
            <div v-if="isAddFormVisible" class="p-6 h-full overflow-y-auto">
                <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md space-y-6 max-w-3xl mx-auto">
                    <h3 class="text-xl font-semibold">Add a New Voice</h3>
                    <form @submit.prevent="handleAddNewVoice" class="space-y-4">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div><label for="alias-new" class="block text-sm font-medium">Alias</label><input type="text" id="alias-new" v-model="newVoiceForm.alias" class="input-field mt-1" required></div>
                            <div><label for="language-new" class="block text-sm font-medium">Language (e.g., en, fr)</label><input type="text" id="language-new" v-model="newVoiceForm.language" class="input-field mt-1" required></div>
                        </div>
                        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                            <h4 class="font-medium mb-3">Audio Source</h4>
                            <div class="flex flex-col sm:flex-row items-center gap-4">
                                <button type="button" @click="isRecording ? stopRecording() : startRecording()" class="btn btn-secondary w-full sm:w-auto" :class="{'bg-red-500 text-white hover:bg-red-600': isRecording}"><IconMicrophone class="w-5 h-5 mr-2"/>{{ isRecording ? 'Stop Recording' : 'Record from Mic' }}</button>
                                <span class="text-sm text-gray-500">OR</span>
                                <input type="file" id="file-new" @change="handleNewFileChange" class="input-field-file" accept="audio/wav,audio/mpeg">
                            </div>
                            <div v-if="isRecording" class="text-center text-red-500 font-semibold animate-pulse mt-3">Recording...</div>
                            <div v-if="recordedAudioUrl" class="mt-4"><h5 class="text-sm font-medium mb-2">Audio Preview</h5><audio :src="recordedAudioUrl" controls class="w-full"></audio></div>
                        </div>
                        <div class="flex justify-end gap-3">
                            <button type="button" @click="cancelAddForm" class="btn btn-secondary">Cancel</button>
                            <button type="submit" class="btn btn-primary" :disabled="isSubmittingNew || isRecording">{{ isSubmittingNew ? 'Saving...' : 'Save Voice' }}</button>
                        </div>
                    </form>
                </div>
            </div>
            <VoiceEditor v-else-if="selectedVoice" :key="selectedVoice.id" :voice-id="selectedVoice.id" :voice-data="selectedVoice" />
            <div v-else class="h-full flex flex-col items-center justify-center text-center p-6">
                <IconMicrophone class="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4" />
                <h3 class="text-xl font-semibold text-gray-700 dark:text-gray-200">Welcome to the Voices Studio</h3>
                <p class="mt-2 text-gray-500 dark:text-gray-400">Select a voice from the sidebar to edit, or create a new one.</p>
            </div>
        </template>
    </PageViewLayout>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useVoicesStore } from '../stores/voices';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import VoiceEditor from '../components/voices/VoiceEditor.vue';
import IconMicrophone from '../assets/icons/IconMicrophone.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconTrash from '../assets/icons/IconTrash.vue';

const voicesStore = useVoicesStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

const { voices, isLoading } = storeToRefs(voicesStore);
const { user } = storeToRefs(authStore);

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
    newVoiceForm.value.file = event.target.files[0] || null;
    recordedAudioUrl.value = URL.createObjectURL(newVoiceForm.value.file);
    recordedAudioBlob.value = newVoiceForm.value.file;
}

async function startRecording() {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder.value = new MediaRecorder(stream);
            audioChunks.value = [];
            mediaRecorder.value.ondataavailable = event => {
                audioChunks.value.push(event.data);
            };
            mediaRecorder.value.onstop = () => {
                recordedAudioBlob.value = new Blob(audioChunks.value, { type: 'audio/wav' });
                recordedAudioUrl.value = URL.createObjectURL(recordedAudioBlob.value);
            };
            mediaRecorder.value.start();
            isRecording.value = true;
        } catch (err) {
            uiStore.addNotification('Microphone access denied or not available.', 'error');
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
            uiStore.addNotification('An audio file or recording is required.', 'warning');
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
        confirmText: 'Delete'
    });
    if (confirmed) {
        await voicesStore.deleteVoice(voice.id);
        if (selectedVoiceId.value === voice.id) {
            selectedVoiceId.value = null;
        }
    }
}

watch(voices, (newVoices) => {
    if (selectedVoiceId.value && !newVoices.some(v => v.id === selectedVoiceId.value)) {
        selectedVoiceId.value = null;
    }
}, { deep: true });

onMounted(() => {
    voicesStore.fetchVoices();
});
</script>