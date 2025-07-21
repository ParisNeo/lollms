<script setup>
import { ref } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const fileInput = ref(null);
const selectedFile = ref(null);
const isDragging = ref(false);

function handleFileSelect(event) {
    const files = event.target.files;
    if (files.length > 0) {
        if (files[0].name === 'webui.db') {
            selectedFile.value = files[0];
        } else {
            uiStore.addNotification("Invalid file. Please select 'webui.db'.", 'error');
            selectedFile.value = null;
        }
    }
}

function triggerFileSelect() {
    fileInput.value?.click();
}

function handleDrop(event) {
    isDragging.value = false;
    const files = event.dataTransfer.files;
    if (files.length > 0) {
        if (files[0].name === 'webui.db') {
            selectedFile.value = files[0];
        } else {
            uiStore.addNotification("Invalid file. Please select 'webui.db'.", 'error');
            selectedFile.value = null;
        }
    }
}

async function handleImport() {
    if (!selectedFile.value) {
        uiStore.addNotification('Please select a file to import.', 'warning');
        return;
    }
    try {
        await adminStore.importOpenWebUIData(selectedFile.value);
        selectedFile.value = null; // Clear after successful start
    } catch (error) {
        // Error is handled by global interceptor
    }
}

async function handlePurge() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Purge Temporary Files?',
        message: 'This will delete all temporary uploaded files older than 24 hours. This action cannot be undone.',
        confirmText: 'Yes, Purge'
    });
    if (confirmed) {
        try {
            await adminStore.purgeUnusedUploads();
        } catch (error) {
            // Error is handled by global interceptor
        }
    }
}

</script>

<template>
    <div class="space-y-8">
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-6 border-b border-gray-200 dark:border-gray-700">
                <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                    Data Import
                </h3>
                <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Import data from other compatible applications.
                </p>
            </div>
            <div class="p-6">
                <div class="space-y-6">
                    <div>
                        <h4 class="text-base font-medium text-gray-800 dark:text-gray-200">Import from Open-WebUI</h4>
                        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                            Migrate users and discussions from an Open-WebUI instance by uploading its `webui.db` database file. The migration will run in the background.
                        </p>
                    </div>
                    <div>
                        <input type="file" ref="fileInput" @change="handleFileSelect" accept=".db" class="hidden" />
                        <div 
                            @click="triggerFileSelect"
                            @dragover.prevent="isDragging = true"
                            @dragleave.prevent="isDragging = false"
                            @drop.prevent="handleDrop"
                            class="mt-2 flex justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors"
                            :class="isDragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'">
                            <div class="text-center">
                                <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true">
                                    <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
                                </svg>
                                <div v-if="selectedFile" class="mt-4 text-sm text-gray-600 dark:text-gray-300">
                                    <p class="font-semibold">{{ selectedFile.name }}</p>
                                    <p class="text-xs text-gray-500">{{ (selectedFile.size / 1024 / 1024).toFixed(2) }} MB</p>
                                </div>
                                <p v-else class="mt-4 flex text-sm leading-6 text-gray-600 dark:text-gray-400">
                                    <span class="font-semibold text-blue-600 dark:text-blue-400 hover:text-blue-500">Upload a file</span>
                                    <span class="pl-1">or drag and drop</span>
                                </p>
                                <p class="text-xs leading-5 text-gray-600 dark:text-gray-400">webui.db file only</p>
                            </div>
                        </div>
                    </div>
                    <div class="flex justify-end">
                        <button 
                            @click="handleImport" 
                            :disabled="!selectedFile || adminStore.isImporting"
                            class="btn btn-primary"
                        >
                            {{ adminStore.isImporting ? 'Importing...' : 'Start Import' }}
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-6 border-b border-gray-200 dark:border-gray-700">
                <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                    Data Maintenance
                </h3>
                <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Perform cleanup and maintenance tasks.
                </p>
            </div>
            <div class="p-6 flex items-center justify-between">
                <div>
                    <h4 class="font-medium text-gray-800 dark:text-gray-200">Purge Unused Uploads</h4>
                    <p class="text-sm text-gray-500 dark:text-gray-400">
                        Deletes temporary files uploaded more than 24 hours ago that are not part of a discussion.
                    </p>
                </div>
                <button @click="handlePurge" class="btn btn-danger">
                    Start Purge Task
                </button>
            </div>
        </div>
    </div>
</template>