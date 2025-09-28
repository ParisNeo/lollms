<!-- [CREATE] frontend/webui/src/components/ui/AudioEditor.vue -->
<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconScissors from '../../assets/icons/IconScissors.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
  audioUrl: { type: String, required: true },
});
const emit = defineEmits(['trimmed']);

const wavesurfer = ref(null);
const waveformRef = ref(null);
const isLoading = ref(true);
const isPlaying = ref(false);
const region = ref(null);

watch(() => props.audioUrl, (newUrl) => {
  if (wavesurfer.value && newUrl) {
    isLoading.value = true;
    wavesurfer.value.load(newUrl);
  }
});

onMounted(() => {
  if (waveformRef.value) {
    wavesurfer.value = WaveSurfer.create({
      container: waveformRef.value,
      waveColor: 'rgb(200 200 200)',
      progressColor: 'rgb(100 100 100)',
      url: props.audioUrl,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
    });

    const wsRegions = wavesurfer.value.registerPlugin(RegionsPlugin.create());
    
    wavesurfer.value.on('ready', () => {
      isLoading.value = false;
      isPlaying.value = false;
    });

    wavesurfer.value.on('play', () => { isPlaying.value = true; });
    wavesurfer.value.on('pause', () => { isPlaying.value = false; });
    wavesurfer.value.on('finish', () => { isPlaying.value = false; });

    wsRegions.on('region-created', (newRegion) => {
      if (region.value) {
        region.value.remove();
      }
      region.value = newRegion;
    });

    wsRegions.enableDragSelection({
        color: 'rgba(255, 0, 0, 0.1)',
    });
  }
});

onUnmounted(() => {
  wavesurfer.value?.destroy();
});

function handlePlayPause() {
  wavesurfer.value?.playPause();
}

function handleTrim() {
  if (region.value) {
    emit('trimmed', { start: region.value.start, end: region.value.end });
    region.value.remove();
    region.value = null;
  }
}
</script>

<template>
  <div class="bg-gray-100 dark:bg-gray-700/50 p-3 rounded-lg">
    <div class="relative min-h-[100px]">
      <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center">
        <IconAnimateSpin class="w-8 h-8 text-gray-400" />
      </div>
      <div ref="waveformRef"></div>
    </div>
    <div class="flex items-center justify-center gap-4 mt-2">
      <button @click="handlePlayPause" class="btn btn-secondary p-2 rounded-full">
        <IconStopCircle v-if="isPlaying" class="w-6 h-6" />
        <IconPlayCircle v-else class="w-6 h-6" />
      </button>
      <button @click="handleTrim" :disabled="!region" class="btn btn-secondary p-2 rounded-full" title="Trim to selection">
        <IconScissors class="w-6 h-6" />
      </button>
    </div>
  </div>
</template>