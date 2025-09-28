<!-- [UPDATE] frontend/webui/src/components/chat/AudioPlayer.vue -->
<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import IconSpeakerWave from '../../assets/icons/IconSpeakerWave.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';

const discussionsStore = useDiscussionsStore();
const currentPlayingAudio = computed(() => discussionsStore.currentPlayingAudio);
const isPlaying = computed(() => !!currentPlayingAudio.value.audio);
</script>

<template>
  <div v-if="isPlaying" class="fixed bottom-4 left-1/2 -translate-x-1/2 bg-gray-800 text-white rounded-full shadow-lg px-4 py-2 flex items-center gap-3 z-50">
    <IconSpeakerWave class="w-5 h-5 animate-pulse" />
    <span class="text-sm font-medium">Playing audio...</span>
    <button @click="discussionsStore.stopCurrentAudio()" class="p-1 rounded-full hover:bg-gray-700">
      <IconStopCircle class="w-6 h-6" />
    </button>
  </div>
</template>