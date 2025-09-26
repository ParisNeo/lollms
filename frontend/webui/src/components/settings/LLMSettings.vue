<!-- frontend/webui/src/components/settings/LLMSettings.vue -->
<script setup>
import { ref, onMounted, watch, computed, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();
const { user } = storeToRefs(authStore);
const { availableLLMModelsGrouped, isLoadingLollmsModels, availableLollmsModels } = storeToRefs(dataStore);

const form = ref({
    lollms_model_name: '',
    llm_ctx_size: 4096,
    llm_temperature: 0.7,
    llm_top_k: 50,
    llm_top_p: 0.95,
    llm_repeat_penalty: 1.1,
    llm_repeat_last_n: 64,
    put_thoughts_in_context: false
});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = {};

// Dropdown state
const isLlmMenuOpen = ref(false);
const llmTriggerRef = ref(null);
const llmFloatingRef = ref(null);
const modelSearchTerm = ref('');

const { floatingStyles: llmFloatingStyles } = useFloating(llmTriggerRef, llmFloatingRef, {
  placement: 'bottom-start',
  whileElementsMounted: autoUpdate,
  middleware: [offset(5), flip(), shift({ padding: 5 })],
});

const vOnClickOutside = {
  mounted: (el, binding) => {
    el.clickOutsideEvent = event => {
      const triggerEl = llmTriggerRef.value;
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

watch(isLlmMenuOpen, (isOpen) => {
    if (isOpen) {
        nextTick(() => {
            const menuElement = llmFloatingRef.value;
            if (menuElement) {
                const selectedButton = menuElement.querySelector('.menu-item-button.selected');
                if (selectedButton) {
                    selectedButton.scrollIntoView({ block: 'nearest' });
                }
            }
        });
    }
});

const areSettingsForced = computed(() => user.value?.llm_settings_overridden ?? false);

const selectedModelDetails = computed(() => {
    if (!form.value.lollms_model_name || !availableLollmsModels.value) return null;
    return availableLollmsModels.value.find(m => m.id === form.value.lollms_model_name);
});

const isContextSizeLocked = computed(() => {
    return selectedModelDetails.value?.alias?.ctx_size_locked === true;
});

const activeModelName = computed({
    get: () => form.value.lollms_model_name,
    set: (name) => {
        if (!areSettingsForced.value) {
            form.value.lollms_model_name = name;
        }
    }
});

const selectedModel = computed(() => {
    if (!activeModelName.value) return null;
    for (const group of availableLLMModelsGrouped.value) {
        const model = group.items.find(item => item.id === activeModelName.value);
        if (model) return model;
    }
    return null;
});

const filteredAvailableLLMModels = computed(() => {
    if (!modelSearchTerm.value) return availableLLMModelsGrouped.value;
    const term = modelSearchTerm.value.toLowerCase();
    const result = [];
    for (const group of availableLLMModelsGrouped.value) {
        const filteredItems = group.items.filter(item => item.name.toLowerCase().includes(term));
        if (filteredItems.length > 0) {
            result.push({ ...group, items: filteredItems });
        }
    }
    return result;
});

function selectModel(id) {
    activeModelName.value = id;
    isLlmMenuOpen.value = false;
}

const populateForm = () => {
    if (user.value) {
        form.value = {
            lollms_model_name: user.value.lollms_model_name || '',
            llm_ctx_size: user.value.llm_ctx_size ?? null,
            llm_temperature: user.value.llm_temperature ?? null,
            llm_top_k: user.value.llm_top_k ?? null,
            llm_top_p: user.value.llm_top_p ?? null,
            llm_repeat_penalty: user.value.llm_repeat_penalty ?? null,
            llm_repeat_last_n: user.value.llm_repeat_last_n ?? null,
            put_thoughts_in_context: user.value.put_thoughts_in_context || false
        };
        pristineState = JSON.parse(JSON.stringify(form.value));
        hasChanges.value = false;
    }
};

onMounted(() => {
    if (dataStore.availableLollmsModels.length === 0) {
        dataStore.fetchAvailableLollmsModels();
    }
    populateForm();
});

watch(user, populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== JSON.stringify(pristineState);
}, { deep: true });

async function handleSave() {
    isLoading.value = true;
    try {
        await authStore.updateUserPreferences(form.value);
    } catch (error) {
        // Handled by API interceptor
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="px-4 py-5 sm:p-6">
            <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">LLM Configuration</h2>
            <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                Select your default text generation model and adjust its parameters.
            </p>
        </div>
        <div class="border-t border-gray-200 dark:border-gray-700">
            <form @submit.prevent="handleSave" class="p-4 sm:p-6 space-y-6">
                <!-- Model Selection Dropdown -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Default LLM Model</label>
                    <div class="relative mt-1">
                        <button ref="llmTriggerRef" @click="isLlmMenuOpen = !isLlmMenuOpen" type="button" class="toolbox-select truncate w-full flex items-center justify-between">
                            <div class="flex items-center space-x-3 truncate">
                                <img v-if="selectedModel?.icon_base64" :src="selectedModel.icon_base64" class="h-8 w-8 rounded-md object-cover"/>
                                <span v-else class="w-8 h-8 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md"><IconCpuChip class="w-5 h-5" /></span>
                                <div class="min-w-0 text-left">
                                    <span class="block font-semibold truncate">{{ selectedModel?.name || 'Select a Model' }}</span>
                                </div>
                            </div>
                            <svg class="w-4 h-4 text-gray-400 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                        </button>
                        <Teleport to="body">
                            <Transition enter-active-class="transition ease-out duration-100" enter-from-class="transform opacity-0 scale-95" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-75" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-95">
                                <div v-if="isLlmMenuOpen" ref="llmFloatingRef" :style="llmFloatingStyles" v-on-click-outside="() => isLlmMenuOpen = false" class="z-50 w-80 origin-top-left rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none py-1 flex flex-col max-h-[50vh]">
                                    <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                        <input type="text" v-model="modelSearchTerm" @click.stop placeholder="Search models..." class="input-field-sm w-full">
                                    </div>
                                    <div class="p-1 flex-grow overflow-y-auto">
                                        <div v-if="isLoadingLollmsModels" class="text-center p-4 text-sm text-gray-500">Loading models...</div>
                                        <div v-for="group in filteredAvailableLLMModels" :key="group.label">
                                            <h4 class="px-2 py-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">{{ group.label }}</h4>
                                            <button v-for="item in group.items" :key="item.id" @click="selectModel(item.id)" class="menu-item-button" :class="{'selected': activeModelName === item.id}">
                                                <div class="flex items-center space-x-3 truncate">
                                                    <img v-if="item.icon_base64" :src="item.icon_base64" class="h-6 w-6 rounded-md object-cover flex-shrink-0" />
                                                    <IconCpuChip v-else class="w-6 h-6 p-0.5 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                                                    <div class="truncate text-left"><p class="font-medium truncate text-sm">{{ item.name }}</p></div>
                                                </div>
                                                <div class="flex items-center gap-2 flex-shrink-0">
                                                    <IconCheckCircle v-if="activeModelName === item.id" class="w-5 h-5 text-blue-600 dark:text-blue-400" />
                                                    <IconEye v-if="item.alias?.has_vision" class="w-5 h-5 text-green-500" title="Vision active" />
                                                </div>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </Transition>
                        </Teleport>
                    </div>
                </div>
                
                 <div v-if="areSettingsForced" class="p-4 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 text-blue-800 dark:text-blue-200">
                    <p class="font-semibold">Settings Overridden by Admin</p>
                    <p class="text-sm">An administrator has set and locked the generation parameters for this model. Your personal settings will not apply.</p>
                </div>

                <!-- Generation Parameters -->
                <fieldset class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" :class="{'opacity-60': areSettingsForced}">
                    <div>
                        <label for="contextSize" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Context Size (tokens)</label>
                        <input type="number" id="contextSize" v-model.number="form.llm_ctx_size" class="input-field mt-1" placeholder="e.g., 4096" :disabled="areSettingsForced || isContextSizeLocked">
                        <p v-if="isContextSizeLocked" class="mt-1 text-xs text-red-600 dark:text-red-400">This model has a fixed context size set by the administrator.</p>
                    </div>
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="temperature" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Temperature</label>
                        <input type="number" id="temperature" v-model.number="form.llm_temperature" class="input-field mt-1" step="0.01" min="0" max="2" placeholder="e.g., 0.7" :disabled="areSettingsForced">
                    </div>
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="topK" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Top K</label>
                        <input type="number" id="topK" v-model.number="form.llm_top_k" class="input-field mt-1" step="1" min="1" placeholder="e.g., 50" :disabled="areSettingsForced">
                    </div>
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="topP" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Top P</label>
                        <input type="number" id="topP" v-model.number="form.llm_top_p" class="input-field mt-1" step="0.01" min="0" max="1" placeholder="e.g., 0.95" :disabled="areSettingsForced">
                    </div>
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="repeatPenalty" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Repeat Penalty</label>
                        <input type="number" id="repeatPenalty" v-model.number="form.llm_repeat_penalty" class="input-field mt-1" step="0.01" min="0" placeholder="e.g., 1.1" :disabled="areSettingsForced">
                    </div>
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="repeatLastN" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Repeat Last N</label>
                        <input type="number" id="repeatLastN" v-model.number="form.llm_repeat_last_n" class="input-field mt-1" step="1" min="0" placeholder="e.g., 64" :disabled="areSettingsForced">
                    </div>
                </fieldset>

                <!-- Toggle for 'think' blocks -->
                <div class="relative flex items-start" :class="{'opacity-60 cursor-not-allowed': areSettingsForced}">
                    <div class="flex h-6 items-center">
                        <input id="putThoughts" v-model="form.put_thoughts_in_context" type="checkbox" :disabled="areSettingsForced" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-blue-600 focus:ring-blue-600 dark:focus:ring-blue-600 dark:ring-offset-gray-800">
                    </div>
                    <div class="ml-3 text-sm leading-6">
                        <label for="putThoughts" class="font-medium text-gray-900 dark:text-gray-300">Include "think" blocks in context</label>
                        <p class="text-gray-500 dark:text-gray-400">Allows the AI to see its previous reasoning steps.</p>
                    </div>
                </div>

                <!-- Save Button -->
                <div class="flex justify-end pt-4">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges || areSettingsForced">
                        <span v-if="isLoading">Saving...</span>
                        <span v-else>Save LLM Settings</span>
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>
<style scoped>
.toolbox-select { @apply w-full text-left text-sm px-2.5 py-1.5 bg-gray-50 dark:bg-gray-700/50 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500; }
.menu-item-button { @apply w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between gap-2; }
.menu-item-button.selected { @apply bg-blue-100 dark:bg-blue-900/50 font-semibold; }
</style>