<!-- frontend/webui/src/components/settings/TTISettings.vue -->
<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

const { user } = storeToRefs(authStore);
const { availableTtiModels, availableTtiModelsGrouped } = storeToRefs(dataStore);

const form = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

// Dropdown state
const isTtiMenuOpen = ref(false);
const ttiTriggerRef = ref(null);
const ttiFloatingRef = ref(null);
const ttiModelSearchTerm = ref('');

const { floatingStyles: ttiFloatingStyles } = useFloating(ttiTriggerRef, ttiFloatingRef, {
  placement: 'bottom-start',
  whileElementsMounted: autoUpdate,
  middleware: [offset(5), flip(), shift({ padding: 5 })],
});

const vOnClickOutside = {
  mounted: (el, binding) => {
    el.clickOutsideEvent = event => {
      const triggerEl = ttiTriggerRef.value;
      if (!(el === event.target || el.contains(event.target) || triggerEl?.contains(event.target))) {
        binding.value();
      }
    };
    document.addEventListener('mousedown', el.clickOutsideEvent);
  },
  unmounted: el => {
    document.removeEventListener('mousedown', el.clickOutsideEvent);
  },
};

watch(isTtiMenuOpen, (isOpen) => {
    if (isOpen) {
        nextTick(() => {
            const menuElement = ttiFloatingRef.value;
            if (menuElement) {
                const selectedButton = menuElement.querySelector('.menu-item-button.selected');
                if (selectedButton) {
                    selectedButton.scrollIntoView({ block: 'nearest' });
                }
            }
        });
    }
});

const activeTtiModel = computed({
  get: () => user.value?.tti_binding_model_name,
  set: (name) => {
    authStore.updateUserPreferences({ tti_binding_model_name: name });
  }
});

const selectedModelDetails = computed(() => {
    if (!activeTtiModel.value || availableTtiModels.value.length === 0) return null;
    return availableTtiModels.value.find(m => m.id === activeTtiModel.value) || null;
});

const modelConfigurableParameters = computed(() => {
    if (!selectedModelDetails.value?.alias) return [];
    const metadataKeys = ['icon', 'title', 'description', 'allow_parameters_override'];
    return Object.entries(selectedModelDetails.value.alias)
        .filter(([key]) => !metadataKeys.includes(key))
        .map(([key, defaultValue]) => ({
            name: key,
            type: typeof defaultValue === 'boolean' ? 'bool' : (typeof defaultValue === 'number' ? 'float' : 'str'),
            default: defaultValue
        }));
});

const userOverrides = computed(() => {
    if (!user.value || !activeTtiModel.value || !user.value.tti_models_config) return {};
    return user.value.tti_models_config[activeTtiModel.value] || {};
});

const allowOverrides = computed(() => {
    if (!selectedModelDetails.value?.alias) return true;
    return selectedModelDetails.value.alias.allow_parameters_override !== false;
})

const filteredAvailableTtiModels = computed(() => {
    if (!ttiModelSearchTerm.value) return availableTtiModelsGrouped.value;
    const term = ttiModelSearchTerm.value.toLowerCase();
    const result = [];
    for (const group of availableTtiModelsGrouped.value) {
        if (group.items) {
            const filteredItems = group.items.filter(item => item.name.toLowerCase().includes(term));
            if (filteredItems.length > 0) {
                result.push({ ...group, items: filteredItems });
            }
        }
    }
    return result;
});

function selectTtiModel(id) {
    activeTtiModel.value = id;
    isTtiMenuOpen.value = false;
}

watch(selectedModelDetails, (newModel) => {
    if (newModel) {
        const newFormState = {};
        modelConfigurableParameters.value.forEach(param => {
            newFormState[param.name] = userOverrides.value[param.name] ?? newModel.alias[param.name] ?? param.default;
        });
        form.value = newFormState;
        pristineState = JSON.stringify(newFormState);
        hasChanges.value = false;
    } else {
        form.value = {};
        pristineState = '{}';
        hasChanges.value = false;
    }
}, { immediate: true, deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

async function handleSave() {
    if (!activeTtiModel.value) return;
    isLoading.value = true;
    try {
        const currentConfig = user.value.tti_models_config || {};
        const newConfigForModel = { ...(currentConfig[activeTtiModel.value] || {}), ...form.value };

        if (selectedModelDetails.value?.alias) {
            Object.keys(newConfigForModel).forEach(key => {
                if (newConfigForModel[key] === selectedModelDetails.value.alias[key] || newConfigForModel[key] === '' || newConfigForModel[key] === null) {
                    delete newConfigForModel[key];
                }
            });
        }
        
        const updatedUserConfigs = {
            ...currentConfig,
            [activeTtiModel.value]: newConfigForModel
        };
        
        if (Object.keys(updatedUserConfigs[activeTtiModel.value]).length === 0) {
            delete updatedUserConfigs[activeTtiModel.value];
        }

        await authStore.updateUserPreferences({ tti_models_config: updatedUserConfigs });
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    } finally {
        isLoading.value = false;
    }
}

function handleResetToDefaults() {
    const newFormState = {};
    if (selectedModelDetails.value?.alias) {
        modelConfigurableParameters.value.forEach(param => {
            newFormState[param.name] = selectedModelDetails.value.alias[param.name] ?? param.default;
        });
    }
    form.value = newFormState;
}

onMounted(() => {
    if (dataStore.availableTtiModels.length === 0) {
        dataStore.fetchAvailableTtiModels();
    }
});
</script>

<template>
    <div class="space-y-8">
        <div>
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                Image Generation (TTI) Parameters
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Configure default parameters for your selected Text-to-Image model. These settings can be overridden by model aliases set by an administrator if overrides are disabled.
            </p>
        </div>

        <div class="space-y-6">
            <div>
                <label class="block text-base font-medium mb-2">Active Image Generation Model</label>
                <div class="relative">
                    <button ref="ttiTriggerRef" @click="isTtiMenuOpen = !isTtiMenuOpen" type="button" class="toolbox-select truncate w-full flex items-center justify-between">
                        <div class="flex items-center space-x-3 truncate">
                            <img v-if="selectedModelDetails?.icon_base64" :src="selectedModelDetails.icon_base64" class="h-8 w-8 rounded-md object-cover"/>
                            <span v-else class="w-8 h-8 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md"><IconPhoto class="w-5 h-5" /></span>
                            <div class="min-w-0 text-left">
                                <span class="block font-semibold truncate">{{ selectedModelDetails?.name || 'Select an Image Model' }}</span>
                            </div>
                        </div>
                        <svg class="w-4 h-4 text-gray-400 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                    </button>
                    <Teleport to="body">
                        <Transition enter-active-class="transition ease-out duration-100" enter-from-class="transform opacity-0 scale-95" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-75" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-95">
                            <div v-if="isTtiMenuOpen" ref="ttiFloatingRef" :style="ttiFloatingStyles" v-on-click-outside="() => isTtiMenuOpen = false" class="z-50 w-80 origin-top-left rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none py-1 flex flex-col max-h-[50vh]">
                                <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                    <input type="text" v-model="ttiModelSearchTerm" @click.stop placeholder="Search TTI models..." class="input-field-sm w-full">
                                </div>
                                <div class="p-1 flex-grow overflow-y-auto">
                                    <div v-if="dataStore.isLoadingTtiModels" class="text-center p-4 text-sm text-gray-500">Loading TTI models...</div>
                                    <div v-else-if="filteredAvailableTtiModels.length === 0" class="text-center p-4 text-sm text-gray-500">No TTI models found.</div>
                                    <div v-for="group in filteredAvailableTtiModels" :key="group.label">
                                        <h4 class="px-2 py-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">{{ group.label }}</h4>
                                        <button v-for="item in group.items" :key="item.id" @click="selectTtiModel(item.id)" class="menu-item-button" :class="{'selected': activeTtiModel === item.id}">
                                            <div class="flex items-center space-x-3 truncate">
                                                <img v-if="item.icon_base64" :src="item.icon_base64" class="h-6 w-6 rounded-md object-cover flex-shrink-0" />
                                                <IconPhoto v-else class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                                <div class="truncate text-left"><p class="font-medium truncate text-sm">{{ item.name }}</p></div>
                                            </div>
                                            <IconCheckCircle v-if="activeTtiModel === item.id" class="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </Transition>
                    </Teleport>
                </div>
            </div>

            <div v-if="activeTtiModel && selectedModelDetails && allowOverrides" class="p-4 border rounded-lg dark:border-gray-700 space-y-4">
                <h4 class="font-medium">Configuration for: <span class="font-mono text-blue-600 dark:text-blue-400">{{ selectedModelDetails.name }}</span></h4>
                <div v-if="modelConfigurableParameters.length === 0" class="text-sm text-gray-500">
                    This model has no parameters exposed for user configuration.
                </div>
                <form v-else @submit.prevent="handleSave" class="space-y-4">
                    <div v-for="param in modelConfigurableParameters" :key="param.name">
                        <label :for="`tti-param-${param.name}`" class="block text-sm font-medium capitalize">{{ param.name.replace(/_/g, ' ') }}</label>
                        <input 
                            v-if="['str', 'int', 'float'].includes(param.type)"
                            :type="param.type === 'str' ? 'text' : 'number'"
                            :step="param.type === 'float' ? '0.01' : '1'"
                            :id="`tti-param-${param.name}`"
                            v-model="form[param.name]"
                            class="input-field mt-1"
                            :placeholder="`Default: ${selectedModelDetails.alias[param.name]}`"
                        />
                         <div v-else-if="param.type === 'bool'" class="mt-1">
                            <button @click="form[param.name] = !form[param.name]" type="button" :class="[form[param.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form[param.name] ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                            </button>
                        </div>
                    </div>
                     <div class="flex justify-end gap-3 pt-4 border-t dark:border-gray-600">
                        <button type="button" @click="handleResetToDefaults" class="btn btn-secondary" :disabled="isLoading">Reset to Defaults</button>
                        <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">{{ isLoading ? 'Saving...' : 'Save Changes' }}</button>
                    </div>
                </form>
            </div>
            <div v-else-if="activeTtiModel && selectedModelDetails && !allowOverrides" class="p-4 border border-yellow-300 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-sm text-yellow-800 dark:text-yellow-200 flex items-center gap-3">
                <IconInfo class="w-5 h-5 flex-shrink-0" />
                <span>An administrator has locked the parameters for this model alias. Your personal settings will be ignored.</span>
            </div>
        </div>
    </div>
</template>

<style scoped>
.toolbox-select {
    @apply w-full text-left text-sm px-2.5 py-1.5 bg-gray-50 dark:bg-gray-700/50 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500;
}
.menu-item-button { @apply w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between gap-2; }
.menu-item-button.selected { @apply bg-blue-100 dark:bg-blue-900/50 font-semibold; }
</style>