<script>
import { mapState, mapActions } from 'pinia';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

export default {
  name: 'DataStoresModal',
  components: { GenericModal },
  computed: {
    ...mapState(useDataStore, ['ownedDataStores', 'sharedDataStores']),
  },
  methods: {
    ...mapActions(useDataStore, ['deleteDataStore']), // Renamed from removeDataStore
    ...mapActions(useUiStore, ['closeModal', 'openModal', 'showConfirmation']),

    openEditor(store = null) {
      // Pass the store object for editing, or null for creating
      this.openModal('dataStoreEditor', store);
    },
    openShareModal(store) {
      this.openModal('shareDataStore', { store });
    },
    openFileManagement(store) {
      this.openModal('fileManagement', { store });
    },
    async handleDelete(store) {
        const confirmed = await this.showConfirmation({
            title: `Delete '${store.name}'?`,
            message: 'Are you sure you want to delete this data store and all its indexed files? This cannot be undone.',
            confirmText: 'Delete Forever'
        });
        if (confirmed) {
            this.deleteDataStore(store.id);
        }
    }
  }
};
</script>

<template>
  <GenericModal modalName="dataStores" title="Manage Data Stores" maxWidthClass="max-w-2xl">
    <template #body>
      <div class="space-y-6">
        <!-- Header with Create Button -->
        <div class="flex justify-between items-center pb-2 border-b dark:border-gray-700">
            <h3 class="text-lg font-medium">Your Data Stores</h3>
            <button @click="openEditor(null)" class="btn btn-primary !text-sm !py-1.5">
                + Create New Store
            </button>
        </div>
        
        <!-- Owned Stores Section -->
        <section>
          <div class="max-h-72 overflow-y-auto space-y-2 pr-2">
            <p v-if="ownedDataStores.length === 0" class="italic text-sm text-gray-500">You don't own any data stores.</p>
            <div v-for="store in ownedDataStores" :key="store.id" class="flex justify-between items-center py-1.5 px-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-sm">
                <div class="flex-1 min-w-0">
                    <strong class="text-gray-800 dark:text-gray-100 truncate block">{{ store.name }}</strong>
                    <p class="text-xs text-gray-500 dark:text-gray-400 truncate">{{ store.description || 'No description' }}</p>
                </div>
                <div class="space-x-1 flex-shrink-0">
                    <button @click="openFileManagement(store)" title="Manage Files" class="p-1.5 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded-full text-blue-500"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 0 0-1.883 2.542l.857 6a2.25 2.25 0 0 0 2.227 1.932H19.05a2.25 2.25 0 0 0 2.227-1.932l.857-6a2.25 2.25 0 0 0-1.883-2.542m-16.5 0V6A2.25 2.25 0 0 1 6 3.75h3.879a1.5 1.5 0 0 1 1.06.44l2.122 2.12a1.5 1.5 0 0 0 1.06.44H18A2.25 2.25 0 0 1 20.25 9v.776" /></svg></button>
                    <button @click="openShareModal(store)" title="Share" class="p-1.5 hover:bg-green-100 dark:hover:bg-green-900/50 rounded-full text-green-500"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.243-3.72a9.094 9.094 0 0 1-3.741-.479 3 3 0 0 1-4.682-2.72m.243 3.72a9.094 9.094 0 0 0-3.741-.479 3 3 0 0 0-4.682-2.72M12 12.75a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm0 0a9.094 9.094 0 0 0-3.741-.479 3 3 0 0 0-4.682-2.72M12 12.75a9.094 9.094 0 0 1 3.741-.479 3 3 0 0 1 4.682-2.72m12 12.75a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm-15 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg></button>
                    <button @click="openEditor(store)" title="Edit" class="p-1.5 hover:bg-yellow-100 dark:hover:bg-yellow-900/50 rounded-full text-yellow-500"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" /></svg></button>
                    <button @click="handleDelete(store)" title="Delete" class="p-1.5 hover:bg-red-100 dark:hover:bg-red-900/50 rounded-full text-red-500"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12.508 0A48.067 48.067 0 0 1 7.8 5.397m7.454 0M12 10.75h.008v.008H12v-.008Z" /></svg></button>
                </div>
            </div>
          </div>
        </section>

        <!-- Shared Stores Section -->
        <section>
          <h4 class="text-md font-medium mb-2">Shared With You</h4>
          <div class="max-h-48 overflow-y-auto space-y-2 border dark:border-gray-600 rounded p-3">
             <p v-if="sharedDataStores.length === 0" class="italic text-sm text-gray-500">No data stores have been shared with you.</p>
             <div v-for="store in sharedDataStores" :key="store.id" class="flex justify-between items-center py-1.5 px-2 text-sm">
                <div>
                    <strong>{{ store.name }}</strong> (from {{ store.owner_username }})
                </div>
             </div>
          </div>
        </section>
      </div>
    </template>
    <template #footer>
        <button @click="closeModal('dataStores')" class="btn btn-secondary">Close</button>
    </template>
  </GenericModal>
</template>