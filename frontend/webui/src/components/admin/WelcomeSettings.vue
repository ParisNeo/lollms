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

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { globalSettings, funFacts, funFactCategories, isLoadingFunFacts, isLoadingFunFactCategories } = storeToRefs(adminStore);

const form = ref({});
const isLoading = ref(false);
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

onMounted(() => {
    adminStore.fetchGlobalSettings();
    adminStore.fetchFunFacts();
    adminStore.fetchFunFactCategories();
});

watch(() => globalSettings.value, populateForm, { deep: true });
watch(form, (newValue) => { hasChanges.value = JSON.stringify(newValue) !== pristineState; }, { deep: true });

function populateForm() {
    const newFormState = {};
    if (welcomeSettings.value.length > 0) {
        welcomeSettings.value.forEach(setting => {
            newFormState[setting.key] = setting.value;
        });
        form.value = newFormState;
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
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
    isLoading.value = true;
    try {
        await adminStore.removeWelcomeLogo();
        logoFile.value = null;
        logoPreview.value = null;
    } finally {
        isLoading.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        const settingsToUpdate = { welcome_text: form.value.welcome_text, welcome_slogan: form.value.welcome_slogan };
        await adminStore.updateGlobalSettings(settingsToUpdate);
        if (logoFile.value) {
            await adminStore.uploadWelcomeLogo(logoFile.value);
            logoFile.value = null;
            logoPreview.value = null;
        }
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
</script>

<template>
    <div class="space-y-12">
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-6 border-b dark:border-gray-700"><h3 class="text-xl font-semibold">Welcome Page Settings</h3></div>
            <form @submit.prevent="handleSave" class="p-6 space-y-6">
                <div><label for="welcome_text" class="label">Main Welcome Text</label><input id="welcome_text" v-model="form.welcome_text" type="text" class="input-field mt-1"></div>
                <div><label for="welcome_slogan" class="label">Slogan</label><input id="welcome_slogan" v-model="form.welcome_slogan" type="text" class="input-field mt-1"></div>
                <div>
                    <label class="label">Custom Logo</label>
                    <div class="mt-2 flex items-center gap-x-4">
                        <img :src="logoPreview || form.welcome_logo_url || logoDefault" alt="Logo Preview" class="h-16 w-16 object-contain rounded-md bg-gray-100 dark:bg-gray-700" />
                        <input type="file" @change="handleFileSelect" accept="image/*" class="hidden" ref="logoInput">
                        <button type="button" @click="$refs.logoInput.click()" class="btn btn-secondary">Change</button>
                        <button v-if="form.welcome_logo_url" type="button" @click="handleRemoveLogo" class="btn btn-danger-outline">Remove</button>
                    </div>
                </div>
                <div class="flex justify-end pt-4 border-t dark:border-gray-700"><button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">{{ isLoading ? 'Saving...' : 'Save Settings' }}</button></div>
            </form>
        </div>
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-6 border-b dark:border-gray-700 flex justify-between items-center"><h3 class="text-xl font-semibold">Fun Facts Management</h3><div class="flex gap-2"><button @click="$refs.importInput.click()" class="btn btn-secondary btn-sm">Import Category</button><input type="file" ref="importInput" @change="handleImportCategory" accept=".json" class="hidden"><button @click="adminStore.exportFunFacts()" class="btn btn-secondary btn-sm">Export All</button></div></div>
            <div class="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div>
                    <div class="flex justify-between items-center mb-2"><h4 class="font-semibold">Categories</h4><button @click="openCategoryModal()" class="btn btn-secondary btn-sm"><IconPlus class="w-4 h-4 mr-1"/>New</button></div>
                    <div class="border rounded-lg overflow-hidden dark:border-gray-700 max-h-96 overflow-y-auto"><div v-if="isLoadingFunFactCategories">Loading...</div><ul v-else class="divide-y dark:divide-gray-700"><li v-for="cat in funFactCategories" :key="cat.id" @click="selectedCategoryId = cat.id" class="p-2 flex items-center justify-between cursor-pointer" :class="selectedCategoryId === cat.id ? 'bg-blue-100 dark:bg-blue-900/50' : 'hover:bg-gray-50 dark:hover:bg-gray-700/50'"><div><span class="font-medium text-sm">{{ cat.name }}</span><div class="w-4 h-4 rounded-full inline-block ml-2" :style="{ backgroundColor: cat.color }"></div></div><div class="flex items-center gap-1"><button @click.stop="handleExportCategory(cat)" class="btn-icon"><IconArrowDownTray class="w-4 h-4"/></button><button @click.stop="openCategoryModal(cat)" class="btn-icon"><IconPencil class="w-4 h-4"/></button><button @click.stop="deleteCategory(cat)" class="btn-icon-danger"><IconTrash class="w-4 h-4"/></button></div></li></ul></div>
                </div>
                <div>
                    <div class="flex justify-between items-center mb-2"><h4 class="font-semibold">{{ selectedCategoryId ? `Facts in "${funFactCategories.find(c=>c.id===selectedCategoryId)?.name}"` : 'Select a Category' }}</h4><button @click="openFactModal()" :disabled="!selectedCategoryId" class="btn btn-secondary btn-sm"><IconPlus class="w-4 h-4 mr-1"/>New</button></div>
                    <div class="border rounded-lg overflow-hidden dark:border-gray-700 max-h-96 overflow-y-auto"><div v-if="isLoadingFunFacts">Loading...</div><div v-else-if="!selectedCategoryId" class="p-4 text-center text-sm text-gray-500">Select a category to view its facts.</div><ul v-else class="divide-y dark:divide-gray-700"><li v-for="fact in filteredFacts" :key="fact.id" class="p-2 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50"><p class="text-sm flex-grow pr-2 truncate" :title="fact.content">{{ fact.content }}</p><div class="flex items-center gap-1 flex-shrink-0"><button @click="openFactModal(fact)" class="btn-icon"><IconPencil class="w-4 h-4"/></button><button @click="deleteFact(fact)" class="btn-icon-danger"><IconTrash class="w-4 h-4"/></button></div></li></ul></div>
                </div>
            </div>
        </div>
    </div>
</template>