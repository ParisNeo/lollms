<!-- [CREATE] frontend/webui/src/components/settings/STTSettings.vue -->
<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

const { user } = storeToRefs(authStore);
const { availableSttModels, availableSttModelsGrouped } = storeToRefs(dataStore);

const form = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

// Dropdown state
const isSttMenuOpen = ref(false);
const sttTriggerRef = ref(null);
const sttFloatingRef = ref(null);
const sttModelSearchTerm = ref('');

const { floatingStyles: sttFloatingStyles } = useFloating(sttTriggerRef, sttFloatingRef, {
  placement: 'bottom-start',
  whileElementsMounted: autoUpdate,
  middleware: [offset(5), flip(), shift({ padding: 5 })],
});

const vOnClickOutside = {
  mounted: (el, binding) => {
    el.clickOutsideEvent = event => {
      const triggerEl = sttTriggerRef.value;
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

watch(isSttMenuOpen, (isOpen) => {
    if (isOpen) {
        nextTick(() => {
            const menuElement = sttFloatingRef.value;
            if (menuElement) {
                const selectedButton = menuElement.querySelector('.menu-item-button.selected');
                if (selectedButton) {
                    selectedButton.scrollIntoView({ block: 'nearest' });
                }
            }
        });
    }
});

const activeSttModel = computed({
  get: () => form.value.stt_binding_model_name,
  set: (name) => {
    form.value.stt_binding_model_name = name;
  }
});

const selectedModelDetails = computed(() => {
    if (!activeSttModel.value || availableSttModels.value.length === 0) return null;
    return availableSttModels.value.find(m => m.id === activeSttModel.value) || null;
});

const modelConfigurableParameters = computed(() => {
    if (!selectedModelDetails.value?.binding_params) {
        return [];
    }
    const allParams = [
        ...(selectedModelDetails.value.binding_params.class_parameters || []),
        ...(selectedModelDetails.value.binding_params.generation_parameters || [])
    ];
    const excludedParams = ['model'];
    const uniqueParams = allParams.reduce((acc, param) => {
        if (!acc.has(param.name) && !excludedParams.includes(param.name)) {
            acc.set(param.name, param);
        }
        return acc;
    }, new Map());
    return Array.from(uniqueParams.values());
});

const userOverrides = computed(() => {
    if (!user.value || !activeSttModel.value || !user.value.stt_models_config) return {};
    return user.value.stt_models_config[activeSttModel.value] || {};
});

const allowOverrides = computed(() => {
    if (!selectedModelDetails.value?.alias) return true;
    return selectedModelDetails.value.alias.allow_parameters_override !== false;
})

const filteredAvailableSttModels = computed(() => {
    if (!sttModelSearchTerm.value) return availableSttModelsGrouped.value;
    const term = sttModelSearchTerm.value.toLowerCase();
    const result = [];
    for (const group of availableSttModelsGrouped.value) {
        if (group.items) {
            const filteredItems = group.items.filter(item => item.name.toLowerCase().includes(term));
            if (filteredItems.length > 0) {
                result.push({ ...group, items: filteredItems });
            }
        }
    }
    return result;
});

function selectSttModel(id) {
    activeSttModel.value = id;
    isSttMenuOpen.value = false;
}

const populateForm = () => {
    if (user.value) {
        const newFormState = {};
        if (selectedModelDetails.value) {
            modelConfigurableParameters.value.forEach(param => {
                newFormState[param.name] = userOverrides.value[param.name] ?? param.default;
            });
        }
        form.value = {
            ...newFormState,
            stt_binding_model_name: user.value.stt_binding_model_name,
        };
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    }
};

watch(selectedModelDetails, populateForm, { immediate: true, deep: true });
watch(user, populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== JSON.stringify(pristineState);
}, { deep: true });

async function handleSave() {
    isLoading.value = true;
    try {
        const payload = {
            stt_binding_model_name: form.value.stt_binding_model_name,
        };

        const currentConfig = user.value.stt_models_config || {};
        const newConfigForModel = {};
        modelConfigurableParameters.value.forEach(param => {
            if (form.value[param.name] !== param.default) {
                newConfigForModel[param.name] = form.value[param.name];
            }
        });
        
        const updatedUserConfigs = {
            ...currentConfig,
            [activeSttModel.value]: newConfigForModel
        };
        
        if (Object.keys(updatedUserConfigs[activeSttModel.value] || {}).length === 0) {
            delete updatedUserConfigs[activeSttModel.value];
        }

        payload.stt_models_config = updatedUserConfigs;

        await authStore.updateUserPreferences(payload);
    } finally {
        isLoading.value = false;
    }
}

function handleResetToDefaults() {
    const newFormState = {};
    if (selectedModelDetails.value) {
        modelConfigurableParameters.value.forEach(param => {
            newFormState[param.name] = param.default;
        });
        form.value = { ...form.value, ...newFormState };
    }
}

onMounted(() => {
    if (dataStore.availableSttModels.length === 0) {
        dataStore.fetchAvailableSttModels();
    }
});
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="px-4 py-5 sm:p-6">
            <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Speech-to-Text (STT) Parameters</h2>
            <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                Configure default parameters for your selected Speech-to-Text model.
            </p>
        </div>
        <div class="border-t border-gray-200 dark:border-gray-700">
            <form @submit.prevent="handleSave" class="p-4 sm:p-6 space-y-6">
                <div>
                    <label class="block text-base font-medium mb-2">Active Speech-to-Text Model</label>
                    <div class="relative">
                        <button ref="sttTriggerRef" @click="isSttMenuOpen = !isSttMenuOpen" type="button" class="toolbox-select truncate w-full flex items-center justify-between">
                            <div class="flex items-center space-x-3 truncate">
                                <img v-if="selectedModelDetails?.alias?.icon" :src="selectedModelDetails.alias.icon" class="h-8 w-8 rounded-md object-cover"/>
                                <span v-else class="w-8 h-8 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md"><IconMicrophone class="w-5 h-5" /></span>
                                <div class="min-w-0 text-left">
                                    <span class="block font-semibold truncate">{{ selectedModelDetails?.name || 'Select a Speech Model' }}</span>
                                </div>
                            </div>
                            <svg class="w-4 h-4 text-gray-400 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                        </button>
                        <Teleport to="body">
                            <Transition enter-active-class="transition ease-out duration-100" enter-from-class="transform opacity-0 scale-95" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-75" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-95">
                                <div v-if="isSttMenuOpen" ref="sttFloatingRef" :style="sttFloatingStyles" v-on-click-outside="() => isSttMenuOpen = false" class="z-50 w-80 origin-top-left rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none py-1 flex flex-col max-h-[50vh]">
                                    <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                        <input type="text" v-model="sttModelSearchTerm" @click.stop placeholder="Search STT models..." class="input-field-sm w-full">
                                    </div>
                                    <div class="p-1 flex-grow overflow-y-auto">
                                        <div v-if="dataStore.isLoadingSttModels" class="text-center p-4 text-sm text-gray-500">Loading STT models...</div>
                                        <div v-else-if="filteredAvailableSttModels.length === 0" class="text-center p-4 text-sm text-gray-500">No STT models found.</div>
                                        <div v-for="group in filteredAvailableSttModels" :key="group.label">
                                            <h4 class="px-2 py-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">{{ group.label }}</h4>
                                            <button v-for="item in group.items" :key="item.id" @click="selectSttModel(item.id)" class="menu-item-button" :class="{'selected': activeSttModel === item.id}">
                                                <div class="flex items-center space-x-3 truncate">
                                                    <img v-if="item.alias?.icon" :src="item.alias.icon" class="h-6 w-6 rounded-md object-cover flex-shrink-0" />
                                                    <IconMicrophone v-else class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                                    <div class="truncate text-left"><p class="font-medium truncate text-sm">{{ item.name }}</p></div>
                                                </div>
                                                <IconCheckCircle v-if="activeSttModel === item.id" class="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </Transition>
                        </Teleport>
                    </div>
                </div>

                <div v-if="activeSttModel && selectedModelDetails && allowOverrides && modelConfigurableParameters.length > 0" class="p-4 border rounded-lg dark:border-gray-700 space-y-4">
                    <h4 class="font-medium">Configuration for: <span class="font-mono text-blue-600 dark:text-blue-400">{{ selectedModelDetails.name }}</span></h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div v-for="param in modelConfigurableParameters" :key="param.name">
                            <label :for="`stt-param-${param.name}`" class="block text-sm font-medium capitalize">{{ param.name.replace(/_/g, ' ') }}</label>
                            <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">{{param.description}}</p>
                            <select v-if="param.options && param.options.length > 0" :id="`stt-param-${param.name}`" v-model="form[param.name]" class="input-field mt-1">
                                <option v-for="option in param.options" :key="option" :value="option">{{ option }}</option>
                            </select>
                            <input 
                                v-else-if="['str', 'int', 'float'].includes(param.type)"
                                :type="param.type === 'str' ? 'text' : 'number'"
                                :step="param.type === 'float' ? '0.01' : '1'"
                                :id="`stt-param-${param.name}`"
                                v-model="form[param.name]"
                                class="input-field mt-1"
                                :placeholder="`Default: ${param.default}`"
                            />
                             <div v-else-if="param.type === 'bool'" class="mt-1">
                                <button @click="form[param.name] = !form[param.name]" type="button" :class="[form[param.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                    <span :class="[form[param.name] ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                        </div>
                    </div>
                     <div class="flex justify-end gap-3 pt-4 border-t dark:border-gray-600">
                        <button type="button" @click="handleResetToDefaults" class="btn btn-secondary" :disabled="isLoading">Reset to Defaults</button>
                    </div>
                </div>
                <div v-else-if="activeSttModel && selectedModelDetails && !allowOverrides" class="p-4 border border-yellow-300 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-sm text-yellow-800 dark:text-yellow-200 flex items-center gap-3">
                    <IconInfo class="w-5 h-5 flex-shrink-0" />
                    <span>An administrator has locked the parameters for this model alias. Your personal settings will be ignored.</span>
                </div>
                 <div class="flex justify-end pt-4 border-t dark:border-gray-600">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">{{ isLoading ? 'Saving...' : 'Save STT Settings' }}</button>
                </div>
            </form>
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