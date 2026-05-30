<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const props = computed(() => uiStore.modalData('artefactViewer'));

const artefact = computed(() => props.value?.artefact || props.value || {});

const title = computed(() => {
    if (!artefact.value) return 'Artefact Viewer';
    // RAG sources have `document`, artefacts have `title`
    return artefact.value.title || artefact.value.document || 'Artefact Details';
});

const content = computed(() => artefact.value?.content || artefact.value?.chunk_text || '');
const images = computed(() => artefact.value?.images || []);

const hasContent = computed(() => content.value && content.value.trim() !== '');
const hasImages = computed(() => images.value && images.value.length > 0);

async function handleImportToCurrentChat() {
    if (!discussionsStore.currentDiscussionId || discussionsStore.currentDiscussionId === 'saved') {
        uiStore.addNotification("Please select or start a chat first.", "warning");
        return;
    }
    try {
        uiStore.closeModal('artefactViewer');
        uiStore.addNotification("Importing document to chat workspace...", "info");

        await discussionsStore.importArtefactFromSource({
            targetDiscussionId: discussionsStore.currentDiscussionId,
            sourceDiscussionId: 'saved',
            artefactTitle: title.value
        });

        // Open the workspace panel automatically for high-fidelity experience
        uiStore.activeSplitArtefactTitle = title.value;
        uiStore.dataZoneTab = 'workspace';
        uiStore.isDataZoneVisible = true;
    } catch (e) {
        console.error("Import failed:", e);
    }
}
</script>

<template>
    <GenericModal
        modal-name="artefactViewer"
        :title="title"
        max-width-class="max-w-4xl"
    >
        <template #body>
            <div v-if="artefact" class="space-y-4">
                <div v-if="!hasContent && !hasImages" class="text-center text-gray-500 italic p-12 bg-gray-50 dark:bg-gray-900/30 rounded-xl border-2 border-dashed dark:border-gray-800">
                    <svg class="w-12 h-12 mx-auto mb-4 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    <p>This artefact has no displayable content or images.</p>
                </div>

                <div v-if="hasImages" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                    <div v-for="(img_b64, index) in images" :key="`${index}-${img_b64.slice(0, 30)}`" class="relative group rounded-lg overflow-hidden">
                        <img :src="'data:image/png;base64,' + img_b64" class="w-full h-48 object-cover cursor-pointer" @click="uiStore.openImageViewer('data:image/png;base64,' + img_b64)" alt="Artefact image"/>
                    </div>
                </div>

                <div v-if="hasContent">
                    <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg max-h-[60vh] overflow-y-auto">
                        <MessageContentRenderer :content="content" />
                    </div>
                </div>

                <div v-if="artefact.similarity_percent" class="pt-4 border-t dark:border-gray-700">
                    <p class="text-sm font-semibold text-gray-700 dark:text-gray-200">
                        Similarity Score: 
                        <span class="font-bold"
                              :class="{
                                  'text-green-600 dark:text-green-400': artefact.similarity_percent >= 85,
                                  'text-yellow-600 dark:text-yellow-400': artefact.similarity_percent >= 70 && artefact.similarity_percent < 85,
                                  'text-red-600 dark:text-red-400': artefact.similarity_percent < 70
                              }">
                            {{ artefact.similarity_percent.toFixed(2) }}%
                        </span>
                    </p>
                </div>

            </div>
        </template>
         <template #footer>
            <div class="flex justify-between items-center w-full">
                <!-- Inline Import Option inside Modal footer -->
                <button 
                    v-if="discussionsStore.currentDiscussionId && discussionsStore.currentDiscussionId !== 'saved'"
                    @click="handleImportToCurrentChat" 
                    class="btn btn-secondary btn-sm flex items-center gap-1.5"
                    title="Copy this global library document directly into your active chat workspace"
                >
                    <IconArrowUpTray class="w-3.5 h-3.5 text-blue-500" />
                    <span>Import to Current Chat</span>
                </button>
                <div v-else></div>
                <button @click="uiStore.closeModal('artefactViewer')" class="btn btn-primary px-8">Close</button>
            </div>
        </template>
    </GenericModal>
</template>