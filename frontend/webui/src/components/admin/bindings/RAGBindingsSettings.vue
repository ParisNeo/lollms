<script setup>
import { ref, onMounted, computed, watch, defineAsyncComponent } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import { parsedMarkdown as parseMarkdown } from '../../../services/markdownParser';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconDatabase from '../../../assets/icons/IconDatabase.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';

const BindingModelsManager = defineAsyncComponent(() => import('./BindingModelsManager.vue'));

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { ragBindings, availableRagBindingTypes, isLoadingRagBindings, globalSettings } = storeToRefs(adminStore);

const isFormVisible = ref(false);
const editingBinding = ref(null);
const isLoadingForm = ref(false);
const isKeyVisible = ref({});
const activeTab = ref('settings');

const getInitialFormState = () => ({
    id: null,
    alias: '',
    name: '',
    config: {},
    default_model_name: null,
    is_active: true
});

const form = ref(getInitialFormState());
const isEditMode = computed(() => editingBinding.value !== null);

const selectedBindingType = computed(() => {
    if (!form.value.name || !Array.isArray(availableRagBindingTypes.value)) return null;
    return availableRagBindingTypes.value.find(b => b.name === form.value.name);
});

const allFormParameters = computed(() => {
    if (!selectedBindingType.value) return [];

    const paramsFromDesc = selectedBindingType.value.input_parameters || [];
    const paramNamesFromDesc = new Set(paramsFromDesc.map(p => p.name));

    // Model Params to exclude
    const modelParams = selectedBindingType.value.model_parameters || [];
    const modelParamNames = new Set(modelParams.map(p => p.name));

    const paramsFromConfig = Object.keys(form.value.config || {})
        .filter(key => 
            !paramNamesFromDesc.has(key) && 
            !modelParamNames.has(key) && 
            key !== 'model_name' &&
            key !== 'model' &&
            key !== 'class'
        )
        .map(key => ({
            name: key,
            type: typeof form.value.config[key] === 'boolean' ? 'bool' : (typeof form.value.config[key] === 'number' ? 'float' : 'str'),
            description: `(Parameter not in binding description)`,
            mandatory: false,
        }));

    const filteredGlobals = paramsFromDesc.filter(p => !modelParamNames.has(p.name) && p.name !== 'model_name');

    return [
        ...filteredGlobals, 
        ...paramsFromConfig
    ];
});

const ragModelDisplayMode = computed({
  get() {
    if (!Array.isArray(globalSettings.value)) return 'mixed';
    const setting = globalSettings.value.find(s => s.key === 'rag_model_display_mode');
    return setting ? setting.value : 'mixed';
  },
  set(newValue) {
    adminStore.updateGlobalSettings({ 'rag_model_display_mode': newValue });
  }
});

watch(() => form.value.name, (newName, oldName) => {
    if (newName !== oldName && !isEditMode.value) {
        if (!Array.isArray(availableRagBindingTypes.value)) return;
        const bindingDesc = availableRagBindingTypes.value.find(b => b.name === newName);
        const newConfig = {};
        if (bindingDesc && bindingDesc.input_parameters) {
            bindingDesc.input_parameters.forEach(param => {
                newConfig[param.name] = param.default !== undefined ? param.default : '';
            });
        }
        form.value.config = newConfig;
    }
});

onMounted(() => {
    adminStore.fetchRagBindings();
    adminStore.fetchAvailableRagBindingTypes();
    adminStore.fetchGlobalSettings();
});

function showAddForm() {
    editingBinding.value = null;
    form.value = getInitialFormState();
    isKeyVisible.value = {};
    activeTab.value = 'settings';
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showEditForm(binding) {
    editingBinding.value = binding;
    form.value = JSON.parse(JSON.stringify(binding));
    if (!form.value.config) form.value.config = {};
    isKeyVisible.value = {};
    activeTab.value = 'settings';
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function hideForm() {
    isFormVisible.value = false;
    editingBinding.value = null;
}

async function handleSubmit() {
    if (!form.value.alias.trim() || !form.value.name) {
        uiStore.addNotification('Alias and Vectorizer Type are required.', 'warning');
        return;
    }
    isLoadingForm.value = true;
    try {
        const payload = {
            alias: form.value.alias,
            name: form.value.name,
            config: form.value.config || {},
            is_active: form.value.is_active,
            default_model_name: form.value.default_model_name || null,
        };
        if (isEditMode.value) {
            await adminStore.updateRagBinding(editingBinding.value.id, payload);
        } else {
            await adminStore.addRagBinding(payload);
        }
        hideForm();
    } finally {
        isLoadingForm.value = false;
    }
}

async function handleDelete(binding) {
    const confirmed = await uiStore.showConfirmation({ title: `Delete RAG Binding '${binding.alias}'?`, confirmText: 'Delete' });
    if (confirmed) {
        await adminStore.deleteRagBinding(binding.id);
    }
}

async function toggleBindingActive(binding) {
    await adminStore.updateRagBinding(binding.id, { is_active: !binding.is_active });
}

function getBindingTitle(name) {
    if (!Array.isArray(availableRagBindingTypes.value)) return name;
    const bindingType = availableRagBindingTypes.value.find(b => b.name === name);
    return bindingType ? bindingType.title : name;
}
</script>

<template>
    <div class="space-y-8">
        <!-- EDIT / ADD FORM VIEW WITH INTEGRATED TABS -->
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-2xl p-6 border border-gray-100 dark:border-gray-700">
            <div class="flex justify-between items-center mb-6 pb-3 border-b dark:border-gray-700">
                <div>
                    <span class="text-[9px] font-black uppercase text-blue-500 tracking-widest">{{ isEditMode ? 'RAG Engine Configuration' : 'New RAG Connection' }}</span>
                    <h3 class="text-xl font-bold text-gray-900 dark:text-white">{{ isEditMode ? form.alias : 'Add New RAG Binding' }}</h3>
                </div>
                <div v-if="isEditMode" class="flex gap-2 text-xs font-bold p-1 bg-gray-100 dark:bg-gray-700/50 rounded-xl">
                    <button @click="activeTab = 'settings'" :class="{'bg-white dark:bg-gray-600 text-blue-600 shadow-sm': activeTab === 'settings', 'text-gray-500': activeTab !== 'settings'}" class="px-3 py-1.5 rounded-lg transition-all">Connection Settings</button>
                    <button @click="activeTab = 'models'" :class="{'bg-white dark:bg-gray-600 text-blue-600 shadow-sm': activeTab === 'models', 'text-gray-500': activeTab !== 'models'}" class="px-3 py-1.5 rounded-lg transition-all">Vectorizer Profiles</button>
                </div>
            </div>

            <!-- Settings Tab -->
            <div v-if="activeTab === 'settings'">
                <form @submit.prevent="handleSubmit" class="space-y-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label for="alias" class="block text-xs font-bold uppercase text-gray-500 mb-1">Alias <span class="text-red-500">*</span></label>
                            <input type="text" id="alias" v-model="form.alias" class="input-field text-xs" required placeholder="e.g., local_embeddings">
                        </div>
                        <div>
                            <label for="name" class="block text-xs font-bold uppercase text-gray-500 mb-1">Vectorizer Type <span class="text-red-500">*</span></label>
                            <select id="name" v-model="form.name" class="input-field text-xs" required :disabled="isEditMode">
                                <option disabled value="">Select a type</option>
                                <option v-for="type in availableRagBindingTypes" :key="type.name" :value="type.name">{{ type.title }}</option>
                            </select>
                        </div>
                    </div>

                    <div v-if="selectedBindingType" class="space-y-6 border-t dark:border-gray-700 pt-6">
                        <div class="text-sm text-gray-600 dark:text-gray-400 prose dark:prose-invert max-w-none" v-html="parseMarkdown(selectedBindingType.description || '')"></div>
                        <div v-for="param in allFormParameters" :key="param.name" class="space-y-1">
                            <label :for="`param-${param.name}`" class="block text-xs font-bold uppercase text-gray-500">
                                {{ param.name.replace(/_/g, ' ') }} <span v-if="param.mandatory" class="text-red-500">*</span>
                            </label>
                            <div class="relative">
                                <input :type="(param.name.includes('key') || param.name.includes('token')) && !isKeyVisible[param.name] ? 'password' : 'text'"
                                       :id="`param-${param.name}`" v-model="form.config[param.name]" class="input-field text-xs" :required="param.mandatory" :placeholder="param.default">
                                 <button v-if="param.name.includes('key') || param.name.includes('token')" type="button" @click="isKeyVisible[param.name] = !isKeyVisible[param.name]" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-500">
                                    <IconEyeOff v-if="isKeyVisible[param.name]" class="w-4 h-4" /><IconEye v-else class="w-4 h-4" />
                                </button>
                            </div>
                            <p class="text-[10px] text-gray-500 mt-1">{{ param.description }}</p>
                        </div>
                    </div>

                    <div class="flex items-center justify-between p-3.5 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-700">
                        <div class="flex flex-col">
                            <span class="text-xs font-bold text-gray-800 dark:text-gray-200">Active Status</span>
                            <span class="text-[10px] text-gray-500">Enable this binding for indexing and querying knowledge stores.</span>
                        </div>
                        <button @click="form.is_active = !form.is_active" type="button" :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                            <span :class="[form.is_active ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>

                    <div class="flex justify-end gap-3 pt-2">
                        <button type="button" @click="hideForm" class="btn btn-secondary text-xs">Cancel</button>
                        <button type="submit" class="btn btn-primary text-xs" :disabled="isLoadingForm">
                            <IconAnimateSpin v-if="isLoadingForm" class="w-4 h-4 mr-1.5 animate-spin" />
                            <span>{{ isEditMode ? 'Save Changes' : 'Create Binding' }}</span>
                        </button>
                    </div>
                </form>
            </div>

            <!-- Profiles Tab -->
            <div v-else-if="activeTab === 'models'">
                <BindingModelsManager :binding="editingBinding" binding-type="rag" />
                <div class="flex justify-end gap-3 mt-4">
                    <button type="button" @click="hideForm" class="btn btn-secondary text-xs">Close</button>
                </div>
            </div>
        </div>

        <!-- MAIN BINDINGS LIST VIEW -->
        <div v-else class="space-y-6">
            <div class="flex justify-between items-center flex-wrap gap-4 bg-white/60 dark:bg-gray-850/50 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-700/60 backdrop-blur-md">
                <div>
                    <h2 class="text-xl font-black tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
                        <IconDatabase class="w-6 h-6 text-blue-500" />
                        <span>RAG Embedding Bindings</span>
                        <span class="text-xs font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300">
                            {{ ragBindings.length }} Vectorizers
                        </span>
                    </h2>
                    <p class="text-xs text-gray-500 mt-0.5">Manage embedding vectorizers and semantic similarity engines for your knowledge base.</p>
                </div>

                <div class="flex items-center gap-3">
                    <div class="flex items-center gap-2">
                        <label for="rag-model-display-mode" class="text-xs font-bold uppercase text-gray-500">Display Mode:</label>
                        <select id="rag-model-display-mode" v-model="ragModelDisplayMode" class="input-field text-xs !py-1 !px-2 bg-white dark:bg-gray-800">
                            <option value="mixed">Mixed (Alias or Original)</option>
                            <option value="aliased">Aliased Only</option>
                            <option value="original">Original Names Only</option>
                        </select>
                    </div>

                    <button @click="handleHealProfiles" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Heal orphaned user preferences">
                        <IconSparkles class="w-3.5 h-3.5 text-purple-500" />
                        <span>Sync & Heal</span>
                    </button>

                    <button @click="openPolicyModal" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Force models or set system defaults for users">
                        <IconCpuChip class="w-3.5 h-3.5 text-blue-500" />
                        <span>⚡ Policy & Defaults</span>
                    </button>

                    <button @click="showAddForm" class="btn btn-primary btn-sm flex items-center gap-1.5 shadow-sm">+ Add RAG Binding</button>
                </div>
            </div>

            <div v-if="isLoadingRagBindings" class="text-center py-12 text-xs font-bold text-gray-400">Loading RAG bindings...</div>
            <div v-else-if="ragBindings.length === 0" class="text-center py-16 bg-gray-50 dark:bg-gray-800/40 rounded-2xl border border-dashed dark:border-gray-700">
                <IconDatabase class="w-12 h-12 text-gray-400 mx-auto mb-2 opacity-40" />
                <p class="text-sm font-bold text-gray-700 dark:text-gray-300">No RAG Bindings Configured</p>
                <button @click="showAddForm" class="btn btn-primary btn-sm mt-3">+ Add First RAG Vectorizer</button>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                <div v-for="binding in ragBindings" :key="binding.id" @click="showEditForm(binding)" 
                     class="bg-white dark:bg-gray-800/90 p-5 rounded-2xl shadow-xs hover:shadow-lg transition-all cursor-pointer flex flex-col justify-between border border-gray-200/80 dark:border-gray-700/80 hover:border-blue-500 group relative">
                    <div>
                        <div class="flex items-start justify-between gap-3 mb-3">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 font-black shrink-0">
                                    <IconDatabase class="w-5 h-5" />
                                </div>
                                <div class="min-w-0">
                                    <h4 class="font-bold text-sm text-gray-900 dark:text-white truncate">{{ binding.alias }}</h4>
                                    <p class="text-[10px] text-gray-500 font-mono capitalize">{{ getBindingTitle(binding.name) }}</p>
                                </div>
                            </div>

                            <button @click.stop="toggleBindingActive(binding)" type="button" :class="[binding.is_active ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                <span :class="[binding.is_active ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>

                        <!-- Stats & Info -->
                        <div class="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700/60 text-xs space-y-1.5 font-mono">
                            <div class="flex justify-between items-center text-[10px]">
                                <span class="text-gray-400">Profiles:</span>
                                <span class="font-bold text-blue-500">{{ Object.keys(binding.model_aliases || {}).length }} Configured Profiles</span>
                            </div>
                            <div v-if="binding.default_model_name" class="flex justify-between items-center text-[10px] truncate">
                                <span class="text-gray-400">Default:</span>
                                <span class="font-bold text-gray-700 dark:text-gray-300 truncate max-w-[140px]">{{ binding.default_model_name }}</span>
                            </div>
                        </div>
                    </div>

                    <div class="border-t dark:border-gray-700/60 pt-3 mt-4 flex justify-between items-center text-xs">
                        <span class="text-blue-500 font-bold text-[10px] uppercase tracking-wider group-hover:underline">Configure Vectorizers &rarr;</span>
                        <button @click.stop="handleDelete(binding)" class="text-rose-500 hover:text-rose-700 font-bold text-[10px] uppercase">Delete</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>
