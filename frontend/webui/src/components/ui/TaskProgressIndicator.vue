<!-- [NEW] frontend/webui/src/components/ui/TaskProgressIndicator.vue -->
<template>
  <div class="flex flex-col gap-1 w-full">
    <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
      <span class="font-medium truncate">{{ task.description || task.name }}</span>
      <span class="font-mono">{{ task.progress }}%</span>
    </div>
    <div class="h-1.5 w-full bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
      <div 
        class="h-full bg-blue-500 transition-all duration-300 ease-out" 
        :style="{ width: `${task.progress}%` }"
        :class="{'bg-red-500': task.status === 'failed', 'bg-green-500': task.status === 'completed'}"
      ></div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  task: { type: Object, required: true }
});
</script>
