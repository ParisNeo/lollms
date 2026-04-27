<script setup>
import { computed, ref, watch } from 'vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconWrenchScrewdriver from '../../../assets/icons/IconWrenchScrewdriver.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';

const props = defineProps({
    pType: { type: String, default: 'process' },
    title: { type: String, default: 'Processing' },
    statusContent: { type: String, default: '' },
    isClosed: { type: Boolean, default: false }
});

const isExpanded = ref(!props.isClosed);

// Auto-expand when new status updates arrive during streaming
watch(() => props.statusContent, () => {
    if (!props.isClosed) {
        isExpanded.value = true;
    }
});

const typeConfig = computed(() => {
    const configs = {
        'tool_execution': {
            label: 'Executing Tool',
            icon: IconWrenchScrewdriver,
            colorClass: 'text-purple-500',
            bgClass: 'bg-purple-50 dark:bg-purple-900/20',
            borderClass: 'border-purple-100 dark:border-purple-800/50'
        },
        'artefact_building': {
            label: 'Building Artefact',
            icon: IconFileText,
            colorClass: 'text-blue-500',
            bgClass: 'bg-blue-50 dark:bg-blue-900/20',
            borderClass: 'border-blue-100 dark:border-blue-800/50'
        },
        'widget_building': {
            label: 'Creating Widget',
            icon: IconCpuChip,
            colorClass: 'text-indigo-500',
            bgClass: 'bg-indigo-50 dark:bg-indigo-900/20',
            borderClass: 'border-indigo-100 dark:border-indigo-800/50'
        },
        'note_building': {
            label: 'Writing Note',
            icon: IconPencil,
            colorClass: 'text-amber-500',
            bgClass: 'bg-amber-50 dark:bg-amber-900/20',
            borderClass: 'border-amber-100 dark:border-amber-800/50'
        }
    };
    return configs[props.pType] || {
        label: 'Processing',
        icon: IconCpuChip,
        colorClass: 'text-gray-500',
        bgClass: 'bg-gray-50 dark:bg-gray-900/20',
        borderClass: 'border-gray-100 dark:border-gray-800/50'
    };
});

const parsedStatusLines = computed(() => {
    if (!props.statusContent) return [];
    return props.statusContent
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.startsWith('*'))
        .map(line => line.substring(1).trim());
});
</script>

<template>
    <div class="my-4 processing-block-wrapper animate-in fade-in slide-in-from-top-1 duration-300">
        <div 
            class="rounded-xl border shadow-sm transition-all"
            :class="[typeConfig.bgClass, typeConfig.borderClass, { 'ring-2 ring-blue-500/10': !isClosed }]"
        >
            <!-- Header Section -->
            <div 
                @click="isExpanded = !isExpanded"
                class="flex items-center justify-between px-4 py-3 cursor-pointer select-none"
            >
                <div class="flex items-center gap-3 min-w-0">
                    <div class="relative flex-shrink-0">
                        <div class="p-2 rounded-lg bg-white dark:bg-gray-800 shadow-sm" :class="typeConfig.colorClass">
                            <component :is="typeConfig.icon" class="w-4 h-4" />
                        </div>
                        <!-- Live Status Indicator -->
                        <div v-if="!isClosed" class="absolute -top-1 -right-1 flex h-3 w-3">
                            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                            <span class="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
                        </div>
                        <div v-else class="absolute -top-1 -right-1">
                            <IconCheckCircle class="w-3.5 h-3.5 text-green-500 fill-white dark:fill-gray-900" />
                        </div>
                    </div>
                    
                    <div class="flex items-baseline gap-2 min-w-0">
                        <span class="text-[10px] font-black uppercase tracking-widest opacity-60 whitespace-nowrap" :class="typeConfig.colorClass">
                            {{ typeConfig.label }}:
                        </span>
                        <h4 class="text-sm font-bold text-gray-800 dark:text-gray-100 truncate">
                            {{ title }}
                        </h4>
                    </div>
                </div>

                <div class="flex items-center gap-3">
                    <div v-if="!isClosed" class="flex items-center gap-2">
                        <IconAnimateSpin class="w-3.5 h-3.5 text-blue-500 animate-spin" />
                        <span class="text-[10px] font-bold text-blue-500 uppercase tracking-tighter animate-pulse">Running</span>
                    </div>
                    <div v-else class="text-[10px] font-bold text-gray-400 uppercase tracking-tighter">
                        Completed
                    </div>
                    <IconChevronRight 
                        class="w-4 h-4 text-gray-400 transition-transform duration-200"
                        :class="{ 'rotate-90': isExpanded }"
                    />
                </div>
            </div>

            <!-- Content / Logs Section -->
            <Transition
                enter-active-class="transition-all duration-300 ease-out"
                enter-from-class="max-h-0 opacity-0"
                enter-to-class="max-h-[500px] opacity-100"
                leave-active-class="transition-all duration-200 ease-in"
                leave-from-class="max-h-[500px] opacity-100"
                leave-to-class="max-h-0 opacity-0"
            >
                <div v-if="isExpanded" class="overflow-hidden">
                    <div class="px-4 pb-4 pt-3 space-y-2.5 border-t border-gray-200/50 dark:border-gray-700/50">
                        <div v-if="parsedStatusLines.length === 0" class="text-xs text-gray-400 italic pl-10">
                            Awaiting task logs...
                        </div>
                        <div 
                            v-for="(line, idx) in parsedStatusLines" 
                            :key="idx"
                            class="flex items-start gap-3 pl-1 group/line"
                        >
                            <div class="flex items-center justify-center w-5 h-5 flex-shrink-0">
                                <div class="w-1.5 h-1.5 rounded-full bg-gray-300 dark:bg-gray-600 group-last/line:bg-blue-500 group-last/line:animate-pulse"></div>
                            </div>
                            <span class="text-xs font-medium uppercase tracking-tight" :class="[
                                idx === parsedStatusLines.length - 1 && !isClosed 
                                ? 'text-blue-600 dark:text-blue-400 font-bold' 
                                : 'text-gray-500 dark:text-gray-400'
                            ]">
                                {{ line }}
                            </span>
                        </div>
                    </div>
                </div>
            </Transition>
        </div>
    </div>
</template>

<style scoped>
.processing-block-wrapper {
    max-width: 100%;
}
</style>