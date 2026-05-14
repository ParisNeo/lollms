<script setup>
import { computed, ref } from 'vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
    pType: { type: String, default: 'process' },
    title: { type: String, default: 'Processing' },
    statusContent: { type: String, default: '' },
    isClosed: { type: Boolean, default: false }
});

const isExpanded = ref(false);

const typeLabel = computed(() => {
    const labels = {
        'tool_execution': 'Executing Tool',
        'artefact_building': 'Building Artefact',
        'widget_building': 'Creating Widget',
        'note_building': 'Writing Note'
    };
    return labels[props.pType] || 'Processing';
});

// Process lines into structured "Steps"
const steps = computed(() => {
    if (!props.statusContent) return [];
    
    // Split into primary chunks (starting with *)
    const rawLines = props.statusContent.split('\n').map(l => l.trim()).filter(l => l);
    const processedSteps = [];
    
    rawLines.forEach(line => {
        if (line.startsWith('*')) {
            // New primary step
            processedSteps.push({
                text: line.substring(1).trim(),
                subLines: [],
                isExpanded: false
            });
        } else if (processedSteps.length > 0) {
            // Continuation of the previous step
            processedSteps[processedSteps.length - 1].subLines.push(line);
        }
    });

    // Deduplicate based on the main text to prevent "history spam"
    const seen = new Set();
    return processedSteps.filter(s => {
        const duplicate = seen.has(s.text);
        seen.add(s.text);
        return !duplicate;
    });
});
</script>

<template>
    <div class="my-3 processing-block-root font-sans overflow-visible">
        <!-- 1. Trigger Area: Discreet Breadcrumb -->
        <button 
            @click="isExpanded = !isExpanded"
            class="group flex items-center gap-1.5 text-left transition-colors focus:outline-none whitespace-nowrap"
        >
            <IconAnimateSpin 
                v-if="!isClosed" 
                class="text-blue-500/70 shrink-0" 
                style="width: 12px; height: 12px; min-width: 12px;" 
            />
            
            <div class="flex items-center gap-1 text-[11px] text-gray-400 dark:text-gray-500 group-hover:text-gray-600 dark:group-hover:text-gray-300">
                <span class="uppercase font-bold tracking-wider opacity-80">{{ typeLabel }}:</span>
                <span class="truncate max-w-[180px] sm:max-w-md font-medium">{{ title }}</span>
                
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style="width: 14px; height: 14px;" class="transition-transform duration-300 opacity-40 shrink-0" :class="{ 'rotate-90': isExpanded }">
                    <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
                </svg>
            </div>
        </button>

        <!-- 2. The Timeline view -->
        <Transition
            enter-active-class="transition-all duration-300 ease-out"
            enter-from-class="max-h-0 opacity-0 -translate-y-1"
            enter-to-class="max-h-[600px] opacity-100 translate-y-0"
            leave-active-class="transition-all duration-200 ease-in"
            leave-from-class="max-h-[600px] opacity-100"
            leave-to-class="max-h-0 opacity-0"
        >
            <div v-if="isExpanded" class="mt-4 ml-1.5 pl-4 border-l border-gray-200/60 dark:border-gray-800 relative space-y-5">
                
                <div v-if="steps.length === 0" class="text-[10px] font-mono text-gray-400 italic">
                    Waiting for execution events...
                </div>

                <div 
                    v-for="(step, idx) in steps" 
                    :key="idx"
                    class="relative group/step"
                >
                    <!-- Timeline Dot -->
                    <div 
                        class="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full border-2 bg-white dark:bg-gray-950 transition-colors"
                        :class="[
                            idx === steps.length - 1 && !isClosed 
                            ? 'border-blue-500 animate-pulse' 
                            : 'border-gray-300 dark:border-gray-700'
                        ]"
                    ></div>

                    <!-- Step Content -->
                    <div class="flex flex-col gap-1">
                        <!-- Main Step Text -->
                        <div class="flex items-center justify-between gap-4">
                            <span 
                                class="text-[11px] font-medium leading-tight transition-colors"
                                :class="idx === steps.length - 1 && !isClosed ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400'"
                            >
                                {{ step.text }}
                            </span>
                            <span class="text-[9px] font-mono text-gray-300 dark:text-gray-700 select-none">0{{ idx + 1 }}</span>
                        </div>

                        <!-- Multi-line sub-content (Collapsible) -->
                        <div v-if="step.subLines.length > 0" class="mt-1">
                            <details class="group/details">
                                <summary class="list-none cursor-pointer flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3 h-3 transition-transform group-open/details:rotate-90">
                                        <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
                                    </svg>
                                    See Details
                                </summary>
                                <div class="mt-2 p-2 bg-gray-50 dark:bg-gray-900/50 rounded border border-gray-100 dark:border-gray-800 font-mono text-[10px] leading-relaxed text-gray-500 dark:text-gray-400">
                                    <div v-for="(sub, sIdx) in step.subLines" :key="sIdx">
                                        {{ sub }}
                                    </div>
                                </div>
                            </details>
                        </div>
                    </div>
                </div>

                <!-- Active Status Cursor -->
                <div v-if="!isClosed" class="flex items-center gap-2 text-[10px] text-blue-500/60 font-mono italic animate-pulse">
                    <span class="h-1.5 w-1.5 rounded-full bg-current"></span>
                    Running next step...
                </div>
            </div>
        </Transition>
    </div>
</template>

<style scoped>
/* Remove default details chevron */
summary::-webkit-details-marker {
  display: none;
}
</style>