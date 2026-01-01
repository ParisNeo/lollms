<script setup>
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useImageStore } from '../../stores/images';
import { useUiStore } from '../../stores/ui';
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';

const props = defineProps({
    searchTerm: { type: String, default: '' }
});

const imageStore = useImageStore();
const uiStore = useUiStore();
const router = useRouter();

const albums = computed(() => {
    let list = imageStore.albums;
    if (props.searchTerm) {
        const lower = props.searchTerm.toLowerCase();
        list = list.filter(a => a.name.toLowerCase().includes(lower));
    }
    return list;
});

const selectedAlbumId = computed(() => imageStore.selectedAlbumId);

function selectAlbum(albumId) {
    imageStore.selectedAlbumId = albumId;
    router.push('/image-studio');
    // Force refresh images for this selection
    imageStore.fetchImages();
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
        confirmText: 'Delete'
    });
    if (confirmed) {
        await imageStore.deleteAlbum(album.id);
    }
}
</script>

<template>
    <div class="space-y-1">
        <!-- "All Images" special item -->
        <div 
            @click="selectAlbum(null)"
            class="group flex items-center justify-between p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
            :class="{'bg-pink-50 dark:bg-pink-900/20': selectedAlbumId === null}"
        >
            <div class="flex items-center gap-3 min-w-0">
                <IconPhoto class="w-4 h-4 flex-shrink-0 text-pink-500" />
                <span class="text-sm font-medium text-slate-700 dark:text-gray-200 truncate">All Images</span>
            </div>
        </div>

        <div v-for="album in albums" :key="album.id" 
             class="group flex items-center justify-between p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
             :class="{'bg-pink-50 dark:bg-pink-900/20': selectedAlbumId === album.id}"
             @click="selectAlbum(album.id)"
        >
            <div class="flex items-center gap-3 min-w-0">
                <IconFolder class="w-4 h-4 flex-shrink-0 text-yellow-500" />
                <span class="text-sm font-medium text-slate-700 dark:text-gray-200 truncate">{{ album.name }}</span>
            </div>
            
            <div class="opacity-0 group-hover:opacity-100 transition-opacity" @click.stop>
                <DropdownMenu icon="ellipsis-vertical" buttonClass="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500">
                    <button @click="renameAlbum(album)" class="menu-item"><IconPencil class="w-4 h-4 mr-2" />Rename</button>
                    <button @click="deleteAlbum(album)" class="menu-item text-red-500"><IconTrash class="w-4 h-4 mr-2" />Delete</button>
                </DropdownMenu>
            </div>
        </div>
        
        <div v-if="albums.length === 0" class="text-center p-4 text-xs text-gray-400 italic">
            No albums created.
        </div>
    </div>
</template>

<style scoped>
.menu-item { @apply flex items-center w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left; }
</style>
