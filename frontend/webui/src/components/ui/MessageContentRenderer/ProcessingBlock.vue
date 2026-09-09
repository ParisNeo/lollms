<script setup>
import { computed, ref } from 'vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../../assets/icons/IconXMark.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';
import IconCopy from '../../../assets/icons/IconCopy.vue';

const props = defineProps({
    pType: { type: String, default: 'process' },
    title: { type: String, default: 'Processing' },
    statusContent: { type: String, default: '' },
    isClosed: { type: Boolean, default: false },
    status: { type: String, default: null } // 'success' | 'failure' | 'finished'
});

const isExpanded = ref(false);
const copiedRaw = ref(false);

const typeLabel = computed(() => {
    const labels = {
        'tool': 'Tool Execution',
        'tool_execution': 'Tool Execution',
        'context_update': 'Context Update',
        'artefact_building': 'Building Artefact',
        'artefact': 'Building Artefact',
        'widget_building': 'Creating Widget',
        'note_building': 'Writing Note',
        'code_execution': 'Executing Code',
        'process': 'Processing'
    };
    return labels[props.pType] || (props.pType ? props.pType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Processing');
});

const isFailure = computed(() => {
    if (props.status === 'failure') return true;
    const content = (props.statusContent || '').toLowerCase();
    return content.includes('<!-- status:failure -->') || 
           content.includes('execution failed') || 
           content.includes('crashed') ||
           content.includes('error:');
});

const isSuccess = computed(() => {
    if (isFailure.value) return false;
    if (props.status === 'success' || props.status === 'finished') return true;
    const content = (props.statusContent || '').toLowerCase();
    return content.includes('<!-- status:success -->') || 
           content.includes('<!-- status:finished -->') || 
           props.isClosed;
});

// Process lines into structured "Steps"
const steps = computed(() => {
    if (!props.statusContent || !props.statusContent.trim()) return [];
    
    const cleanContent = props.statusContent.replace(/<!--\s*status:[a-zA-Z0-9_-]+\s*-->/gi, '').trim();
    if (!cleanContent) return [];

    const rawLines = cleanContent.split('\n').map(l => l.trimEnd()).filter(l => l.trim().length > 0);
    const processedSteps = [];
    let currentStep = null;
    
    rawLines.forEach((line) => {
        const trimmed = line.trim();
        const isBullet = trimmed.startsWith('*') || trimmed.startsWith('-') || trimmed.startsWith('•');
        
        if (isBullet) {
            currentStep = {
                text: trimmed.replace(/^[\*\-•]\s*/, ''),
                subLines: [],
                isExpanded: false
            };
            processedSteps.push(currentStep);
        } else if (currentStep) {
            currentStep.subLines.push(line);
        } else {
            // First lines before any bullet
            currentStep = {
                text: trimmed,
                subLines: [],
                isExpanded: false
            };
            processedSteps.push(currentStep);
        }
    });

    if (processedSteps.length === 0 && rawLines.length > 0) {
        processedSteps.push({
            text: rawLines[0].trim(),
            subLines: rawLines.slice(1),
            isExpanded: false
        });
    }

    return processedSteps;
});

function copyAllLogs() {
    if (!props.statusContent) return;
    navigator.clipboard.writeText(props.statusContent.replace(/<!--\s*status:[a-zA-Z0-9_-]+\s*-->/gi, '').trim());
    copiedRaw.value = true;
    setTimeout(() => { copiedRaw.value = false; }, 2000);
}
</script>

<template>
    <div class="my-3 processing-block-root font-sans overflow-visible not-prose">
        <!-- 1. Trigger Area: Discreet Breadcrumb / Header -->
        <button 
            type="button"
            @click="isExpanded = !isExpanded"
            class="group flex items-center gap-2 text-left transition-all focus:outline-none py-1 px-2.5 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800/70 border border-gray-200/60 dark:border-gray-700/60 shadow-2xs select-none cursor-pointer"
        >
            <!-- Status Indicator -->
            <IconAnimateSpin 
                v-if="!isClosed" 
                class="text-blue-500 shrink-0 animate-spin w-3.5 h-3.5" 
            />
            <IconCheckCircle 
                v-else-if="isSuccess"
                class="text-emerald-500 shrink-0 w-3.5 h-3.5"
            />
            <IconXMark 
                v-else-if="isFailure"
                class="text-rose-500 shrink-0 w-3.5 h-3.5"
            />
            <span 
                v-else 
                class="w-2 h-2 rounded-full bg-gray-400 shrink-0"
            ></span>

            <div class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white">
                <span class="uppercase font-bold tracking-wider text-[10px] text-gray-400 dark:text-gray-500">{{ typeLabel }}:</span>
                <span class="truncate max-w-[220px] sm:max-w-md font-semibold text-gray-800 dark:text-gray-200">{{ title }}</span>

                <span v-if="isFailure" class="px-1.5 py-0.2 rounded text-[9px] font-black uppercase tracking-wider bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 border border-rose-200 dark:border-rose-800 shrink-0">
                    Failed
                </span>
                <span v-else-if="isSuccess && isClosed" class="text-[9px] font-mono text-emerald-600 dark:text-emerald-400 font-bold shrink-0">
                    Done
                </span>

                <IconChevronRight class="w-3 h-3 transition-transform duration-300 opacity-60 shrink-0 ml-1" :class="{ 'rotate-90': isExpanded }" />
            </div>
        </button>

        <!-- 2. The Timeline view -->
        <Transition
            enter-active-class="transition-all duration-300 ease-out"
            enter-from-class="max-h-0 opacity-0 -translate-y-1"
            enter-to-class="max-h-[800px] opacity-100 translate-y-0"
            leave-active-class="transition-all duration-200 ease-in"
            leave-from-class="max-h-[800px] opacity-100"
            leave-to-class="max-h-0 opacity-0"
        >
            <div v-if="isExpanded" class="mt-3 ml-2 pl-4 border-l-2 border-gray-200 dark:border-gray-800 relative space-y-4 animate-in fade-in">
                
                <div v-if="steps.length === 0" class="text-xs font-mono text-gray-400 italic py-1">
                    {{ isClosed ? 'Process finished (no detailed log output).' : 'Waiting for execution events...' }}
                </div>

                <div 
                    v-for="(step, idx) in steps" 
                    :key="idx"
                    class="relative group/step"
                >
                    <!-- Timeline Dot -->
                    <div 
                        class="absolute -left-[22px] top-1 w-2.5 h-2.5 rounded-full border-2 bg-white dark:bg-gray-950 transition-colors"
                        :class="[
                            idx === steps.length - 1 && !isClosed 
                            ? 'border-blue-500 animate-pulse bg-blue-100' 
                            : isFailure && idx === steps.length - 1
                            ? 'border-rose-500 bg-rose-100'
                            : 'border-emerald-500/80 bg-emerald-50 dark:bg-emerald-950'
                        ]"
                    ></div>

                    <!-- Step Content -->
                    <div class="flex flex-col gap-1">
                        <!-- Main Step Text -->
                        <div class="flex items-center justify-between gap-4">
                            <span 
                                class="text-xs font-medium leading-snug transition-colors font-mono"
                                :class="[
                                    idx === steps.length - 1 && !isClosed ? 'text-blue-600 dark:text-blue-400 font-bold' : 
                                    isFailure && idx === steps.length - 1 ? 'text-rose-600 dark:text-rose-400 font-bold' : 
                                    'text-gray-700 dark:text-gray-300'
                                ]"
                            >
                                {{ step.text }}
                            </span>
                            <span class="text-[9px] font-mono text-gray-400 select-none">{{ idx + 1 < 10 ? '0' + (idx + 1) : idx + 1 }}</span>
                        </div>

                        <!-- Multi-line sub-content (Collapsible or open) -->
                        <div v-if="step.subLines.length > 0" class="mt-1">
                            <details class="group/details" :open="step.subLines.length <= 6">
                                <summary class="list-none cursor-pointer flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
                                    <IconChevronRight class="w-3 h-3 transition-transform group-open/details:rotate-90" />
                                    <span>{{ step.subLines.length }} output lines</span>
                                </summary>
                                <div class="mt-1.5 p-2.5 bg-gray-50 dark:bg-gray-900 rounded-xl border border-gray-200/80 dark:border-gray-800 font-mono text-xs leading-relaxed text-gray-700 dark:text-gray-300 overflow-x-auto custom-scrollbar whitespace-pre-wrap max-h-60">
                                    <div v-for="(sub, sIdx) in step.subLines" :key="sIdx">
                                        {{ sub }}
                                    </div>
                                </div>
                            </details>
                        </div>
                    </div>
                </div>

                <!-- Footer with Copy Raw Logs and Status -->
                <div class="pt-2 border-t dark:border-gray-800/60 flex items-center justify-between text-[10px] text-gray-400 font-mono">
                    <div v-if="!isClosed" class="flex items-center gap-1.5 text-blue-500 animate-pulse italic">
                        <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
                        <span>Running next step...</span>
                    </div>
                    <div v-else class="text-gray-400">
                        {{ isFailure ? '⚠️ Process terminated with errors' : '✓ Process completed' }}
                    </div>

                    <button 
                        type="button"
                        @click="copyAllLogs"
                        class="hover:text-blue-500 flex items-center gap-1 transition-colors px-1.5 py-0.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                        title="Copy logs to clipboard"
                    >
                        <IconCopy class="w-3 h-3" />
                        <span>{{ copiedRaw ? 'Copied!' : 'Copy Logs' }}</span>
                    </button>
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