<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';

const uiStore = useUiStore();
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

</script>

<template>
    <GenericModal
        modal-name="artefactViewer"
        :title="title"
        max-width-class="max-w-4xl"
    >
        <template #body>
            <div v-if="artefact" class="space-y-4">
                <div v-if="hasContent && !hasImages" class="text-center text-gray-500 italic p-4">
                    This artefact has no displayable content or images.
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
            <button @click="uiStore.closeModal('artefactViewer')" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>
</template>