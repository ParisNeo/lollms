<script setup>
import { computed } from 'vue';
import IconPresentationChartBar from '../../../assets/icons/IconPresentationChartBar.vue';
import IconVideoCamera from '../../../assets/icons/IconVideoCamera.vue';
import IconBookOpen from '../../../assets/icons/IconBookOpen.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';

const props = defineProps({
    title: String,
    type: String
});

const emit = defineEmits(['update:title', 'update:type', 'next']);

const projectTypes = [
    { id: 'generic', label: 'General Research', icon: IconFileText, desc: 'A standard notebook for organizing research and notes.' },
    { id: 'slides_making', label: 'Presentation Deck', icon: IconPresentationChartBar, desc: 'Generate slides, visuals, and speaker notes.' },
    { id: 'youtube_video', label: 'Video Production', icon: IconVideoCamera, desc: 'Create scripts, storyboards, and asset lists for video.' },
    { id: 'book_building', label: 'Book / Long-form', icon: IconBookOpen, desc: 'Plan and write structured long-form content.' },
];

const localTitle = computed({
    get: () => props.title,
    set: (val) => emit('update:title', val)
});

function selectType(id) {
    emit('update:type', id);
}
</script>

<template>
    <div class="h-full flex flex-col">
        <div class="text-center mb-8">
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">Choose Project Type</h2>
        </div>
        
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
            <div v-for="pt in projectTypes" :key="pt.id" @click="selectType(pt.id)"
                 class="group p-6 rounded-xl border-2 cursor-pointer transition-all hover:shadow-lg flex flex-col items-center text-center gap-3"
                 :class="type === pt.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 shadow-md' : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'">
                <component :is="pt.icon" class="w-12 h-12 transition-transform group-hover:scale-110" :class="type === pt.id ? 'text-blue-600' : 'text-gray-400'" />
                <div>
                    <h3 class="font-bold text-base text-gray-900 dark:text-white mb-1">{{ pt.label }}</h3>
                    <p class="text-xs text-gray-500">{{ pt.desc }}</p>
                </div>
            </div>
        </div>

        <div class="space-y-3 max-w-2xl mx-auto w-full">
            <label class="block text-sm font-bold text-gray-700 dark:text-gray-300">Project Title <span class="text-red-500">*</span></label>
            <input v-model="localTitle" class="input-field w-full text-lg px-4 py-3 border-2 transition-colors focus:border-blue-500" placeholder="e.g. 'Project Mars'" @keyup.enter="$emit('next')" />
        </div>
    </div>
</template>
