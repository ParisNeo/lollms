<script setup>
import { computed, ref, watch } from 'vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconWrenchScrewdriver from '../../../assets/icons/IconWrenchScrewdriver.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';
import IconTerminal from '../../../assets/icons/ui/IconTerminal.vue';

const props = defineProps({
    pType: { type: String, default: 'process' },
    title: { type: String, default: 'Processing' },
    statusContent: { type: String, default: '' },
    isClosed: { type: Boolean, default: false }
});

const isExpanded = ref(!props.isClosed);
const showAllLogs = ref(false);

// Auto-expand when new status updates arrive during streaming
watch(() => props.statusContent, () => {
    if (!props.isClosed) {
        isExpanded.value = true;
    }
});

// CRITICAL FIX: Auto-collapse when process completes to prevent spam display
watch(() => props.isClosed, (closed) => {
    if (closed) {
        isExpanded.value = false;
        showAllLogs.value = false;
    } else {
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
            borderClass: 'border-purple-100 dark:border-purple-800/50',
            barClass: 'bg-purple-500',
            glowClass: 'shadow-purple-500/30'
        },
        'artefact_building': {
            label: 'Building Artefact',
            icon: IconFileText,
            colorClass: 'text-blue-500',
            bgClass: 'bg-blue-50 dark:bg-blue-900/20',
            borderClass: 'border-blue-100 dark:border-blue-800/50',
            barClass: 'bg-blue-500',
            glowClass: 'shadow-blue-500/30'
        },
        'widget_building': {
            label: 'Creating Widget',
            icon: IconCpuChip,
            colorClass: 'text-indigo-500',
            bgClass: 'bg-indigo-50 dark:bg-indigo-900/20',
            borderClass: 'border-indigo-100 dark:border-indigo-800/50',
            barClass: 'bg-indigo-500',
            glowClass: 'shadow-indigo-500/30'
        },
        'note_building': {
            label: 'Writing Note',
            icon: IconPencil,
            colorClass: 'text-amber-500',
            bgClass: 'bg-amber-50 dark:bg-amber-900/20',
            borderClass: 'border-amber-100 dark:border-amber-800/50',
            barClass: 'bg-amber-500',
            glowClass: 'shadow-amber-500/30'
        }
    };
    return configs[props.pType] || {
        label: 'Processing',
        icon: IconCpuChip,
        colorClass: 'text-gray-500',
        bgClass: 'bg-gray-50 dark:bg-gray-900/20',
        borderClass: 'border-gray-100 dark:border-gray-800/50',
        barClass: 'bg-gray-500',
        glowClass: 'shadow-gray-500/30'
    };
});

const genericPatterns = [
    'WRITING CONTENT DATA',
    'GENERATING CONTENT',
    'PROCESSING DATA',
    'BUILDING COMPONENT',
    'COMPILING ASSETS',
    'FETCHING DATA',
    'RENDERING OUTPUT'
];

function isGenericMessage(msg) {
    if (!msg) return false;
    const upper = msg.toUpperCase();
    return genericPatterns.some(pattern => upper.includes(pattern));
}

const rawLines = computed(() => {
    if (!props.statusContent) return [];
    return props.statusContent
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.startsWith('*'))
        .map(line => line.substring(1).trim())
        .map(line => isGenericMessage(line) ? 'Writing content data...' : line);
});

const collapsedLines = computed(() => {
    const lines = rawLines.value;
    if (lines.length === 0) return [];

    let genericCount = 0;
    const meaningfulLines = [];

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (isGenericMessage(line)) {
            genericCount++;
        } else {
            meaningfulLines.push(line);
        }
    }

    const result = [];
    const lastMeaningful = meaningfulLines.slice(-5);
    for (const line of lastMeaningful) {
        result.push({ text: line, count: 1, isGeneric: false });
    }

    if (genericCount > 0) {
        result.push({ text: 'Writing content data...', count: genericCount, isGeneric: true });
    }

    return result;
});

const displayLines = computed(() => {
    if (showAllLogs.value) {
        const capped = rawLines.value.slice(-50);
        // CRITICAL FIX: Group consecutive identical lines even in expanded view
        // to prevent redundant spam display
        const grouped = [];
        for (const text of capped) {
            const last = grouped[grouped.length - 1];
            if (last && last.text === text) {
                last.count++;
            } else {
                grouped.push({ text, count: 1, isGeneric: isGenericMessage(text) });
            }
        }
        return grouped;
    }
    return collapsedLines.value;
});

const stepCounter = computed(() => {
    const current = rawLines.value.length;
    return `${current} steps logged`;
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
                    <div class="relative shrink-0">
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

            <!-- Progress Bar -->
            <div v-if="rawLines.length > 0" class="px-4 pb-2">
                <div class="flex items-center justify-between mb-1.5">
                    <div class="flex items-center gap-2">
                        <IconTerminal class="w-3 h-3 text-gray-400" />
                        <span class="text-[10px] font-bold uppercase tracking-tighter text-gray-500 dark:text-gray-400">
                            {{ stepCounter }}
                        </span>
                    </div>
                    <span v-if="!isClosed" class="text-[10px] font-bold uppercase tracking-tighter animate-pulse" :class="typeConfig.colorClass">
                        Working...
                    </span>
                </div>
                <div class="h-1.5 w-full rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden relative">
                    <div 
                        v-if="!isClosed"
                        class="absolute top-0 left-0 h-full w-1/3 rounded-full animate-marquee"
                        :class="[typeConfig.barClass, 'opacity-70']"
                    ></div>
                    <div 
                        v-else
                        class="h-full w-full rounded-full"
                        :class="typeConfig.barClass"
                    ></div>
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
                    <div class="px-4 pb-4 pt-3 space-y-1 border-t border-gray-200/50 dark:border-gray-700/50">
                        <div v-if="rawLines.length === 0" class="text-xs text-gray-400 italic pl-10 font-mono">
                            Awaiting task logs...
                        </div>

                        <!-- Terminal Header -->
                        <div v-if="rawLines.length > 0" class="flex items-center justify-between mb-2 pb-2 border-b border-gray-200/30 dark:border-gray-700/30">
                            <div class="flex items-center gap-1.5">
                                <div class="w-2.5 h-2.5 rounded-full bg-red-400/80"></div>
                                <div class="w-2.5 h-2.5 rounded-full bg-yellow-400/80"></div>
                                <div class="w-2.5 h-2.5 rounded-full bg-green-400/80"></div>
                                <span class="ml-2 text-[10px] text-gray-400 font-mono uppercase tracking-wider">console.log</span>
                            </div>
                            <button 
                                v-if="collapsedLines.length !== rawLines.length"
                                @click.stop="showAllLogs = !showAllLogs"
                                class="text-[10px] font-bold uppercase tracking-tighter px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                            >
                                {{ showAllLogs ? 'Collapse' : 'Show all' }} {{ rawLines.length }}
                            </button>
                        </div>

                        <!-- Log Lines -->
                        <div 
                            v-for="line in displayLines" 
                            :key="line.text + '-' + (line.count || 0)"
                            class="flex items-start gap-2.5 pl-1 group/line font-mono"
                        >
                            <!-- Step Indicator -->
                            <div class="flex items-center justify-center w-5 h-5 shrink-0 mt-0.5">
                                <!-- Active / Last step -->
                                <div 
                                    v-if="line === displayLines[displayLines.length - 1] && !isClosed"
                                    class="relative"
                                >
                                    <div 
                                        class="w-4 h-4 rounded-full flex items-center justify-center"
                                        :class="[typeConfig.bgClass, typeConfig.glowClass, { 'animate-pulse shadow-lg': !isClosed }]"
                                    >
                                        <div class="w-2 h-2 rounded-full" :class="typeConfig.barClass"></div>
                                    </div>
                                    <!-- Shimmer ring -->
                                    <div 
                                        class="absolute inset-0 rounded-full border-2 border-transparent animate-spin"
                                        :class="typeConfig.colorClass"
                                        style="border-top-color: currentColor; animation-duration: 2s;"
                                    ></div>
                                </div>
                                <!-- Completed step -->
                                <div 
                                    v-else
                                    class="w-4 h-4 rounded-full flex items-center justify-center bg-gray-100 dark:bg-gray-800"
                                >
                                    <IconCheckCircle class="w-3 h-3 text-green-500" />
                                </div>
                            </div>

                            <!-- Line Text -->
                            <div class="flex items-center gap-2 min-w-0 flex-1">
                                <span 
                                    class="text-[11px] leading-relaxed tracking-tight truncate"
                                    :class="[
                                        line === displayLines[displayLines.length - 1] && !isClosed 
                                            ? [typeConfig.colorClass, 'font-bold'] 
                                            : 'text-gray-400 dark:text-gray-500'
                                    ]"
                                >
                                    {{ line.text }}
                                </span>
                                <!-- Count Badge -->
                                <span 
                                    v-if="line.count > 1"
                                    class="shrink-0 text-[10px] font-black px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 tabular-nums"
                                >
                                    ×{{ line.count }}
                                </span>
                            </div>
                        </div>

                        <!-- Live cursor for active process -->
                        <div v-if="!isClosed && rawLines.length > 0" class="flex items-center gap-2.5 pl-1 mt-1">
                            <div class="w-5 shrink-0 flex justify-center">
                                <div 
                                    class="w-2 h-4 rounded-sm animate-pulse"
                                    :class="typeConfig.barClass"
                                ></div>
                            </div>
                            <span class="text-[10px] text-gray-400 font-mono animate-pulse">_</span>
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

@keyframes shimmer {
    0% {
        opacity: 0.4;
    }
    50% {
        opacity: 1;
    }
    100% {
        opacity: 0.4;
    }
}

.animate-shimmer {
    animation: shimmer 2s ease-in-out infinite;
}

@keyframes marquee {
    0% {
        transform: translateX(-100%);
    }
    100% {
        transform: translateX(300%);
    }
}

.animate-marquee {
    animation: marquee 1.5s linear infinite;
}
</style>