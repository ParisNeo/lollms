<template>
  <div :class="[
      'my-1.5 overflow-hidden rounded-lg border transition-all duration-300 shadow-sm',
      colorConfig.bg, colorConfig.border
  ]">
      <details class="group/proc-logs" :open="!isClosed">
          <summary class="flex items-center justify-between px-3 py-1 cursor-pointer list-none select-none hover:opacity-80 transition-opacity outline-none">
              <div class="flex items-center gap-2 min-w-0">
                  <!-- Aligned Status Icon -->
                  <div class="flex-shrink-0 flex items-center justify-center">
                      <IconAnimateSpin v-if="!isClosed" class="w-3.5 h-3.5 animate-spin" :class="colorConfig.text" />
                      <IconCheckCircle v-else class="w-3.5 h-3.5" :class="colorConfig.text" />
                  </div>

                  <div class="flex items-center gap-2 min-w-0 leading-none pt-1">
                      <!-- DYNAMIC HEADER CONTENT -->
                      <template v-if="!isClosed">
                          <h4 class="text-[11px] font-medium truncate dark:text-gray-300 text-gray-600 italic">
                              {{ currentStatus || 'Initializing...' }}
                          </h4>
                      </template>
                      
                      <template v-else>
                          <span class="text-[9px] font-black uppercase tracking-wider opacity-70 whitespace-nowrap" :class="colorConfig.text">
                              {{ typeLabel }}:
                          </span>
                          <h4 class="text-[11px] font-bold truncate dark:text-gray-200 text-gray-700">{{ title }}</h4>
                      </template>
                  </div>
              </div>

              <div class="flex items-center gap-2 ml-4">
                  <span v-if="!isClosed" class="text-[8px] font-black uppercase animate-pulse opacity-80 px-1.5 py-0.5 rounded bg-white/50 dark:bg-black/20" :class="colorConfig.text">
                      Active
                  </span>
                  <IconChevronRight class="w-3 h-3 text-gray-400 group-open/proc-logs:rotate-90 transition-transform" />
              </div>
          </summary>

          <!-- Log History Body -->
          <div class="px-4 pb-2 space-y-0.5 bg-white/40 dark:bg-black/10 font-mono text-[10px] border-t dark:border-gray-700/30 pt-1.5">
              <template v-if="lines.length > 0">
                  <div v-for="(line, lIdx) in lines" :key="lIdx" 
                       class="flex items-center gap-2 text-gray-500 dark:text-gray-400 border-l-2 pl-2 py-0.5"
                       :class="colorConfig.indicatorBorder">
                      <span class="truncate">{{ line.trim().replace(/^\*\s*/, '') }}</span>
                      
                      <IconAnimateSpin v-if="!isClosed && lIdx === lines.length - 1" class="w-2.5 h-2.5 animate-spin opacity-40" :class="colorConfig.text" />
                  </div>
              </template>
              
              <div v-if="isClosed" class="text-[8px] font-black uppercase mt-1 flex items-center gap-1 border-l-2 pl-2 h-4" :class="[colorConfig.text, colorConfig.indicatorBorder]">
                  Success
              </div>
          </div>
      </details>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';

const props = defineProps({
    pType: { type: String, required: true },
    title: { type: String, required: true },
    statusContent: { type: String, default: '' },
    isClosed: { type: Boolean, default: false }
});

const lines = computed(() => {
    if (!props.statusContent) return [];
    return props.statusContent.split('\n').filter(l => l.trim() !== '');
});

// The message currently displayed in the header during generation
const currentStatus = computed(() => {
    if (lines.value.length === 0) return '';
    return lines.value[lines.value.length - 1].replace(/^\*\s*/, '').trim();
});

const typeLabel = computed(() => {
    return props.pType.split('_')[0]; 
});

const colorConfig = computed(() => {
    const type = props.pType.toLowerCase();
    
    if (type.includes('note')) {
        return {
            bg: 'bg-amber-50/30 dark:bg-amber-900/5',
            border: 'border-amber-200/40 dark:border-amber-800/30',
            text: 'text-amber-600 dark:text-amber-400',
            indicatorBorder: 'border-amber-400/20'
        };
    }
    
    if (type.includes('skill')) {
        return {
            bg: 'bg-emerald-50/30 dark:bg-emerald-900/5',
            border: 'border-emerald-200/40 dark:border-emerald-800/30',
            text: 'text-emerald-600 dark:text-emerald-400',
            indicatorBorder: 'border-emerald-400/20'
        };
    }

    if (type.includes('artefact') || type.includes('widget')) {
        return {
            bg: 'bg-blue-50/30 dark:bg-blue-900/5',
            border: 'border-blue-200/40 dark:border-blue-800/30',
            text: 'text-blue-600 dark:text-blue-400',
            indicatorBorder: 'border-blue-400/20'
        };
    }

    return {
        bg: 'bg-gray-50/50 dark:bg-gray-800/20',
        border: 'border-gray-200/60 dark:border-gray-700/50',
        text: 'text-indigo-500 dark:text-indigo-400',
        indicatorBorder: 'border-gray-300/40'
    };
});
</script>

<style scoped>
details > summary::-webkit-details-marker { display: none; }
</style>