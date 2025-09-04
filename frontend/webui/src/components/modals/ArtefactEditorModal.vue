<script setup>
import { ref, computed, watch } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalProps = computed(() => uiStore.modalData('artefactEditor'));
const artefact = computed(() => modalProps.value?.artefact);
const discussionId = computed(() => modalProps.value?.discussionId);

const isEditing = computed(() => !!artefact.value?.title);
const title = ref('');
const content = ref('');
const keptImages = ref([]); // URLs of images to keep
const newImageFiles = ref([]); // New File objects
const newImagePreviews = ref([]); // Data URLs for previewing new images
const imageInput = ref(null);
const updateInPlace = ref(false); // New state for the switch

watch(
    () => uiStore.isModalOpen('artefactEditor'),
    (isOpen) => {
        if (isOpen) {
            title.value = artefact.value?.title || '';
            content.value = artefact.value?.content || '';
            keptImages.value = (artefact.value?.images || []).map(img_b64 => `data:image/png;base64,${img_b64}`);
            newImageFiles.value = [];
            newImagePreviews.value = [];
            updateInPlace.value = false; // Reset switch on open
        }
    },
    { immediate: true }
);

function triggerImageUpload() {
    imageInput.value?.click();
}

async function handleImageSelection(event) {
    const files = Array.from(event.target.files);
    for (const file of files) {
        newImageFiles.value.push(file);
        const reader = new FileReader();
        reader.onload = (e) => {
            newImagePreviews.value.push(e.target.result);
        };
        reader.readAsDataURL(file);
    }
    event.target.value = '';
}

function removeKeptImage(index) {
    keptImages.value.splice(index, 1);
}

function removeNewImage(index) {
    newImageFiles.value.splice(index, 1);
    newImagePreviews.value.splice(index, 1);
}

function removeAllImages() {
    keptImages.value = [];
    newImageFiles.value = [];
    newImagePreviews.value = [];
}

const allImages = computed(() => [...keptImages.value, ...newImagePreviews.value]);

async function handleSubmit() {
    if (!title.value.trim() || !discussionId.value) {
        uiStore.addNotification('Title is required.', 'warning');
        return;
    }

    const newImagesB64 = await Promise.all(
        newImageFiles.value.map(file => {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        })
    );
    
    const keptImagesB64 = keptImages.value.map(url => url.split(',')[1]);

    if (isEditing.value) {
        await discussionsStore.updateArtefact({
            discussionId: discussionId.value,
            artefactTitle: artefact.value.title,
            newContent: content.value,
            newImagesB64: newImagesB64,
            keptImagesB64: keptImagesB64,
            version: artefact.value.version, // Pass the version being edited
            updateInPlace: updateInPlace.value // Pass the switch state
        });
    } else {
        await discussionsStore.createManualArtefact({
            discussionId: discussionId.value,
            title: title.value,
            content: content.value,
            imagesB64: [...keptImagesB64, ...newImagesB64],
        });
    }

    uiStore.closeModal('artefactEditor');
}
</script>

<template>
    <GenericModal
        modalName="artefactEditor"
        :title="isEditing ? 'Edit Artefact' : 'Create New Artefact'"
        maxWidthClass="max-w-4xl"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-4">
                <div>
                    <label for="artefact-title" class="label">Title</label>
                    <input
                        id="artefact-title"
                        type="text"
                        v-model="title"
                        class="input-field"
                        :disabled="isEditing"
                        required
                    />
                     <p v-if="isEditing" class="text-xs text-gray-500 mt-1">Title cannot be changed after creation.</p>
                </div>
                <div>
                    <label for="artefact-content" class="label">Content</label>
                    <CodeMirrorEditor v-model="content" class="h-64" />
                </div>
                <div>
                    <div class="flex justify-between items-center mb-2">
                        <label class="label">Images</label>
                        <div class="flex items-center gap-2">
                             <button @click="removeAllImages" type="button" class="btn btn-danger-outline btn-sm" :disabled="allImages.length === 0">
                                <IconTrash class="w-4 h-4 mr-1"/>
                                Remove All
                            </button>
                            <button @click="triggerImageUpload" type="button" class="btn btn-secondary btn-sm">
                                <IconPhoto class="w-4 h-4 mr-1"/>
                                Add Images
                            </button>
                        </div>

                    </div>
                    <input type="file" ref="imageInput" @change="handleImageSelection" multiple accept="image/*" class="hidden">
                    <div v-if="allImages.length === 0" class="text-center text-sm text-gray-500 p-4 border-2 border-dashed rounded-lg">
                        No images attached.
                    </div>
                    <div v-else class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2 p-2 border rounded-lg">
                        <div v-for="(imgSrc, index) in keptImages" :key="`kept-${index}`" class="relative group">
                            <img :src="imgSrc" class="w-full h-24 object-cover rounded-md" alt="Kept image">
                            <button @click="removeKeptImage(index)" type="button" class="absolute top-1 right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">&times;</button>
                        </div>
                        <div v-for="(imgSrc, index) in newImagePreviews" :key="`new-${index}`" class="relative group">
                            <img :src="imgSrc" class="w-full h-24 object-cover rounded-md" alt="New image preview">
                            <button @click="removeNewImage(index)" type="button" class="absolute top-1 right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">&times;</button>
                        </div>
                    </div>
                </div>
                <!-- New Switch for Update In-Place -->
                <div v-if="isEditing" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <span class="flex-grow flex flex-col">
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Update Current Version</span>
                        <span class="text-sm text-gray-500 dark:text-gray-400">
                            {{ updateInPlace ? 'Overwrite this version directly.' : 'Create a new version with your changes.' }}
                        </span>
                    </span>
                    <button @click="updateInPlace = !updateInPlace" type="button" :class="[updateInPlace ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[updateInPlace ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>
            </form>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('artefactEditor')" type="button" class="btn btn-secondary">Cancel</button>
            <button @click="handleSubmit" type="button" class="btn btn-primary">{{ isEditing ? 'Save Changes' : 'Create Artefact' }}</button>
        </template>
    </GenericModal>
</template>