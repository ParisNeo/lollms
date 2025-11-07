<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import JsonRenderer from '../ui/JsonRenderer.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('allSourcesSearch'));
const sources = computed(() => props.value?.sources || []);

const searchTerm = ref('');
const searchResults = ref([]); // [{sourceIndex, matchIndexInContent, ...}]
const currentMatchIndex = ref(-1);

const searchMatchesCount = computed(() => searchResults.value.length);

watch(searchTerm, (newTerm) => {
    if (!newTerm) {
        searchResults.value = [];
        currentMatchIndex.value = -1;
        return;
    }
    const regex = new RegExp(newTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const matches = [];
    let matchCounter = 0;
    sources.value.forEach((source, sourceIndex) => {
        if (source.content) {
            let match;
            while ((match = regex.exec(source.content)) !== null) {
                matches.push({
                    sourceIndex,
                    sourceTitle: source.title,
                    matchIndex: matchCounter++,
                    matchIndexInContent: match.index,
                });
            }
        }
    });
    searchResults.value = matches;
    if (matches.length > 0) {
        currentMatchIndex.value = 0;
        nextTick(() => scrollToMatch(0));
    } else {
        currentMatchIndex.value = -1;
    }
});

function highlightedContent(content) {
    if (!content) return '';
    if (!searchTerm.value) return content;
    const regex = new RegExp(`(${searchTerm.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return content.replace(regex, '<mark class="bg-yellow-300 dark:bg-yellow-600 rounded">$1</mark>');
}

function scrollToMatch(matchIndex) {
    const match = searchResults.value[matchIndex];
    if (!match) return;
    const sourceElement = document.getElementById(`all-sources-content-${match.sourceIndex}`);
    if (sourceElement) {
        const marks = sourceElement.querySelectorAll('mark');
        let currentMarkIndex = 0;
        for (let i = 0; i < match.sourceIndex; i++) {
            if (sources.value[i].content) {
                const regex = new RegExp(searchTerm.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
                currentMarkIndex += (sources.value[i].content.match(regex) || []).length;
            }
        }
        
        const marksInCurrentSource = (sources.value[match.sourceIndex].content.match(new RegExp(searchTerm.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')) || []).length;
        
        let targetMarkIndexInSource = -1;
        const regex = new RegExp(searchTerm.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
        let i = 0;
        let m;
        while ((m = regex.exec(sources.value[match.sourceIndex].content)) !== null) {
            if (m.index === match.matchIndexInContent) {
                targetMarkIndexInSource = i;
                break;
            }
            i++;
        }

        if (targetMarkIndexInSource > -1) {
            const allMarks = document.querySelectorAll('.all-sources-search-container mark');
            allMarks.forEach(m => m.classList.remove('current-search-highlight'));
            
            const targetMark = marks[targetMarkIndexInSource];
            if (targetMark) {
                targetMark.classList.add('current-search-highlight');
                targetMark.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }
}

function navigateSearch(direction) {
    if (searchMatchesCount.value === 0) return;
    let newIndex = currentMatchIndex.value + direction;
    if (newIndex < 0) newIndex = searchMatchesCount.value - 1;
    if (newIndex >= searchMatchesCount.value) newIndex = 0;
    currentMatchIndex.value = newIndex;
    scrollToMatch(newIndex);
}
</script>
<template>
    <GenericModal modalName="allSourcesSearch" title="Search All Sources" maxWidthClass="max-w-5xl">
        <template #body>
            <div class="p-4 space-y-4">
                <div class="relative">
                    <input type="text" v-model="searchTerm" placeholder="Search in all source contents..." class="input-field w-full pr-32" autofocus />
                    <div v-if="searchTerm" class="absolute inset-y-0 right-0 flex items-center pr-3 text-sm">
                        <span>{{ searchMatchesCount > 0 ? currentMatchIndex + 1 : 0 }} / {{ searchMatchesCount }}</span>
                        <button @click="navigateSearch(-1)" class="ml-2 p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600" :disabled="searchMatchesCount === 0"><IconChevronRight class="w-4 h-4 transform rotate-180" /></button>
                        <button @click="navigateSearch(1)" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600" :disabled="searchMatchesCount === 0"><IconChevronRight class="w-4 h-4" /></button>
                    </div>
                </div>

                <div class="max-h-[60vh] overflow-y-auto space-y-4 pr-2 all-sources-search-container">
                    <div v-for="(source, index) in sources" :key="index" class="p-4 border rounded-lg dark:border-gray-700">
                        <h3 class="font-semibold text-lg mb-2">{{ source.title }}</h3>
                        <div :id="`all-sources-content-${index}`" class="whitespace-pre-wrap break-words text-sm bg-gray-50 dark:bg-gray-800/50 p-2 rounded-md" v-html="highlightedContent(source.content)"></div>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('allSourcesSearch')" type="button" class="btn btn-secondary">Close</button>
        </template>
    </GenericModal>
</template>
<style>
.current-search-highlight {
    background-color: #FFA500 !important;
    border-radius: 2px;
}
</style>
