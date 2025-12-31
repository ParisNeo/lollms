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
import IconInfo from '../../assets/icons/IconInfo.vue';
import GenerateFunFactsModal from '../modals/GenerateFunFactsModal.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { globalSettings, funFacts, funFactCategories, isLoadingFunFacts, isLoadingFunFactCategories } = storeToRefs(adminStore);

// Initialize form with default structure
const form = ref({
    welcome_text: '',
    welcome_slogan: '',
    welcome_logo_url: '',
    force_welcome_message: false,
    forced_welcome_message_title: '',
    forced_welcome_message_content: ''
});
const isLoading = ref(false);
const isRemovingLogo = ref(false);
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
    adminStore.fetchGlobalSettings();
    adminStore.fetchFunFacts();
    adminStore.fetchFunFactCategories();
});

watch(() => globalSettings.value, populateForm, { deep: true, immediate: true });
watch(form, (newValue) => { hasChanges.value = JSON.stringify(newValue) !== pristineState; }, { deep: true });

function populateForm() {
    if (welcomeSettings.value.length > 0) {
        const settingsMap = welcomeSettings.value.reduce((acc, setting) => {
            acc[setting.key] = setting.value;
            return acc;
        }, {});
        
        form.value.welcome_text = settingsMap.welcome_text || '';
        form.value.welcome_slogan = settingsMap.welcome_slogan || '';
        form.value.welcome_logo_url = settingsMap.welcome_logo_url || '';
        form.value.force_welcome_message = settingsMap.force_welcome_message || false;
        form.value.forced_welcome_message_title = settingsMap.forced_welcome_message_title || 'System Announcement';
        form.value.forced_welcome_message_content = settingsMap.forced_welcome_message_content || '';
        
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
        logoPreview.value = null;
        logoFile.value = null;
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
    } finally {
        isRemovingLogo.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        const settingsToUpdate = { 
            welcome_text: form.value.welcome_text, 
            welcome_slogan: form.value.welcome_slogan,
            force_welcome_message: form.value.force_welcome_message,
            forced_welcome_message_title: form.value.forced_welcome_message_title,
            forced_welcome_message_content: form.value.forced_welcome_message_content
        };
        
        const promises = [adminStore.updateGlobalSettings(settingsToUpdate)];
        if (logoFile.value) {
            promises.push(adminStore.uploadWelcomeLogo(logoFile.value));
        }
        await Promise.all(promises);
        
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
    if (await uiStore.showConfirmation({ title: 'Delete Category?', message: `Permanently delete "${category.name}" and all facts inside?`, confirmText: 'Delete All'})) {
        await adminStore.deleteFunFactCategory(category.id);
        if (selectedCategoryId.value === category.id) selectedCategoryId.value = null;
    }
}
async function deleteFact(fact) { if (await uiStore.showConfirmation({ title: 'Delete Fun Fact?', message: 'Are you sure?', confirmText: 'Delete' })) { await adminStore.deleteFunFact(fact.id); } }
async function handleExportCategory(category) { await adminStore.exportCategory(category.id, category.name); }
async function handleImportCategory(event) {
    const file = event.target.files[0];
    if (file) await adminStore.importCategoryFromFile(file);
    event.target.value = '';
}
async function handleExportAll() { await adminStore.exportFunFacts(); }
function openGenerateFunFactsModal(nFacts = 5) { 
    uiStore.openModal('generateFunFacts', { categoryId: selectedCategoryId.value, nFacts: nFacts }); 
}

async function toggleCategoryActive(category) {
    const newState = !category.is_active;
    // Optimistic update
    const originalState = category.is_active;
    category.is_active = newState;
    
    try {
        await adminStore.updateFunFactCategory(category.id, { is_active: newState });
    } catch (e) {
        // Revert
        category.is_active = originalState;
        uiStore.addNotification('Failed to update category status.', 'error');
    }
}

</script>

<template>
    <div class="space-y-10">
        <!-- Welcome Branding -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-6 border-b dark:border-gray-700">
                <h3 class="text-xl font-semibold">Welcome Page Branding</h3>
                <p class="text-sm text-gray-500 mt-1">Configure text and visuals for the login and splash screens.</p>
            </div>
            <div v-if="adminStore.isLoadingSettings && !Object.keys(form).length" class="p-6 text-center text-gray-500">Loading...</div>
            <form v-else @submit.prevent="handleSave" class="p-6 space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label for="welcome_text" class="label">Main Branding Text</label>
                        <input id="welcome_text" v-model="form.welcome_text" type="text" class="input-field mt-1" placeholder="LoLLMs">
                    </div>
                    <div>
                        <label for="welcome_slogan" class="label">Slogan</label>
                        <input id="welcome_slogan" v-model="form.welcome_slogan" type="text" class="input-field mt-1" placeholder="One tool to rule them all">
                    </div>
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

                <!-- Force Message Section -->
                <div class="pt-6 mt-6 border-t dark:border-gray-700 space-y-6">
                    <div class="flex items-center justify-between p-4 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-100 dark:border-yellow-900/30 rounded-xl">
                        <div class="flex flex-col">
                            <span class="text-sm font-bold text-yellow-800 dark:text-yellow-400 uppercase tracking-widest">System-wide Announcement</span>
                            <span class="text-xs text-gray-600 dark:text-gray-400 mt-1">Replace random fun facts with a specific message for all users.</span>
                        </div>
                        <button @click="form.force_welcome_message = !form.force_welcome_message" type="button" :class="[form.force_welcome_message ? 'bg-yellow-500' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                            <span :class="[form.force_welcome_message ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>

                    <div v-if="form.force_welcome_message" class="space-y-4 animate-fade-in">
                        <div>
                            <label class="label">Announcement Title</label>
                            <input v-model="form.forced_welcome_message_title" type="text" class="input-field mt-1" placeholder="Maintenance, New Feature, etc.">
                        </div>
                        <div>
                            <label class="label">Announcement Content (Markdown Supported)</label>
                            <textarea v-model="form.forced_welcome_message_content" rows="4" class="input-field mt-1" placeholder="Write your message here..."></textarea>
                        </div>
                        
                        <!-- Markdown Syntax Examples -->
                        <div class="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                            <div class="flex items-center gap-2 mb-2 text-blue-600 dark:text-blue-400">
                                <IconInfo class="w-4 h-4" />
                                <span class="text-xs font-bold uppercase tracking-wider">Markdown Cheat Sheet</span>
                            </div>
                            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-[11px] font-mono leading-relaxed">
                                <div>
                                    <p class="text-gray-400 mb-1 font-sans">Links</p>
                                    <code class="text-blue-500">[Text](URL)</code>
                                </div>
                                <div>
                                    <p class="text-gray-400 mb-1 font-sans">Images</p>
                                    <code class="text-green-500">![Alt](IMG_URL)</code>
                                </div>
                                <div>
                                    <p class="text-gray-400 mb-1 font-sans">Video (YouTube)</p>
                                    <code class="text-red-500">Just paste the full URL on a new line</code>
                                </div>
                            </div>
                        </div>

                        <div class="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-xs text-blue-800 dark:text-blue-300">
                             💡 Users can click this message on the splash screen to keep it visible while they read.
                        </div>
                    </div>
                </div>

                <div class="flex justify-end pt-4 border-t dark:border-gray-700">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">{{ isLoading ? 'Saving...' : 'Save Settings' }}</button>
                </div>
            </form>
        </div>

        <!-- Fun Facts Management (Normal Flow) -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg flex flex-col h-[800px]">
            <div class="p-6 border-b dark:border-gray-700 flex justify-between items-center flex-wrap gap-2 flex-shrink-0">
                <h3 class="text-xl font-semibold">Fun Facts Repository</h3>
                <div class="flex gap-2">
                    <button @click="$refs.importInput.click()" class="btn btn-secondary btn-sm">Import Category</button>
                    <input type="file" ref="importInput" @change="handleImportCategory" accept=".json" class="hidden">
                    <button @click="handleExportAll" class="btn btn-secondary btn-sm">Export All</button>
                </div>
            </div>
            
            <div class="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8 flex-grow min-h-0">
                <!-- Categories List -->
                <div class="flex flex-col min-h-0 h-full">
                    <div class="flex justify-between items-center mb-4 flex-shrink-0">
                        <h4 class="font-semibold text-lg">Categories</h4>
                        <div class="flex items-center gap-2">
                            <button @click="openGenerateFunFactsModal(5)" class="btn btn-secondary btn-sm"><IconSparkles class="w-4 h-4 mr-1"/> AI Generate</button>
                            <button @click="openCategoryModal()" class="btn btn-secondary btn-sm"><IconPlus class="w-4 h-4 mr-1"/>New</button>
                        </div>
                    </div>
                    <div class="border rounded-lg overflow-hidden dark:border-gray-700 flex-grow min-h-0 bg-gray-50 dark:bg-gray-900/50">
                        <div v-if="isLoadingFunFactCategories" class="p-4 text-center text-gray-500">Loading...</div>
                        <ul v-else class="divide-y dark:divide-gray-700 overflow-y-auto h-full">
                            <li v-for="cat in funFactCategories" :key="cat.id" @click="selectedCategoryId = cat.id" class="p-3 flex items-center gap-3 cursor-pointer transition-colors group" :class="selectedCategoryId === cat.id ? 'bg-blue-100 dark:bg-blue-900/50' : 'hover:bg-gray-100 dark:hover:bg-gray-800'">
                                <!-- Actions on the LEFT -->
                                <div class="flex items-center gap-2 flex-shrink-0">
                                     <!-- Activation Toggle -->
                                    <button @click.stop="toggleCategoryActive(cat)" class="focus:outline-none relative" :title="cat.is_active ? 'Deactivate Pack' : 'Activate Pack'">
                                        <div class="w-9 h-5 rounded-full transition-colors duration-200 shadow-sm border dark:border-gray-600" :class="cat.is_active ? 'bg-green-500 border-green-600' : 'bg-gray-200 dark:bg-gray-700'">
                                            <div class="w-3.5 h-3.5 bg-white rounded-full absolute top-0.5 shadow-sm transition-transform duration-200" :class="cat.is_active ? 'translate-x-4.5 left-0.5' : 'translate-x-0.5 left-0.5'"></div>
                                        </div>
                                    </button>
                                    <!-- Edit -->
                                    <button @click.stop="openCategoryModal(cat)" class="p-1.5 rounded-full hover:bg-blue-200 dark:hover:bg-blue-800 text-gray-500 hover:text-blue-600 dark:text-gray-400 transition-colors" title="Edit Category">
                                        <IconPencil class="w-4 h-4"/>
                                    </button>
                                    <!-- Delete -->
                                    <button @click.stop="deleteCategory(cat)" class="p-1.5 rounded-full hover:bg-red-200 dark:hover:bg-red-900 text-gray-500 hover:text-red-600 dark:text-gray-400 transition-colors" title="Delete Category">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                    <!-- Export -->
                                    <button @click.stop="handleExportCategory(cat)" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors" title="Export JSON">
                                        <IconArrowDownTray class="w-4 h-4"/>
                                    </button>
                                </div>
                                
                                <!-- Content -->
                                <div class="flex items-center gap-3 min-w-0 flex-grow pl-2 border-l dark:border-gray-700 ml-1">
                                    <span class="w-4 h-4 rounded-full flex-shrink-0 shadow-sm ring-1 ring-black/5 dark:ring-white/10" :style="{ backgroundColor: cat.color }"></span>
                                    <span class="font-medium text-sm truncate" :class="{'line-through opacity-50': !cat.is_active}">{{ cat.name }}</span>
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>

                <!-- Facts List -->
                <div class="flex flex-col min-h-0 h-full">
                    <div class="flex justify-between items-center mb-4 flex-shrink-0">
                        <h4 class="font-semibold text-lg truncate pr-2">{{ selectedCategoryName }}</h4>
                        <div class="flex items-center gap-2">
                             <button @click="openGenerateFunFactsModal(1)" :disabled="!selectedCategoryId" class="btn btn-secondary btn-sm"><IconSparkles class="w-4 h-4 mr-1"/> Generate 1</button>
                            <button @click="openFactModal()" :disabled="!selectedCategoryId" class="btn btn-secondary btn-sm"><IconPlus class="w-4 h-4 mr-1"/>New</button>
                        </div>
                    </div>
                    <div class="border rounded-lg overflow-hidden dark:border-gray-700 flex-grow min-h-0 bg-gray-50 dark:bg-gray-900/50">
                        <div v-if="isLoadingFunFacts" class="p-4 text-center text-gray-500">Loading...</div>
                        <div v-else-if="!selectedCategoryId" class="p-10 text-center text-gray-500 italic flex flex-col items-center justify-center h-full">
                            <IconInfo class="w-10 h-10 mb-2 opacity-50"/>
                            Select a category to view facts.
                        </div>
                        <ul v-else class="divide-y dark:divide-gray-700 overflow-y-auto h-full">
                            <li v-for="fact in filteredFacts" :key="fact.id" class="p-3 flex items-start gap-3 hover:bg-gray-100 dark:hover:bg-gray-800 group transition-colors">
                                <!-- Actions on LEFT -->
                                <div class="flex items-center gap-1 flex-shrink-0 mt-0.5">
                                    <button @click="openFactModal(fact)" class="p-1.5 rounded-full hover:bg-blue-200 dark:hover:bg-blue-800 text-gray-400 hover:text-blue-600 dark:text-gray-500 dark:hover:text-blue-300 transition-colors" title="Edit Fact">
                                        <IconPencil class="w-4 h-4"/>
                                    </button>
                                    <button @click="deleteFact(fact)" class="p-1.5 rounded-full hover:bg-red-200 dark:hover:bg-red-900 text-gray-400 hover:text-red-600 dark:text-gray-500 dark:hover:text-red-300 transition-colors" title="Delete Fact">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                </div>
                                <p class="text-sm flex-grow leading-relaxed border-l dark:border-gray-700 pl-3 ml-1">{{ fact.content }}</p>
                            </li>
                            <li v-if="filteredFacts.length === 0" class="p-8 text-center text-gray-400 text-sm italic">
                                No facts in this category yet.
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
        
        <GenerateFunFactsModal v-if="uiStore.activeModal === 'generateFunFacts'" />

    </div>
</template>

<style scoped>
.label { @apply block text-sm font-bold text-gray-700 dark:text-gray-300; }
.animate-fade-in { animation: fadeIn 0.4s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
</style>
