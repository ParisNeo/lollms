<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import JsonRenderer from '../ui/JsonRenderer.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('sourceViewer'));

const title = computed(() => props.value?.title || 'Source');
const content = computed(() => props.value?.content || '');
const score = computed(() => props.value?.score ? Math.round(props.value.score) : null);
const metadata = computed(() => (props.value?.metadata && Object.keys(props.value.metadata).length > 0) ? props.value.metadata : null);

const searchTerm = ref('');
const searchResults = ref({ count: 0, positions: [], currentIndex: -1 });
const contentRef = ref(null);

const scoreColor = computed(() => {
    if (score.value === null) return 'bg-gray-400';
    if (score.value < 50) return 'bg-red-500';
    if (score.value < 80) return 'bg-yellow-500';
    return 'bg-green-500';
});

const highlightedContent = computed(() => {
    if (!content.value) return '';
    if (!searchTerm.value) return content.value;
    const regex = new RegExp(`(${searchTerm.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return content.value.replace(regex, '<mark class="bg-yellow-300 dark:bg-yellow-600 rounded">$1</mark>');
});

watch(searchTerm, (newTerm) => {
    if (!newTerm) {
        searchResults.value = { count: 0, positions: [], currentIndex: -1 };
        return;
    }
    const regex = new RegExp(newTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const positions = [];
    let match;
    while ((match = regex.exec(content.value)) !== null) {
        positions.push(match.index);
    }
    searchResults.value = { count: positions.length, positions, currentIndex: positions.length > 0 ? 0 : -1 };
    if (positions.length > 0) {
        nextTick(() => scrollToMatch(0));
    }
});

function scrollToMatch(index) {
    if (!contentRef.value) return;
    const marks = contentRef.value.querySelectorAll('mark');
    if (marks[index]) {
        marks.forEach(mark => mark.classList.remove('current-search-highlight'));
        marks[index].classList.add('current-search-highlight');
        marks[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function navigateSearch(direction) {
    if (searchResults.value.count === 0) return;
    let newIndex = searchResults.value.currentIndex + direction;
    if (newIndex < 0) newIndex = searchResults.value.count - 1;
    if (newIndex >= searchResults.value.count) newIndex = 0;
    searchResults.value.currentIndex = newIndex;
    scrollToMatch(newIndex);
}

</script>
<template>
    <GenericModal modalName="sourceViewer" :title="title" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="space-y-4 p-4">
                <div v-if="score !== null" class="flex items-center gap-3">
                    <span class="text-sm font-medium flex-shrink-0">Similarity:</span>
                    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 relative overflow-hidden">
                        <div class="h-4 rounded-full text-white text-xs flex items-center justify-center transition-all duration-300" :class="scoreColor" :style="{ width: score + '%' }">
                            <span v-if="score > 10">{{ score }}%</span>
                        </div>
                        <span v-if="score <= 10" class="absolute inset-0 flex items-center justify-center text-xs font-semibold" :class="score > 50 ? 'text-white' : 'text-gray-800 dark:text-gray-200'">{{score}}%</span>
                    </div>
                </div>

                <details v-if="metadata" class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border dark:border-gray-700" open>
                    <summary class="font-semibold cursor-pointer">Metadata</summary>
                    <div class="mt-2">
                        <JsonRenderer :json="metadata" />
                    </div>
                </details>

                <div>
                    <h4 class="font-semibold mb-2">Content</h4>
                    <div class="relative">
                        <input type="text" v-model="searchTerm" placeholder="Search in content..." class="input-field w-full pr-32" />
                        <div v-if="searchTerm" class="absolute inset-y-0 right-0 flex items-center pr-3 text-sm">
                            <span>{{ searchResults.count > 0 ? searchResults.currentIndex + 1 : 0 }} / {{ searchResults.count }}</span>
                            <button @click="navigateSearch(-1)" class="ml-2 p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600" :disabled="searchResults.count === 0"><IconChevronRight class="w-4 h-4 transform rotate-180" /></button>
                            <button @click="navigateSearch(1)" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600" :disabled="searchResults.count === 0"><IconChevronRight class="w-4 h-4" /></button>
                        </div>
                    </div>
                    <div ref="contentRef" class="mt-2 p-3 bg-gray-100 dark:bg-gray-900 rounded-md max-h-96 overflow-y-auto whitespace-pre-wrap break-words">
                        <span v-html="highlightedContent"></span>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('sourceViewer')" type="button" class="btn btn-secondary">Close</button>
        </template>
    </GenericModal>
</template>
<style>
.current-search-highlight {
    background-color: #FFA500 !important;
    border-radius: 2px;
}
</style>
