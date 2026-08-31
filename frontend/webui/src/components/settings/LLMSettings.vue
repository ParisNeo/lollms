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
const { availableLLMModelsGrouped, isLoadingLollmsModels } = storeToRefs(dataStore);

const form = ref({
    lollms_model_name: '',
    llm_temperature: 0.7,
    llm_top_k: 50,
    llm_top_p: 0.95,
    llm_repeat_penalty: 1.1,
    llm_repeat_last_n: 64,
    put_thoughts_in_context: false,
    reasoning_activation: false,
    reasoning_effort: null,
    reasoning_summary: false
});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = {};

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
            llm_temperature: user.value.llm_temperature ?? null,
            llm_top_k: user.value.llm_top_k ?? null,
            llm_top_p: user.value.llm_top_p ?? null,
            llm_repeat_penalty: user.value.llm_repeat_penalty ?? null,
            llm_repeat_last_n: user.value.llm_repeat_last_n ?? null,
            put_thoughts_in_context: user.value.put_thoughts_in_context || false,
            reasoning_activation: user.value.reasoning_activation || false,
            reasoning_effort: user.value.reasoning_effort || null,
            reasoning_summary: user.value.reasoning_summary || false
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
        uiStore.addNotification('LLM model profile preferences saved.', 'success');
    } catch (error) {
        // Handled by API interceptor
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl border border-gray-100 dark:border-gray-700">
        <div class="px-6 py-5 border-b border-gray-100 dark:border-gray-700">
            <h2 class="text-xl font-bold text-gray-900 dark:text-white">LLM Universal Model Profiles</h2>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Select your default execution model profile and adjust generation parameters.
            </p>
        </div>
        <div class="p-6">
            <form @submit.prevent="handleSave" class="space-y-6">
                <!-- Model Selection Dropdown -->
                <div>
                    <label class="block text-xs font-bold uppercase text-gray-700 dark:text-gray-300 tracking-wider mb-1">Active Model Profile</label>
                    <div class="relative">
                        <button ref="llmTriggerRef" @click="isLlmMenuOpen = !isLlmMenuOpen" type="button" class="toolbox-select truncate w-full flex items-center justify-between">
                            <div class="flex items-center space-x-3 truncate">
                                <img v-if="selectedModel?.icon_base64" :src="selectedModel.icon_base64" class="h-8 w-8 rounded-lg object-cover"/>
                                <span v-else class="w-8 h-8 shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-100 dark:bg-gray-700 rounded-lg"><IconCpuChip class="w-5 h-5" /></span>
                                <div class="min-w-0 text-left">
                                    <span class="block font-bold text-sm truncate">{{ selectedModel?.name || 'Select a Model Profile' }}</span>
                                    <span v-if="selectedModel?.forced_context_size" class="text-[10px] font-mono text-blue-500">Context: {{ selectedModel.forced_context_size }} tokens</span>
                                </div>
                            </div>
                            <svg class="w-4 h-4 text-gray-400 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                        </button>
                        <Teleport to="body">
                            <Transition enter-active-class="transition ease-out duration-100" enter-from-class="transform opacity-0 scale-95" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-75" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-95">
                                <div v-if="isLlmMenuOpen" ref="llmFloatingRef" :style="llmFloatingStyles" v-on-click-outside="() => isLlmMenuOpen = false" class="z-50 w-84 origin-top-left rounded-xl bg-white dark:bg-gray-800 shadow-2xl ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none py-1 flex flex-col max-h-[50vh] border dark:border-gray-700">
                                    <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10 border-b dark:border-gray-700">
                                        <input type="text" v-model="modelSearchTerm" @click.stop placeholder="Search profiles..." class="input-field text-xs w-full">
                                    </div>
                                    <div class="p-1 grow overflow-y-auto">
                                        <div v-if="isLoadingLollmsModels" class="text-center p-4 text-sm text-gray-500">Loading profiles...</div>
                                        <div v-for="group in filteredAvailableLLMModels" :key="group.label">
                                            <h4 class="px-2 py-1.5 text-[10px] font-black uppercase tracking-wider text-gray-400 dark:text-gray-500">{{ group.label }}</h4>
                                            <button v-for="item in group.items" :key="item.id" @click="selectModel(item.id)" class="menu-item-button" :class="{'selected': activeModelName === item.id}">
                                                <div class="flex items-center space-x-3 truncate">
                                                    <img v-if="item.icon_base64" :src="item.icon_base64" class="h-6 w-6 rounded-md object-cover shrink-0" />
                                                    <IconCpuChip v-else class="w-6 h-6 p-0.5 text-gray-500 dark:text-gray-400 shrink-0" />
                                                    <div class="truncate text-left">
                                                        <p class="font-medium truncate text-xs">{{ item.name }}</p>
                                                        <p v-if="item.forced_context_size" class="text-[9px] font-mono text-gray-400">{{ item.forced_context_size }} tokens</p>
                                                    </div>
                                                </div>
                                                <div class="flex items-center gap-2 shrink-0">
                                                    <IconCheckCircle v-if="activeModelName === item.id" class="w-4 h-4 text-emerald-500" />
                                                    <IconEye v-if="item.vision_enabled || item.has_vision" class="w-4 h-4 text-blue-500" title="Vision Active" />
                                                </div>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </Transition>
                        </Teleport>
                    </div>
                </div>
                
                <div v-if="areSettingsForced" class="p-4 bg-amber-50 dark:bg-amber-950/30 border-l-4 border-amber-500 rounded-r-xl text-amber-900 dark:text-amber-200">
                    <p class="font-bold text-xs">Profile Overrides Enforced</p>
                    <p class="text-xs mt-0.5">Parameters for this profile are fixed by the administrator or profile policy.</p>
                </div>

                <!-- Generation Parameters -->
                <fieldset class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" :class="{'opacity-60': areSettingsForced}">
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="temperature" class="block text-xs font-bold uppercase text-gray-500 mb-1">Temperature</label>
                        <input type="number" id="temperature" v-model.number="form.llm_temperature" class="input-field text-xs" step="0.01" min="0" max="2" placeholder="e.g., 0.7" :disabled="areSettingsForced">
                    </div>
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="topK" class="block text-xs font-bold uppercase text-gray-500 mb-1">Top K</label>
                        <input type="number" id="topK" v-model.number="form.llm_top_k" class="input-field text-xs" step="1" min="1" placeholder="e.g., 50" :disabled="areSettingsForced">
                    </div>
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="topP" class="block text-xs font-bold uppercase text-gray-500 mb-1">Top P</label>
                        <input type="number" id="topP" v-model.number="form.llm_top_p" class="input-field text-xs" step="0.01" min="0" max="1" placeholder="e.g., 0.95" :disabled="areSettingsForced">
                    </div>
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="repeatPenalty" class="block text-xs font-bold uppercase text-gray-500 mb-1">Repeat Penalty</label>
                        <input type="number" id="repeatPenalty" v-model.number="form.llm_repeat_penalty" class="input-field text-xs" step="0.01" min="0" placeholder="e.g., 1.1" :disabled="areSettingsForced">
                    </div>
                    <div :class="{'cursor-not-allowed': areSettingsForced}">
                        <label for="repeatLastN" class="block text-xs font-bold uppercase text-gray-500 mb-1">Repeat Last N</label>
                        <input type="number" id="repeatLastN" v-model.number="form.llm_repeat_last_n" class="input-field text-xs" step="1" min="0" placeholder="e.g., 64" :disabled="areSettingsForced">
                    </div>
                </fieldset>

                <!-- Reasoning Section -->
                <div class="border-t dark:border-gray-700/60 pt-4">
                    <h3 class="font-bold text-xs uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-3">Reasoning & Thinking Mode</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-5" :class="{'opacity-60': areSettingsForced}">
                        <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-900/40 p-3 rounded-xl border dark:border-gray-700">
                            <span class="grow flex flex-col pr-4">
                                <span class="text-xs font-bold text-gray-800 dark:text-gray-200">Enable Thinking Mode</span>
                                <span class="text-[10px] text-gray-400">Activates native reasoning traces if supported by the model profile.</span>
                            </span>
                            <button @click="form.reasoning_activation = !form.reasoning_activation" type="button" :disabled="areSettingsForced" :class="[form.reasoning_activation ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form.reasoning_activation ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>

                        <div :class="{'cursor-not-allowed': areSettingsForced}">
                            <label for="reasoning-effort" class="block text-xs font-bold uppercase text-gray-500 mb-1">Reasoning Effort</label>
                            <select id="reasoning-effort" v-model="form.reasoning_effort" class="input-field text-xs" :disabled="areSettingsForced">
                                <option :value="null">Default</option>
                                <option value="low">Low</option>
                                <option value="medium">Medium</option>
                                <option value="high">High</option>
                            </select>
                        </div>

                        <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-900/40 p-3 rounded-xl border dark:border-gray-700">
                             <span class="grow flex flex-col pr-4">
                                <span class="text-xs font-bold text-gray-800 dark:text-gray-200">Reasoning Summary</span>
                                <span class="text-[10px] text-gray-400">Summarize intermediate chain-of-thought tokens.</span>
                            </span>
                            <button @click="form.reasoning_summary = !form.reasoning_summary" type="button" :disabled="areSettingsForced" :class="[form.reasoning_summary ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form.reasoning_summary ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>
                        
                        <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-900/40 p-3 rounded-xl border dark:border-gray-700">
                             <span class="grow flex flex-col pr-4">
                                <span class="text-xs font-bold text-gray-800 dark:text-gray-200">Include "think" blocks in history</span>
                                <span class="text-[10px] text-gray-400">Allows subsequent generation turns to see past reasoning traces.</span>
                            </span>
                            <button @click="form.put_thoughts_in_context = !form.put_thoughts_in_context" type="button" :disabled="areSettingsForced" :class="[form.put_thoughts_in_context ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form.put_thoughts_in_context ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Save Button -->
                <div class="flex justify-end pt-4 border-t dark:border-gray-700">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges || areSettingsForced">
                        <span v-if="isLoading">Saving Profile...</span>
                        <span v-else>Save Profile Settings</span>
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";

.toolbox-select { @apply w-full text-left text-sm px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500; }
.menu-item-button { @apply w-full text-left p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between gap-2 transition-colors; }
.menu-item-button.selected { @apply bg-blue-50 dark:bg-blue-900/40 font-bold text-blue-600 dark:text-blue-300; }
</style>