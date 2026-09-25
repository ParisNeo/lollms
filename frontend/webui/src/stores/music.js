// frontend/webui/src/stores/music.js
import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks';

export const useMusicStore = defineStore('music', () => {
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();

    // Studio Settings & Form State
    const activeTab = ref('simple'); // 'simple' | 'studio'
    const prompt = ref('a rap song about love');
    const lyrics = ref(`[intro]
Check one two, check
Listen close

[verse]
Midnight stories, secrets told
Your hand in mine, we're bold
Through the storm, we'll never fold
Our love is worth more than gold

[chorus]
I'm in love with you, so true
I'm in love, I'm in love with you
I'm in love with you, I'll pursue
My whole life I will give to you

[outro]
Fading in the morning glow
Never letting go`);

    const globalMetadata = ref('Basic Attributes: bpm is 92. key is F, and scale is major. Contemporary Rap / Hip-Hop Love Ballad. Global Emotional Progression: Opens reflective and intimate in the verse, builds tension in the pre-chorus, erupts euphoric in the chorus, turns vulnerable in the second verse.');
    const vocalDetails = ref('Vocal Gender & Timbre: Singer A (Male), smooth tenor with slight rasp. Vocal Style: Conversational in verses, melodic in pre-chorus, emphatic rhythmic in chorus.');
    const arrangement = ref('Primary: drum machine, bass synth, electric piano. Secondary: pads in pre-chorus, lead synth and strings in chorus.');
    const duration = ref(60);
    const instrumental = ref(false);
    const selectedModel = ref(null);

    // Audio & Tracks State
    const tracks = ref([]);
    const isLoadingTracks = ref(false);
    const isGenerating = ref(false);
    const isWritingLyrics = ref(false);
    const isWritingPrompt = ref(false);

    // Player State
    const currentTrack = ref(null);
    const isPlaying = ref(false);
    const audioPlayer = ref(null);
    const currentTime = ref(0);
    const totalDuration = ref(0);

    async function fetchTracks() {
        isLoadingTracks.value = true;
        try {
            const res = await apiClient.get('/api/music-studio/tracks');
            tracks.value = Array.isArray(res.data) ? res.data : [];
            if (!currentTrack.value && tracks.value.length > 0) {
                currentTrack.value = tracks.value[0];
            }
        } catch (e) {
            console.error("Failed to load tracks:", e);
        } finally {
            isLoadingTracks.value = false;
        }
    }

    async function generateSong() {
        isGenerating.value = true;
        try {
            const payload = {
                title: prompt.value.substring(0, 40) || 'My Song',
                prompt: prompt.value,
                lyrics: instrumental.value ? '' : lyrics.value,
                duration: Number(duration.value),
                instrumental: instrumental.value,
                global_metadata: globalMetadata.value,
                vocal_details: vocalDetails.value,
                arrangement: arrangement.value,
                model: selectedModel.value
            };

            const res = await apiClient.post('/api/music-studio/generate', payload);
            const task = res.data;
            tasksStore.addTask(task);
            uiStore.addNotification("Music generation started in background!", "success");
            return task;
        } catch (e) {
            uiStore.addNotification(e.response?.data?.detail || "Failed to start song generation.", "error");
            throw e;
        } finally {
            isGenerating.value = false;
        }
    }

    async function writeLyricsWithAi(customDesc = null) {
        isWritingLyrics.value = true;
        try {
            const desc = customDesc || prompt.value;
            const res = await apiClient.post('/api/music-studio/write-lyrics', {
                description: desc,
                current_lyrics: lyrics.value
            });
            if (res.data?.lyrics) {
                lyrics.value = res.data.lyrics;
                uiStore.addNotification("Structured lyrics generated!", "success");
            }
        } catch (e) {
            uiStore.addNotification("Failed to write lyrics with AI.", "error");
        } finally {
            isWritingLyrics.value = false;
        }
    }

    async function writePromptWithAi(customDesc = null) {
        isWritingPrompt.value = true;
        try {
            const desc = customDesc || prompt.value;
            const res = await apiClient.post('/api/music-studio/write-prompt', {
                description: desc,
                lyrics: lyrics.value
            });
            if (res.data) {
                if (res.data.global_metadata) globalMetadata.value = res.data.global_metadata;
                if (res.data.vocal_details) vocalDetails.value = res.data.vocal_details;
                if (res.data.arrangement) arrangement.value = res.data.arrangement;
                uiStore.addNotification("Structured sound prompts written!", "success");
            }
        } catch (e) {
            uiStore.addNotification("Failed to write sound prompt with AI.", "error");
        } finally {
            isWritingPrompt.value = false;
        }
    }

    async function expandIdeaAndSwitchToStudio() {
        isWritingLyrics.value = true;
        try {
            const res = await apiClient.post('/api/music-studio/expand-idea', {
                idea: prompt.value,
                instrumental: instrumental.value
            });
            if (res.data) {
                if (res.data.lyrics) lyrics.value = res.data.lyrics;
                if (res.data.global_metadata) globalMetadata.value = res.data.global_metadata;
                if (res.data.vocal_details) vocalDetails.value = res.data.vocal_details;
                if (res.data.arrangement) arrangement.value = res.data.arrangement;
                activeTab.value = 'studio';
                uiStore.addNotification("Idea expanded into full Studio setup! Review and tweak.", "success");
            }
        } catch (e) {
            uiStore.addNotification("Failed to expand idea.", "error");
        } finally {
            isWritingLyrics.value = false;
        }
    }

    async function deleteTrack(trackId) {
        const confirmed = await uiStore.showConfirmation({
            title: "Delete Track",
            message: "Permanently delete this song and its audio file?",
            confirmText: "Delete",
            danger: true
        });
        if (!confirmed.confirmed) return;

        try {
            await apiClient.delete(`/api/music-studio/tracks/${trackId}`);
            tracks.value = tracks.value.filter(t => t.id !== trackId);
            if (currentTrack.value?.id === trackId) {
                currentTrack.value = tracks.value[0] || null;
            }
            uiStore.addNotification("Track deleted.", "info");
        } catch (e) {
            uiStore.addNotification("Failed to delete track.", "error");
        }
    }

    function selectTrack(track) {
        currentTrack.value = track;
    }

    return {
        activeTab,
        prompt,
        lyrics,
        globalMetadata,
        vocalDetails,
        arrangement,
        duration,
        instrumental,
        selectedModel,
        tracks,
        isLoadingTracks,
        isGenerating,
        isWritingLyrics,
        isWritingPrompt,
        currentTrack,
        isPlaying,
        audioPlayer,
        currentTime,
        totalDuration,
        fetchTracks,
        generateSong,
        writeLyricsWithAi,
        writePromptWithAi,
        expandIdeaAndSwitchToStudio,
        deleteTrack,
        selectTrack
    };
});