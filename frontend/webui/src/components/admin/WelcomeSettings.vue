
<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import logoDefault from '../../assets/logo.png';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { globalSettings, funFacts, funFactCategories, isLoadingFunFacts, isLoadingFunFactCategories } = storeToRefs(adminStore);

// Initialize form with default structure to prevent reactivity issues
const form = ref({
    welcome_text: '',
    welcome_slogan: '',
    welcome_logo_url: ''
});
const isLoading = ref(false);
const isRemovingLogo = ref(false); // Specific loading state for logo removal
const hasChanges = ref(false);
const logoFile = ref(null);
const logoPreview = ref(null);
let pristineState = '{}';
const selectedCategoryId = ref(null);

const welcomeSettings = computed(() => globalSettings.value.filter(s => s.category === 'Welcome Page'));
const filteredFacts = computed(() => {
    if (!selectedCategoryId.value) return [];
    return funFacts.value.filter(f => f.category.id === selectedCategoryId.value);
});
const selectedCategoryName = computed(() => {
    if (!selectedCategoryId.value) return 'Select a Category';
    const cat = funFactCategories.value.find(c => c.id === selectedCategoryId.value);
    return cat ? cat.name : 'Select a Category';
});


onMounted(() => {
    // These fetches are now more resilient due to pinia's design (won't re-fetch if data exists)
    adminStore.fetchGlobalSettings();
    adminStore.fetchFunFacts();
    adminStore.fetchFunFactCategories();
});

watch(() => globalSettings.value, populateForm, { deep: true, immediate: true }); // immediate to run on mount
watch(form, (newValue) => { hasChanges.value = JSON.stringify(newValue) !== pristineState; }, { deep: true });

function populateForm() {
    if (welcomeSettings.value.length > 0) {
        const settingsMap = welcomeSettings.value.reduce((acc, setting) => {
            acc[setting.key] = setting.value;
            return acc;
        }, {});
        
        // Assign to form ref, ensuring all keys are present
        form.value.welcome_text = settingsMap.welcome_text || '';
        form.value.welcome_slogan = settingsMap.welcome_slogan || '';
        form.value.welcome_logo_url = settingsMap.welcome_logo_url || '';
        
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
        logoPreview.value = null; // Clear preview on re-populate
        logoFile.value = null; // Clear file on re-populate
    }
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file && file.type.startsWith('image/')) {
        logoFile.value = file;
        const reader = new FileReader();
        reader.onload = (e) => { logoPreview.value = e.target.result; };
        reader.readAsDataURL(file);
        hasChanges.value = true;
    }
}

async function handleRemoveLogo() {
    isRemovingLogo.value = true;
    try {
        await adminStore.removeWelcomeLogo();
        // The store action will trigger a fetchGlobalSettings, which will re-populate the form.
    } finally {
        isRemovingLogo.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        const settingsToUpdate = { welcome_text: form.value.welcome_text, welcome_slogan: form.value.welcome_slogan };
        
        const promises = [adminStore.updateGlobalSettings(settingsToUpdate)];

        if (logoFile.value) {
            promises.push(adminStore.uploadWelcomeLogo(logoFile.value));
        }
        
        await Promise.all(promises);
        
        // After save, reset pristine state to the new form state
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
        logoFile.value = null;
        logoPreview.value = null;
        
    } finally {
        isLoading.value = false;
    }
}

function openCategoryModal(category = null) { uiStore.openModal('funFactCategory', { category, onSave: adminStore.fetchFunFactCategories }); }
function openFactModal(fact = null) {
    if (!selectedCategoryId.value && !fact) {
        uiStore.addNotification('Please select a category first.', 'warning');
        return;
    }
    uiStore.openModal('funFact', { fact, preselectedCategoryId: selectedCategoryId.value, onSave: adminStore.fetchFunFacts });
}
async function deleteCategory(category) {
    if (await uiStore.showConfirmation({ title: 'Delete Category and its Facts?', message: `This will permanently delete "${category.name}" and all facts inside it. This action cannot be undone.`, confirmText: 'Delete All'})) {
        await adminStore.deleteFunFactCategory(category.id);
        if (selectedCategoryId.value === category.id) {
            selectedCategoryId.value = null;
        }
    }
}
async function deleteFact(fact) { if (await uiStore.showConfirmation({ title: 'Delete Fun Fact?', message: 'Are you sure you want to delete this fact?', confirmText: 'Delete' })) { await adminStore.deleteFunFact(fact.id); } }
async function handleExportCategory(category) { await adminStore.exportCategory(category.id, category.name); }
async function handleImportCategory(event) {
    const file = event.target.files[0];
    if (file) { await adminStore.importCategoryFromFile(file); }
    event.target.value = ''; // Reset file input
}
async function handleExportAll() {
    await adminStore.exportFunFacts();
}
function openGenerateFunFactsModal() {
    uiStore.openModal('generateFunFacts');
}
</script>

<template>
    <div class="space-y-12">
        <!-- Welcome Page Settings -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-6 border-b dark:border-gray-700">
                <h3 class="text-xl font-semibold">Welcome Page Settings</h3>
            </div>
            <div v-if="adminStore.isLoadingSettings && !Object.keys(form).length" class="p-6 text-center text-gray-500">Loading settings...</div>
            <form v-else @submit.prevent="handleSave" class="p-6 space-y-6">
                <div>
                    <label for="welcome_text" class="label">Main Welcome Text</label>
                    <input id="welcome_text" v-model="form.welcome_text" type="text" class="input-field mt-1">
                </div>
                <div>
                    <label for="welcome_slogan" class="label">Slogan</label>
                    <input id="welcome_slogan" v-model="form.welcome_slogan" type="text" class="input-field mt-1">
                </div>
                <div>
                    <label class="label">Custom Logo</label>
                    <div class="mt-2 flex items-center gap-x-4">
                        <img :src="logoPreview || form.welcome_logo_url || logoDefault" alt="Logo Preview" class="h-16 w-16 object-contain rounded-md bg-gray-100 dark:bg-gray-700 p-1 border dark:border-gray-600" />
                        <input type="file" @change="handleFileSelect" accept="image/*" class="hidden" ref="logoInput">
                        <button type="button" @click="$refs.logoInput.click()" class="btn btn-secondary">Change</button>
                        <button v-if="form.welcome_logo_url" type="button" @click="handleRemoveLogo" class="btn btn-danger-outline" :disabled="isRemovingLogo">
                            {{ isRemovingLogo ? 'Removing...' : 'Remove' }}
                        </button>
                    </div>
                </div>
                <div class="flex justify-end pt-4 border-t dark:border-gray-700">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">{{ isLoading ? 'Saving...' : 'Save Settings' }}</button>
                </div>
            </form>
        </div>

        <!-- Fun Facts Management -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-6 border-b dark:border-gray-700 flex justify-between items-center flex-wrap gap-2">
                <h3 class="text-xl font-semibold">Fun Facts Management</h3>
                <div class="flex gap-2">
                    <button @click="$refs.importInput.click()" class="btn btn-secondary btn-sm">Import Category</button>
                    <input type="file" ref="importInput" @change="handleImportCategory" accept=".json" class="hidden">
                    <button @click="handleExportAll" class="btn btn-secondary btn-sm">Export All</button>
                </div>
            </div>
            <div class="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div>
                    <div class="flex justify-between items-center mb-2">
                        <h4 class="font-semibold">Categories</h4>
                        <div class="flex items-center gap-2">
                            <button @click="openGenerateFunFactsModal" class="btn btn-secondary btn-sm"><IconSparkles class="w-4 h-4 mr-1"/> Generate with AI</button>
                            <button @click="openCategoryModal()" class="btn btn-secondary btn-sm"><IconPlus class="w-4 h-4 mr-1"/>New</button>
                        </div>
                    </div>
                    <div class="border rounded-lg overflow-hidden dark:border-gray-700 max-h-96 overflow-y-auto">
                        <div v-if="isLoadingFunFactCategories" class="p-4 text-center text-gray-500">Loading...</div>
                        <ul v-else class="divide-y dark:divide-gray-700">
                            <li v-for="cat in funFactCategories" :key="cat.id" @click="selectedCategoryId = cat.id" class="p-3 flex items-center justify-between cursor-pointer transition-colors" :class="selectedCategoryId === cat.id ? 'bg-blue-100 dark:bg-blue-900/50' : 'hover:bg-gray-50 dark:hover:bg-gray-700/50'">
                                <div class="flex items-center gap-3">
                                    <span class="w-5 h-5 rounded-full flex-shrink-0" :style="{ backgroundColor: cat.color }"></span>
                                    <span class="font-medium text-sm truncate" :title="cat.name">{{ cat.name }}</span>
                                </div>
                                <div class="flex items-center gap-1 flex-shrink-0">
                                    <button @click.stop="handleExportCategory(cat)" class="btn-icon" title="Export"><IconArrowDownTray class="w-4 h-4"/></button>
                                    <button @click.stop="openCategoryModal(cat)" class="btn-icon" title="Edit"><IconPencil class="w-4 h-4"/></button>
                                    <button @click.stop="deleteCategory(cat)" class="btn-icon-danger" title="Delete"><IconTrash class="w-4 h-4"/></button>
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>
                <div>
                    <div class="flex justify-between items-center mb-2">
                        <h4 class="font-semibold truncate pr-2" :title="selectedCategoryName">{{ selectedCategoryName }}</h4>
                        <button @click="openFactModal()" :disabled="!selectedCategoryId" class="btn btn-secondary btn-sm"><IconPlus class="w-4 h-4 mr-1"/>New</button>
                    </div>
                    <div class="border rounded-lg overflow-hidden dark:border-gray-700 max-h-96 overflow-y-auto">
                        <div v-if="isLoadingFunFacts" class="p-4 text-center text-gray-500">Loading...</div>
                        <div v-else-if="!selectedCategoryId" class="p-4 text-center text-sm text-gray-500 italic">Select a category to view its facts.</div>
                        <ul v-else class="divide-y dark:divide-gray-700">
                            <li v-for="fact in filteredFacts" :key="fact.id" class="p-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 group">
                                <p class="text-sm flex-grow pr-2" :title="fact.content">{{ fact.content }}</p>
                                <div class="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button @click="openFactModal(fact)" class="btn-icon" title="Edit"><IconPencil class="w-4 h-4"/></button>
                                    <button @click="deleteFact(fact)" class="btn-icon-danger" title="Delete"><IconTrash class="w-4 h-4"/></button>
                                </div>
                            </li>
                            <li v-if="selectedCategoryId && filteredFacts.length === 0" class="p-4 text-center text-sm text-gray-500 italic">No facts in this category yet.</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
