<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const props = computed(() => uiStore.modalData('artefactEditor'));
const artefact = computed(() => props.value?.artefact);
const discussionId = computed(() => props.value?.discussionId);

const getInitialState = () => ({
    title: '',
    content: '',
    images: [],
    newImages: [],
});

const form = ref(getInitialState());
const isLoading = ref(false);
const imageInput = ref(null);

const isEditMode = computed(() => !!artefact.value?.title);
const modalTitle = computed(() => isEditMode.value ? `Edit Artefact: ${artefact.value.title}` : 'Create New Artefact');

watch(props, (newProps) => {
    if (newProps && uiStore.isModalOpen('artefactEditor')) {
        form.value = getInitialState();
        if (newProps.artefact) {
            form.value.title = newProps.artefact.title || '';
            form.value.content = newProps.artefact.content || '';
            form.value.images = (newProps.artefact.images || []).map(img_b64 => ({
                b64: img_b64,
                isNew: false
            }));
        }
    }
}, { immediate: true, deep: true });

function triggerImageUpload() {
    imageInput.value?.click();
}

async function handleImageSelection(event) {
    const files = Array.from(event.target.files);
    for (const file of files) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const b64 = e.target.result.split(',')[1];
            form.value.newImages.push({ b64, isNew: true, file });
        };
        reader.readAsDataURL(file);
    }
    event.target.value = '';
}

function removeImage(index, isNew) {
    if (isNew) {
        form.value.newImages.splice(index, 1);
    } else {
        form.value.images.splice(index, 1);
    }
}

async function handleSubmit() {
    if (!form.value.title.trim()) {
        uiStore.addNotification('Artefact title is required.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        if (isEditMode.value) {
            // Update logic
            await discussionsStore.updateArtefact({
                discussionId: discussionId.value,
                artefactTitle: artefact.value.title,
                version: artefact.value.version,
                newContent: form.value.content,
                newImagesB64: form.value.newImages.map(img => img.b64),
                keptImagesB64: form.value.images.map(img => img.b64)
            });
        } else {
            // Create logic
            await discussionsStore.createManualArtefact({
                discussionId: discussionId.value,
                title: form.value.title,
                content: form.value.content,
                imagesB64: form.value.newImages.map(img => img.b64)
            });
        }
        uiStore.closeModal('artefactEditor');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="artefactEditor"
        :title="modalTitle"
        max-width-class="max-w-4xl"
    >
        <template #body>
            <form v-if="form" @submit.prevent="handleSubmit" class="space-y-4">
                <div>
                    <label for="artefact-title" class="label">Title</label>
                    <input
                        id="artefact-title"
                        v-model="form.title"
                        type="text"
                        class="input-field mt-1"
                        :disabled="isEditMode"
                        placeholder="Enter a unique title for the artefact"
                        required
                    />
                </div>
                <div>
                    <label for="artefact-content" class="label">Content (Markdown)</label>
                    <CodeMirrorEditor
                        v-model="form.content"
                        class="mt-1 h-64"
                        placeholder="Enter artefact content here..."
                    />
                </div>
                <div>
                    <div class="flex justify-between items-center mb-2">
                        <label class="label">Images</label>
                        <button @click="triggerImageUpload" type="button" class="btn btn-secondary btn-sm">
                            <IconPhoto class="w-4 h-4 mr-2" /> Add Image
                        </button>
                        <input type="file" ref="imageInput" @change="handleImageSelection" multiple accept="image/*" class="hidden">
                    </div>
                    <div class="p-2 border rounded-md min-h-[80px] bg-gray-50 dark:bg-gray-900/50">
                        <div v-if="form.images.length === 0 && form.newImages.length === 0" class="text-center text-sm text-gray-500 py-4">
                            No images attached.
                        </div>
                        <div v-else class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                            <!-- Existing Images -->
                            <div v-for="(image, index) in form.images" :key="`existing-${index}`" class="relative group/image">
                                <img :src="`data:image/png;base64,${image.b64}`" class="w-full h-24 object-cover rounded" />
                                <div class="absolute inset-0 bg-black/50 opacity-0 group-hover/image:opacity-100 transition-opacity flex items-center justify-center gap-1">
                                    <button @click="uiStore.openImageViewer(`data:image/png;base64,${image.b64}`)" type="button" class="p-1.5 bg-white/20 text-white rounded-full hover:bg-white/40" title="View"><IconMaximize class="w-4 h-4" /></button>
                                    <button @click="removeImage(index, false)" type="button" class="p-1.5 bg-red-500/80 text-white rounded-full hover:bg-red-600" title="Delete"><IconXMark class="w-4 h-4" /></button>
                                </div>
                            </div>
                            <!-- New Images -->
                             <div v-for="(image, index) in form.newImages" :key="`new-${index}`" class="relative group/image">
                                <img :src="`data:image/png;base64,${image.b64}`" class="w-full h-24 object-cover rounded" />
                                 <div class="absolute inset-0 bg-black/50 opacity-0 group-hover/image:opacity-100 transition-opacity flex items-center justify-center gap-1">
                                    <button @click="uiStore.openImageViewer(`data:image/png;base64,${image.b64}`)" type="button" class="p-1.5 bg-white/20 text-white rounded-full hover:bg-white/40" title="View"><IconMaximize class="w-4 h-4" /></button>
                                    <button @click="removeImage(index, true)" type="button" class="p-1.5 bg-red-500/80 text-white rounded-full hover:bg-red-600" title="Delete"><IconXMark class="w-4 h-4" /></button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
             <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('artefactEditor')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" type="button" class="btn btn-primary" :disabled="isLoading">
                    <IconAnimateSpin v-if="isLoading" class="w-5 h-5 mr-2" />
                    {{ isLoading ? 'Saving...' : (isEditMode ? 'Save Changes' : 'Create Artefact') }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>