<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useMusicStore } from '../stores/music';
import { useTasksStore } from '../stores/tasks';
import { useUiStore } from '../stores/ui';

import IconMusicalNote from '../assets/icons/IconMusicalNote.vue';
import IconPlayCircle from '../assets/icons/IconPlayCircle.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconStopCircle from '../assets/icons/IconStopCircle.vue';

const musicStore = useMusicStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();

const { 
    activeTab, prompt, lyrics, globalMetadata, vocalDetails, arrangement,
    duration, instrumental, tracks, isLoadingTracks, isGenerating,
    isWritingLyrics, isWritingPrompt, currentTrack
} = storeToRefs(musicStore);

const customLyricsPrompt = ref('');
const customSoundPrompt = ref('');
const audioPlayerRef = ref(null);
const isAudioPlaying = ref(false);
const audioCurrentTime = ref(0);
const audioDuration = ref(0);
const isRecordingVideo = ref(false);

const visualizerCanvasRef = ref(null);
let animationFrameId = null;
let audioContext = null;
let analyserNode = null;
let audioSourceNode = null;

const promptPresets = [
    "a smoky late-night soul ballad about old flames, warm female voice",
    "a defiant punk anthem about staying up too late",
    "a cozy lo-fi hip hop beat for studying, no vocals",
    "an upbeat 80s synth-pop track about neon city nights, punchy drums",
    "an ethereal celtic acoustic folk song with delicate acoustic guitar"
];

const sectionTags = [
    "[intro]", "[verse]", "[pre-chorus]", "[chorus]",
    "[post-chorus]", "[bridge]", "[instrumental]", "[solo]", "[outro]"
];

function insertSectionTag(tag) {
    if (!lyrics.value) {
        lyrics.value = `${tag}\n`;
        return;
    }
    const endsWithNewline = lyrics.value.endsWith('\n');
    lyrics.value += (endsWithNewline ? '' : '\n\n') + `${tag}\n`;
}

function applyPreset(p) {
    prompt.value = p;
    if (p.includes("no vocals") || p.includes("lo-fi")) {
        instrumental.value = true;
    }
}

function setupAudioVisualizer() {
    if (!audioPlayerRef.value || !visualizerCanvasRef.value) return;

    if (!audioContext) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioContextClass();
        analyserNode = audioContext.createAnalyser();
        analyserNode.fftSize = 64;

        try {
            audioSourceNode = audioContext.createMediaElementSource(audioPlayerRef.value);
            audioSourceNode.connect(analyserNode);
            analyserNode.connect(audioContext.destination);
        } catch (e) {
            // Context connection fallback
        }
    }

    drawVisualizer();
}

function drawVisualizer() {
    const canvas = visualizerCanvasRef.value;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    const bufferLength = analyserNode ? analyserNode.frequencyBinCount : 32;
    const dataArray = new Uint8Array(bufferLength);

    const render = () => {
        animationFrameId = requestAnimationFrame(render);

        if (analyserNode && isAudioPlaying.value) {
            analyserNode.getByteFrequencyData(dataArray);
        } else {
            for (let i = 0; i < bufferLength; i++) {
                dataArray[i] = Math.max(10, Math.sin(Date.now() / 600 + i * 0.4) * 45 + 50);
            }
        }

        ctx.fillStyle = '#0b0b0b';
        ctx.fillRect(0, 0, width, height);

        const barCount = 28;
        const barWidth = 6;
        const gap = 8;
        const totalW = barCount * (barWidth + gap) - gap;
        const startX = (width - totalW) / 2;

        for (let i = 0; i < barCount; i++) {
            const rawVal = dataArray[i % bufferLength] || 20;
            const barHeight = Math.max(12, (rawVal / 255) * (height * 0.58));
            const x = startX + i * (barWidth + gap);
            const y = (height - barHeight) / 2;

            const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
            grad.addColorStop(0, '#ffcc00');
            grad.addColorStop(1, '#ff8800');

            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.roundRect(x, y, barWidth, barHeight, 3);
            ctx.fill();
        }

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 22px system-ui, -apple-system, sans-serif';
        ctx.textAlign = 'center';
        const displayTitle = (currentTrack.value?.title || prompt.value || 'MiniMax Song').substring(0, 35);
        ctx.fillText(displayTitle, width / 2, 55);

        ctx.fillStyle = '#ffaa00';
        ctx.font = 'bold 16px system-ui, -apple-system, sans-serif';
        ctx.fillText('MiniMax Music 3', width / 2, height - 42);

        ctx.fillStyle = '#777777';
        ctx.font = '12px system-ui, -apple-system, sans-serif';
        ctx.fillText('made with diffusers & lollms', width / 2, height - 22);
    };

    render();
}

function toggleAudio() {
    if (!audioPlayerRef.value) return;
    if (audioContext && audioContext.state === 'suspended') {
        audioContext.resume();
    }
    if (isAudioPlaying.value) {
        audioPlayerRef.value.pause();
    } else {
        audioPlayerRef.value.play();
    }
}

function onAudioTimeUpdate() {
    if (audioPlayerRef.value) {
        audioCurrentTime.value = audioPlayerRef.value.currentTime;
        audioDuration.value = audioPlayerRef.value.duration || 0;
    }
}

function formatSecs(secs) {
    if (!secs || isNaN(secs)) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}

async function exportWaveformVideo() {
    if (!visualizerCanvasRef.value || !audioPlayerRef.value) return;
    const canvas = visualizerCanvasRef.value;
    const audio = audioPlayerRef.value;

    isRecordingVideo.value = true;
    uiStore.addNotification("Recording visualizer video...", "info");

    try {
        const stream = canvas.captureStream(30);

        if (audio.captureStream) {
            const audioStream = audio.captureStream();
            audioStream.getAudioTracks().forEach(t => stream.addTrack(t));
        } else if (audio.mozCaptureStream) {
            const audioStream = audio.mozCaptureStream();
            audioStream.getAudioTracks().forEach(t => stream.addTrack(t));
        }

        const recorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
        const chunks = [];
        recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
        recorder.onstop = () => {
            const blob = new Blob(chunks, { type: 'video/webm' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${currentTrack.value?.title || 'minimax_song'}_visualizer.webm`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            uiStore.addNotification("Visualizer video exported!", "success");
            isRecordingVideo.value = false;
        };

        audio.currentTime = 0;
        await audio.play();
        recorder.start();

        const recordDuration = Math.min(audio.duration || 10, 15) * 1000;
        setTimeout(() => {
            recorder.stop();
            audio.pause();
        }, recordDuration);

    } catch (e) {
        console.error("Video export failed:", e);
        uiStore.addNotification("Could not record video directly.", "error");
        isRecordingVideo.value = false;
    }
}

const activeMusicTasks = computed(() => {
    return tasksStore.tasks.filter(t => 
        (t.name.includes("Generate Song") || t.name.includes("Music")) && 
        (t.status === 'running' || t.status === 'pending')
    );
});

watch(() => tasksStore.tasks, (newTasks) => {
    const finishedSongTask = newTasks.find(t => 
        t.name.includes("Generate Song") && t.status === 'completed' && !t._processed_for_music
    );
    if (finishedSongTask) {
        finishedSongTask._processed_for_music = true;
        musicStore.fetchTracks();
        uiStore.addNotification("Your song is ready to play!", "success");
    }
}, { deep: true });

onMounted(() => {
    musicStore.fetchTracks();
    setupAudioVisualizer();
});
</script>

<template>
  <div class="h-full flex flex-col bg-gray-50 dark:bg-gray-950 overflow-y-auto custom-scrollbar">
    
    <!-- Top Banner & Header -->
    <div class="border-b border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md px-6 py-4 shrink-0">
        <div class="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-4">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-amber-500 to-yellow-400 flex items-center justify-center text-white shadow-lg shadow-amber-500/20">
                    <IconMusicalNote class="w-6 h-6" />
                </div>
                <div>
                    <h1 class="text-xl font-black text-gray-900 dark:text-white flex items-center gap-2">
                        <span>MiniMax Music 3</span>
                        <span class="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 font-bold border border-amber-200 dark:border-amber-800">
                            Studio
                        </span>
                    </h1>
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                        Full-length song generation with expressive vocals, lyrics arrangement, and structured production.
                    </p>
                </div>
            </div>

            <!-- Active Task Pill -->
            <div v-if="activeMusicTasks.length > 0" class="flex items-center gap-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 px-4 py-2 rounded-2xl shadow-xs">
                <IconAnimateSpin class="w-4 h-4 text-amber-600 animate-spin" />
                <span class="text-xs font-bold text-amber-800 dark:text-amber-200">{{ activeMusicTasks[0].description }}</span>
            </div>
        </div>
    </div>

    <!-- Main Workspace Container -->
    <div class="max-w-7xl mx-auto w-full p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 grow">
        
        <!-- LEFT COLUMN: CREATOR WORKBENCH -->
        <div class="lg:col-span-7 flex flex-col gap-5">
            
            <!-- Mode Switcher -->
            <div class="flex items-center justify-between bg-white dark:bg-gray-900 p-2 rounded-2xl border border-gray-200 dark:border-gray-800 shadow-xs">
                <div class="flex items-center gap-1.5 p-1 bg-gray-100 dark:bg-gray-800 rounded-xl">
                    <button 
                        @click="activeTab = 'simple'" 
                        class="px-5 py-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all cursor-pointer"
                        :class="activeTab === 'simple' ? 'bg-amber-500 text-white shadow-md' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'"
                    >
                        Simple
                    </button>
                    <button 
                        @click="activeTab = 'studio'" 
                        class="px-5 py-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all cursor-pointer"
                        :class="activeTab === 'studio' ? 'bg-amber-500 text-white shadow-md' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'"
                    >
                        Studio
                    </button>
                </div>
                <span class="text-xs text-gray-400 italic pr-3 font-serif">
                    {{ activeTab === 'simple' ? 'a full song from a one-line idea' : 'lyrics + structured caption, full control' }}
                </span>
            </div>

            <!-- TAB 1: SIMPLE MODE -->
            <div v-if="activeTab === 'simple'" class="bg-white dark:bg-gray-900 p-6 rounded-3xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-5">
                <div>
                    <label class="block text-xs font-black uppercase tracking-wider text-gray-400 mb-2">Song Concept / Style Idea</label>
                    <textarea 
                        v-model="prompt"
                        rows="3"
                        class="input-field w-full text-sm leading-relaxed resize-none p-3.5"
                        placeholder="e.g. a rap song about love, emotional 80s synth ballad, cheerful pop punk..."
                    ></textarea>
                </div>

                <!-- Inspiration Presets -->
                <div class="space-y-1.5">
                    <span class="text-[10px] font-black uppercase tracking-wider text-gray-400">Inspiration Presets:</span>
                    <div class="flex flex-wrap gap-2">
                        <button 
                            v-for="p in promptPresets" 
                            :key="p"
                            type="button"
                            @click="applyPreset(p)"
                            class="px-3 py-1.5 rounded-full text-xs font-medium bg-amber-50/80 hover:bg-amber-100 text-amber-900 dark:bg-amber-950/40 dark:hover:bg-amber-900/50 dark:text-amber-200 border border-amber-200/80 dark:border-amber-800/60 transition-all text-left cursor-pointer active:scale-98"
                        >
                            {{ p }}
                        </button>
                    </div>
                </div>

                <!-- Instrumental Toggle & Actions Row -->
                <div class="pt-2 flex items-center justify-between flex-wrap gap-4 border-t dark:border-gray-800">
                    <label class="flex items-center gap-2.5 cursor-pointer select-none">
                        <input type="checkbox" v-model="instrumental" class="rounded text-amber-500 focus:ring-amber-500 h-4 w-4 bg-transparent border-gray-300 dark:border-gray-700" />
                        <span class="text-xs font-bold text-gray-700 dark:text-gray-300">Instrumental Only (No Vocals)</span>
                    </label>

                    <div class="flex items-center gap-3">
                        <button 
                            type="button"
                            @click="musicStore.expandIdeaAndSwitchToStudio" 
                            :disabled="isWritingLyrics"
                            class="btn btn-secondary btn-sm flex items-center gap-1.5 font-bold"
                        >
                            <IconAnimateSpin v-if="isWritingLyrics" class="w-3.5 h-3.5 animate-spin" />
                            <IconSparkles v-else class="w-3.5 h-3.5 text-amber-500" />
                            <span>Write lyrics & review</span>
                        </button>

                        <button 
                            type="button" 
                            @click="musicStore.generateSong" 
                            :disabled="isGenerating || activeMusicTasks.length > 0"
                            class="btn btn-primary btn-sm px-6 py-2.5 rounded-xl flex items-center gap-2 shadow-lg shadow-amber-500/20 bg-amber-500 hover:bg-amber-600 border-none text-white font-black uppercase text-xs tracking-wider cursor-pointer"
                        >
                            <IconAnimateSpin v-if="isGenerating" class="w-4 h-4 animate-spin" />
                            <IconMusicalNote v-else class="w-4 h-4" />
                            <span>Generate</span>
                        </button>
                    </div>
                </div>

                <!-- Duration Slider Card -->
                <div class="p-4 bg-gray-50 dark:bg-gray-800/40 rounded-2xl border dark:border-gray-800 space-y-2">
                    <div class="flex items-center justify-between text-xs">
                        <span class="font-bold text-gray-700 dark:text-gray-300">Maximum song duration (seconds)</span>
                        <div class="flex items-center gap-2">
                            <input type="number" v-model.number="duration" min="5" max="300" class="input-field !py-0.5 !px-2 text-xs font-mono font-bold w-16 text-center" />
                            <button @click="duration = 60" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200" title="Reset to 60s">
                                <IconRefresh class="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                    <input type="range" v-model.number="duration" min="5" max="300" step="5" class="w-full accent-amber-500 h-1.5 rounded-lg cursor-pointer" />
                    <div class="flex justify-between text-[10px] text-gray-400 font-mono">
                        <span>5s</span>
                        <span>300s (5 mins)</span>
                    </div>
                </div>
            </div>

            <!-- TAB 2: STUDIO PRO MODE -->
            <div v-else-if="activeTab === 'studio'" class="space-y-5">
                
                <!-- Lyrics Workshop -->
                <div class="bg-white dark:bg-gray-900 p-6 rounded-3xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-4">
                    <div class="flex items-center justify-between">
                        <h3 class="text-xs font-black uppercase tracking-wider text-gray-400">Lyrics Workshop</h3>

                        <!-- Section Insertion Tags Row -->
                        <div class="flex items-center gap-1 flex-wrap">
                            <button 
                                v-for="tag in sectionTags" 
                                :key="tag"
                                type="button"
                                @click="insertSectionTag(tag)"
                                class="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-gray-100 hover:bg-amber-100 dark:bg-gray-800 dark:hover:bg-amber-950/60 text-gray-700 dark:text-gray-300 hover:text-amber-800 dark:hover:text-amber-300 border border-gray-200 dark:border-gray-700 transition-colors cursor-pointer"
                            >
                                {{ tag }}
                            </button>
                        </div>
                    </div>

                    <!-- AI Lyricist Bar -->
                    <div class="flex items-center gap-2 p-1.5 bg-amber-50/60 dark:bg-amber-950/30 rounded-2xl border border-amber-200/60 dark:border-amber-900/40">
                        <input 
                            v-model="customLyricsPrompt"
                            type="text" 
                            placeholder="Describe lyrics to write for you... e.g. nostalgic road-trip song, punchy one-line chorus"
                            class="grow bg-transparent border-none text-xs px-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:ring-0"
                            @keyup.enter="musicStore.writeLyricsWithAi(customLyricsPrompt)"
                        />
                        <button 
                            @click="musicStore.writeLyricsWithAi(customLyricsPrompt)"
                            :disabled="isWritingLyrics"
                            class="btn btn-secondary btn-xs shrink-0 text-amber-700 dark:text-amber-300 border-amber-300 font-bold flex items-center gap-1"
                        >
                            <IconAnimateSpin v-if="isWritingLyrics" class="w-3.5 h-3.5 animate-spin" />
                            <IconSparkles v-else class="w-3.5 h-3.5 text-amber-500" />
                            <span>Write</span>
                        </button>
                    </div>

                    <textarea 
                        v-model="lyrics"
                        rows="11"
                        class="input-field w-full font-mono text-xs leading-relaxed p-4 h-64 resize-y"
                        placeholder="[verse]&#10;Write your verses here...&#10;&#10;[chorus]&#10;Catchy melodic chorus..."
                    ></textarea>
                    
                    <p class="text-[10px] text-gray-400 italic">
                        Section tags sit <strong>alone on their own line</strong> — words on a tag line are dropped. Musical directions belong in Arrangement, never in the lyrics.
                    </p>
                </div>

                <!-- Structured Prompt Workbench -->
                <div class="bg-white dark:bg-gray-900 p-6 rounded-3xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-4">
                    <div class="flex items-center justify-between">
                        <h3 class="text-xs font-black uppercase tracking-wider text-gray-400">Structured Prompt Workbench</h3>
                    </div>

                    <!-- AI Prompt Architect Bar -->
                    <div class="flex items-center gap-2 p-1.5 bg-purple-50/60 dark:bg-purple-950/30 rounded-2xl border border-purple-200/60 dark:border-purple-900/40">
                        <input 
                            v-model="customSoundPrompt"
                            type="text" 
                            placeholder="Describe the sound to write for you... e.g. dreamy shoegaze, slow build, whispered female vocal"
                            class="grow bg-transparent border-none text-xs px-2 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:ring-0"
                            @keyup.enter="musicStore.writePromptWithAi(customSoundPrompt)"
                        />
                        <button 
                            @click="musicStore.writePromptWithAi(customSoundPrompt)"
                            :disabled="isWritingPrompt"
                            class="btn btn-secondary btn-xs shrink-0 text-purple-700 dark:text-purple-300 border-purple-300 font-bold flex items-center gap-1"
                        >
                            <IconAnimateSpin v-if="isWritingPrompt" class="w-3.5 h-3.5 animate-spin" />
                            <IconSparkles v-else class="w-3.5 h-3.5 text-purple-500" />
                            <span>Write</span>
                        </button>
                    </div>

                    <div class="space-y-4">
                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <label class="text-xs font-bold text-gray-700 dark:text-gray-200">Global metadata</label>
                                <span class="text-[10px] text-gray-400 font-mono">genre · BPM · key & scale · mood arc · scenario · production</span>
                            </div>
                            <textarea v-model="globalMetadata" rows="3" class="input-field w-full text-xs font-mono leading-relaxed p-3"></textarea>
                        </div>

                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <label class="text-xs font-bold text-gray-700 dark:text-gray-200">Vocal details</label>
                                <span class="text-[10px] text-gray-400 font-mono">gender · timbre · style per section · harmonies · effects</span>
                            </div>
                            <textarea v-model="vocalDetails" rows="3" class="input-field w-full text-xs font-mono leading-relaxed p-3"></textarea>
                        </div>

                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <label class="text-xs font-bold text-gray-700 dark:text-gray-200">Arrangement</label>
                                <span class="text-[10px] text-gray-400 font-mono">instruments per section · groove · bass · textures · spatial fx</span>
                            </div>
                            <textarea v-model="arrangement" rows="3" class="input-field w-full text-xs font-mono leading-relaxed p-3"></textarea>
                        </div>
                    </div>

                    <!-- Studio Action Bar -->
                    <div class="pt-4 border-t dark:border-gray-800 flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <span class="text-xs font-bold text-gray-500">Duration:</span>
                            <input type="number" v-model.number="duration" min="5" max="300" class="input-field !py-1 !px-2 text-xs font-mono font-bold w-16 text-center" />
                            <span class="text-xs text-gray-400 font-mono">seconds</span>
                        </div>

                        <button 
                            type="button" 
                            @click="musicStore.generateSong" 
                            :disabled="isGenerating || activeMusicTasks.length > 0"
                            class="btn btn-primary px-8 py-3 rounded-2xl flex items-center gap-2 shadow-xl shadow-amber-500/20 bg-amber-500 hover:bg-amber-600 border-none text-white font-black uppercase text-xs tracking-wider cursor-pointer"
                        >
                            <IconAnimateSpin v-if="isGenerating" class="w-4 h-4 animate-spin" />
                            <IconMusicalNote v-else class="w-4 h-4" />
                            <span>Generate Song</span>
                        </button>
                    </div>
                </div>

            </div>
        </div>

        <!-- RIGHT COLUMN: PLAYER, VIDEO VISUALIZER & PLAYLIST -->
        <div class="lg:col-span-5 flex flex-col gap-6">

            <!-- Audio Player Bar -->
            <div class="bg-white dark:bg-gray-900 p-5 rounded-3xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-4">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-black uppercase tracking-wider text-gray-400 flex items-center gap-2">
                        <IconMusicalNote class="w-4 h-4 text-amber-500" />
                        <span>Your Song</span>
                    </span>
                    <span v-if="currentTrack" class="text-xs font-mono text-gray-400">{{ formatSecs(audioCurrentTime) }} / {{ formatSecs(audioDuration) }}</span>
                </div>

                <audio 
                    ref="audioPlayerRef" 
                    :src="currentTrack ? currentTrack.audio_url : null"
                    @timeupdate="onAudioTimeUpdate"
                    @play="isAudioPlaying = true"
                    @pause="isAudioPlaying = false"
                    @ended="isAudioPlaying = false"
                    class="hidden"
                ></audio>

                <div class="flex items-center gap-4 bg-gray-50 dark:bg-gray-800/50 p-4 rounded-2xl border dark:border-gray-700/60">
                    <button 
                        @click="toggleAudio" 
                        :disabled="!currentTrack"
                        class="w-12 h-12 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white flex items-center justify-center shadow-lg shadow-amber-500/20 transition-all active:scale-95 disabled:opacity-40 cursor-pointer shrink-0"
                    >
                        <IconStopCircle v-if="isAudioPlaying" class="w-6 h-6" />
                        <IconPlayCircle v-else class="w-6 h-6" />
                    </button>

                    <div class="grow min-w-0">
                        <h4 class="text-sm font-black text-gray-900 dark:text-white truncate">
                            {{ currentTrack ? currentTrack.title : 'No song selected' }}
                        </h4>
                        <p class="text-[10px] text-gray-400 truncate mt-0.5">
                            {{ currentTrack ? currentTrack.prompt : 'Generate a track or select one from history.' }}
                        </p>
                    </div>

                    <a 
                        v-if="currentTrack"
                        :href="currentTrack.audio_url"
                        :download="`${currentTrack.title}.wav`"
                        class="p-2.5 rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 transition-colors"
                        title="Download Audio (.wav)"
                    >
                        <IconArrowDownTray class="w-5 h-5" />
                    </a>
                </div>
            </div>

            <!-- MiniMax Visualizer Video Card -->
            <div class="bg-white dark:bg-gray-900 p-5 rounded-3xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-4">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-black uppercase tracking-wider text-gray-400">Spectrum Visualizer</span>
                    <button 
                        @click="exportWaveformVideo" 
                        :disabled="!currentTrack || isRecordingVideo"
                        class="btn btn-secondary btn-xs flex items-center gap-1.5 font-bold"
                    >
                        <IconAnimateSpin v-if="isRecordingVideo" class="w-3.5 h-3.5 animate-spin" />
                        <IconArrowDownTray v-else class="w-3.5 h-3.5 text-amber-500" />
                        <span>{{ isRecordingVideo ? 'Recording Video...' : 'Export Video' }}</span>
                    </button>
                </div>

                <div class="relative w-full aspect-square rounded-2xl overflow-hidden bg-black shadow-2xl border border-gray-800">
                    <canvas 
                        ref="visualizerCanvasRef" 
                        width="512" 
                        height="512" 
                        class="w-full h-full object-cover block"
                    ></canvas>
                </div>
            </div>

            <!-- Track History Playlist -->
            <div class="bg-white dark:bg-gray-900 p-5 rounded-3xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-4">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-black uppercase tracking-wider text-gray-400">Library Playlist ({{ tracks.length }})</span>
                    <button @click="musicStore.fetchTracks" class="p-1 text-gray-400 hover:text-amber-500">
                        <IconRefresh class="w-3.5 h-3.5" :class="{'animate-spin': isLoadingTracks}" />
                    </button>
                </div>

                <div v-if="isLoadingTracks" class="text-center py-6 text-xs text-gray-400">Loading library...</div>
                <div v-else-if="tracks.length === 0" class="text-center py-8 text-xs text-gray-400 italic border border-dashed rounded-2xl dark:border-gray-800">
                    No songs in library yet. Use the studio to craft your first song!
                </div>
                <div v-else class="space-y-2 max-h-80 overflow-y-auto custom-scrollbar pr-1">
                    <div 
                        v-for="t in tracks" 
                        :key="t.id"
                        @click="musicStore.selectTrack(t)"
                        class="p-3 rounded-2xl border transition-all flex items-center justify-between gap-3 cursor-pointer group"
                        :class="currentTrack?.id === t.id ? 'bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800 shadow-xs' : 'border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50'"
                    >
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="w-8 h-8 rounded-xl bg-amber-500 text-white flex items-center justify-center shrink-0 shadow-xs">
                                <IconMusicalNote class="w-4 h-4" />
                            </div>
                            <div class="min-w-0">
                                <h5 class="text-xs font-bold text-gray-900 dark:text-gray-100 truncate">{{ t.title }}</h5>
                                <p class="text-[10px] text-gray-400 truncate">{{ t.duration }}s · {{ t.instrumental ? 'Instrumental' : 'Vocal' }}</p>
                            </div>
                        </div>

                        <div class="flex items-center gap-1 shrink-0">
                            <button @click.stop="musicStore.deleteTrack(t.id)" class="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 rounded-lg transition-opacity" title="Delete Track">
                                <IconTrash class="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>

        </div>

    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";

.input-field {
    @apply bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl text-gray-800 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 transition-all;
}
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>