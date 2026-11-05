<script setup>
import { useRouter } from 'vue-router';
import IconUserCircle from '@/assets/icons/IconUserCircle.vue';

const router = useRouter();

function openStudio() {
  router.push({ name: 'PersonalityStudio' });
}
</script>

<template>
  <div class="flex flex-col items-center justify-center p-8 text-center space-y-4">
    <div class="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-950/40 flex items-center justify-center">
      <IconUserCircle class="w-8 h-8 text-blue-500" />
    </div>
    <div class="space-y-1.5">
      <h2 class="text-xl font-bold text-gray-900 dark:text-gray-100">Personality Studio</h2>
      <p class="text-sm text-gray-500 dark:text-gray-400 max-w-md">
        Personalities now live in a dedicated three-pane workspace. Manage the catalog, edit SOUL prompts,
        attach skills and tools, and generate content with the built-in LoLLMs Copilot.
      </p>
    </div>
    <button type="button" class="btn btn-primary" @click="openStudio">
      Open Personality Studio
    </button>
  </div>
</template>