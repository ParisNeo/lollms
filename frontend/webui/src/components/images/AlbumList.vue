<script setup>
import { computed, ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useImageStore } from '../../stores/images';
import { useUiStore } from '../../stores/ui';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';

const props = defineProps({
    searchTerm: { type: String, default: '' }
});

const imageStore = useImageStore();
const uiStore = useUiStore();
const router = useRouter();
const route = useRoute();

const isAlbumsSectionOpen = ref(true);

onMounted(() => {
    imageStore.fetchAlbums();
    imageStore.fetchImages();
});

const albums = computed(() => {
    let list = imageStore.albums || [];
    if (props.searchTerm) {
        const lower = props.searchTerm.toLowerCase();
        list = list.filter(a => (a.name || '').toLowerCase().includes(lower));
    }
    return list;
});

const filteredImages = computed(() => {
    let list = imageStore.images || [];
    if (props.searchTerm) {
        const lower = props.searchTerm.toLowerCase();
        list = list.filter(img => 
            (img.prompt || '').toLowerCase().includes(lower) || 
            (img.model || '').toLowerCase().includes(lower) ||
            (img.filename || '').toLowerCase().includes(lower)
        );
    }
    return list;
});

const selectedAlbumId = computed(() => imageStore.selectedAlbumId);

function selectAlbum(albumId) {
    imageStore.selectedAlbumId = albumId;
    if (!route.path.startsWith('/image-studio')) {
        router.push('/image-studio');
    }
    imageStore.fetchImages(1);
}

function openImageInEditor(img) {
    router.push(`/image-studio/edit/${img.id}`);
}

function openImageInStudio(img) {
    if (!route.path.startsWith('/image-studio')) {
        router.push('/image-studio');
    }
}

function openLightbox(img, idx) {
    const list = filteredImages.value.map(i => ({
        src: `/api/image-studio/${i.id}/file`,
        prompt: i.prompt || 'Image Creation'
    }));
    uiStore.openImageViewer({ imageList: list, startIndex: idx });
}

async function handleCreateAlbum() {
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'New Album',
        message: 'Enter album name:',
        confirmText: 'Create',
        inputType: 'text',
        inputPlaceholder: 'My Album'
    });
    if (confirmed && value) {
        await imageStore.createAlbum(value);
    }
}

async function renameAlbum(album) {
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'Rename Album',
        message: 'Enter new name:',
        confirmText: 'Rename',
        inputType: 'text',
        inputValue: album.name
    });
    if (confirmed && value) {
        await imageStore.updateAlbum(album.id, value);
    }
}

async function deleteAlbum(album) {
    const { confirmed } = await uiStore.showConfirmation({
        title: `Delete Album "${album.name}"?`,
        message: 'Images within will be ungrouped, not deleted.',
        confirmText: 'Delete',
        danger: true
    });
    if (confirmed) {
        await imageStore.deleteAlbum(album.id);
    }
}

async function handleDeleteImage(img) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Image',
        message: 'Are you sure you want to permanently delete this image from your gallery?',
        confirmText: 'Delete',
        danger: true
    });
    if (confirmed) {
        await imageStore.deleteImage(img.id);
    }
}

function formatTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}
</script>

<template>
    <div class="h-full flex flex-col space-y-3">
        <!-- 1. ALBUMS & COLLECTIONS SECTION -->
        <div class="space-y-1 shrink-0">
            <!-- All Images Master Row -->
            <div 
                @click="selectAlbum(null)"
                class="group flex items-center justify-between p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                :class="{'bg-pink-50 dark:bg-pink-900/20 text-pink-700 dark:text-pink-300 font-bold': selectedAlbumId === null}"
            >
                <div class="flex items-center gap-2.5 min-w-0">
                    <IconPhoto class="w-4 h-4 shrink-0 text-pink-500" />
                    <span class="text-xs truncate">All Images</span>
                </div>
                <span class="text-[10px] font-mono font-bold text-gray-400 bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">
                    {{ imageStore.totalImages || imageStore.images.length }}
                </span>
            </div>

            <!-- Albums Dropdown Header -->
            <div class="flex items-center justify-between pt-2 pb-1 px-1">
                <button 
                    @click="isAlbumsSectionOpen = !isAlbumsSectionOpen"
                    class="flex items-center gap-1 text-[10px] font-black uppercase tracking-widest text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
                >
                    <IconChevronRight class="w-3 h-3 transition-transform" :class="{'rotate-90': isAlbumsSectionOpen}" />
                    <span>Albums ({{ albums.length }})</span>
                </button>

                <button 
                    @click="handleCreateAlbum"
                    class="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded text-gray-400 hover:text-pink-500 transition-colors"
                    title="Create New Album"
                >
                    <IconPlus class="w-3.5 h-3.5" />
                </button>
            </div>

            <!-- Albums List -->
            <div v-show="isAlbumsSectionOpen" class="space-y-0.5 pl-2">
                <div v-for="album in albums" :key="album.id" 
                     class="group flex items-center justify-between p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                     :class="{'bg-pink-50 dark:bg-pink-900/20 text-pink-700 dark:text-pink-300 font-bold': selectedAlbumId === album.id}"
                     @click="selectAlbum(album.id)"
                >
                    <div class="flex items-center gap-2 min-w-0">
                        <IconFolder class="w-3.5 h-3.5 shrink-0 text-amber-500" />
                        <span class="text-xs truncate">{{ album.name }}</span>
                    </div>
                    
                    <div class="opacity-0 group-hover:opacity-100 transition-opacity" @click.stop>
                        <DropdownMenu icon="ellipsis-vertical" buttonClass="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400">
                            <button @click="renameAlbum(album)" class="menu-item"><IconPencil class="w-3.5 h-3.5 mr-2" />Rename</button>
                            <button @click="deleteAlbum(album)" class="menu-item text-red-500"><IconTrash class="w-3.5 h-3.5 mr-2" />Delete</button>
                        </DropdownMenu>
                    </div>
                </div>
            </div>
        </div>

        <div class="border-t dark:border-gray-800 pt-2 shrink-0 flex justify-between items-center px-1">
            <span class="text-[10px] font-black uppercase tracking-widest text-gray-400">
                Gallery Stream ({{ filteredImages.length }})
            </span>
            <button 
                @click="imageStore.fetchImages()" 
                class="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded text-gray-400 hover:text-blue-500 transition-colors"
                title="Refresh Gallery Stream"
            >
                <IconPhoto class="w-3.5 h-3.5" :class="{'animate-spin': imageStore.isLoading}" />
            </button>
        </div>

        <!-- 2. IMAGE ITEMS LIST -->
        <div class="grow overflow-y-auto custom-scrollbar space-y-1 pr-1">
            <div v-if="imageStore.isLoading && filteredImages.length === 0" class="text-center py-8">
                <IconAnimateSpin class="w-6 h-6 text-pink-500 animate-spin mx-auto mb-2" />
                <p class="text-[10px] text-gray-400 uppercase font-black tracking-widest">Loading creations...</p>
            </div>

            <div v-else-if="filteredImages.length === 0" class="text-center py-10 text-gray-400 space-y-1">
                <IconPhoto class="w-8 h-8 mx-auto opacity-20" />
                <p class="text-xs font-bold uppercase tracking-widest">{{ searchTerm ? 'No matching images' : 'No images in album' }}</p>
                <p class="text-[10px] text-gray-500">Create or upload images in Image Studio.</p>
            </div>

            <!-- List Item Cards -->
            <div 
                v-for="(img, idx) in filteredImages" 
                :key="img.id"
                class="group flex items-center gap-2.5 p-1.5 rounded-xl border transition-all shadow-xs cursor-pointer"
                :class="route.params.id === img.id ? 'border-pink-500 bg-pink-50/80 dark:bg-pink-950/40 ring-1 ring-pink-500/50' : 'border-gray-100 dark:border-gray-800/80 bg-white dark:bg-gray-900/60 hover:border-pink-300 dark:hover:border-pink-900/50 hover:bg-pink-50/30 dark:hover:bg-pink-950/10'"
                @click="openImageInEditor(img)"
            >
                <!-- Thumbnail -->
                <div class="relative w-12 h-12 rounded-lg overflow-hidden shrink-0 bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
                    <AuthenticatedImage 
                        :src="`/api/image-studio/${img.id}/thumbnail?size=128`" 
                        class="w-full h-full object-cover" 
                    />
                </div>

                <!-- Info Column -->
                <div class="grow min-w-0 flex flex-col justify-center leading-tight">
                    <p class="text-xs font-bold text-gray-800 dark:text-gray-200 truncate" :title="img.prompt || 'Untitled Image'">
                        {{ img.prompt || 'Image Creation' }}
                    </p>
                    <div class="flex items-center gap-1.5 mt-1 text-[9px] font-mono text-gray-400">
                        <span v-if="img.width && img.height">{{ img.width }}×{{ img.height }}</span>
                        <span>•</span>
                        <span>{{ formatTime(img.created_at) }}</span>
                    </div>
                </div>

                <!-- Hover Actions -->
                <div class="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity" @click.stop>
                    <button 
                        @click.stop="openViewer(img, idx)" 
                        class="p-1 text-gray-400 hover:text-blue-500 rounded hover:bg-gray-100 dark:hover:bg-gray-800" 
                        title="Lightbox Preview"
                    >
                        <IconMaximize class="w-3.5 h-3.5" />
                    </button>
                    <button 
                        @click.stop="openImageInEditor(img)" 
                        class="p-1 text-gray-400 hover:text-purple-500 rounded hover:bg-gray-100 dark:hover:bg-gray-800" 
                        title="Open in Layer Canvas Editor"
                    >
                        <IconPencil class="w-3.5 h-3.5" />
                    </button>
                    <button 
                        @click.stop="handleDeleteImage(img)" 
                        class="p-1 text-gray-400 hover:text-red-500 rounded hover:bg-gray-100 dark:hover:bg-gray-800" 
                        title="Delete Image"
                    >
                        <IconTrash class="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.menu-item { @apply flex items-center w-full px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left; }
</style>