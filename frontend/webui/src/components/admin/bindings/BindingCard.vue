
<!-- frontend/webui/src/components/admin/bindings/BindingCard.vue -->
<script setup>
import { ref, computed, defineAsyncComponent, watch, onUnmounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import { useTasksStore } from '../../../stores/tasks';
import { BINDING_TYPES, bindingActions } from './bindingConfigs';
import { parsedMarkdown as parseMarkdown } from '../../../services/markdownParser';

import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconCog from '../../../assets/icons/IconCog.vue';
import IconDatabase from '../../../assets/icons/IconDatabase.vue';
import IconTerminal from '../../../assets/icons/ui/IconTerminal.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconArrowPath from '../../../assets/icons/IconArrowPath.vue';
import IconPlayCircle from '../../../assets/icons/IconPlayCircle.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconClose from '../../../assets/icons/IconClose.vue';
import IconSave from '../../../assets/icons/IconSave.vue';
import JsonRenderer from '../../ui/JsonRenderer.vue';

const props = defineProps({
    binding: { type: Object, required: true },
    bindingType: { type: String, required: true },
    availableTypes: { type: Array, default: () => [] },
});

const emit = defineEmits(['saved', 'deleted']);

const adminStore = useAdminStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const { tasks } = storeToRefs(tasksStore);

const cfg = computed(() => BINDING_TYPES[props.bindingType] || BINDING_TYPES.llm);
const actions = computed(() => bindingActions(props.bindingType));

const isDrawerOpen = ref(false);
const drawerTab = ref('settings'); // settings | models | commands
const isSaving = ref(false);
const isKeyVisible = ref({});
const commandParams = ref({});
const currentCommandTaskId = ref(null);
const lastExecutedCommandName = ref(null);
const activeCommandResult = ref(null);
const isTogglingActive = ref(false);

const form = ref(buildInitialForm());

function buildInitialForm() {
    return {
        alias: props.binding.alias || '',
        name: props.binding.name || '',
        config: JSON.parse(JSON.stringify(props.binding.config || {})),
        default_model_name: props.binding.default_model_name || '',
        is_active: props.binding.is_active !== false,
    };
}

const selectedTypeDescriptor = computed(() => {
    if (!form.value.name || !Array.isArray(props.availableTypes)) return null;
    const target = form.value.name.toLowerCase();
    return props.availableTypes.find(t => {
        const bn = (t.binding_name || t.name || '').toLowerCase();
        return bn === target;
    }) || null;
});

const hasCommands = computed(() => {
    if (!cfg.value.supportsCommands) return false;
    const desc = selectedTypeDescriptor.value;
    return !!(desc && Array.isArray(desc.commands) && desc.commands.length > 0);
});

const hasZoo = computed(() => {
    // Zoo availability is not statically known without a probe; expose the tab
    // only when the modality supports it. The panel itself handles empty state.
    return !!cfg.value.supportsZoo;
});

const allFormParameters = computed(() => {
    const desc = selectedTypeDescriptor.value;
    if (!desc) return [];
    const seen = new Set();
    const out = [];
    const sources = [desc.global_input_parameters, desc.input_parameters, desc.parameters];
    for (const src of sources) {
        if (!Array.isArray(src)) continue;
        for (const p of src) {
            if (!p || !p.name || seen.has(p.name)) continue;
            if (p.name === 'model_name' || p.name === 'model') continue;
            seen.add(p.name);
            out.push(p);
        }
    }
    // Also surface ad-hoc config keys not declared in the descriptor
    const declared = new Set(out.map(p => p.name));
    for (const key of Object.keys(form.value.config || {})) {
        if (declared.has(key) || key === 'model_name' || key === 'model' || key === 'class') continue;
        const val = form.value.config[key];
        out.push({
            name: key,
            type: typeof val === 'boolean' ? 'bool' : (typeof val === 'number' ? 'float' : 'str'),
            description: '(Custom configuration parameter)',
            mandatory: false,
        });
    }
    return out;
});

const currentTask = computed(() => {
    if (!currentCommandTaskId.value) return null;
    return tasks.value.find(t => t.id === currentCommandTaskId.value) || null;
});

watch(currentTask, (t) => {
    if (t && t.status === 'completed') activeCommandResult.value = t.result;
}, { deep: true });

watch(() => props.binding, () => {
    form.value = buildInitialForm();
});

function parseOptions(options) {
    if (typeof options === 'string') return options.split(',').map(o => o.trim()).filter(Boolean);
    if (Array.isArray(options)) return options.map(o => typeof o === 'object' && o !== null ? (o.value || o.name || o.label) : String(o)).filter(Boolean);
    return [];
}

function openDrawer(tab = 'settings') {
    form.value = buildInitialForm();
    drawerTab.value = tab;
    isDrawerOpen.value = true;
    isKeyVisible.value = {};
    commandParams.value = {};
    currentCommandTaskId.value = null;
    lastExecutedCommandName.value = null;
    activeCommandResult.value = null;
    // Bind Escape to close the modal while it's open (no leak: removed in
    // closeDrawer and on unmount).
    window.addEventListener('keydown', _handleModalEscape);
    if (hasCommands.value) {
        const desc = selectedTypeDescriptor.value;
        const params = {};
        (desc.commands || []).forEach(cmd => {
            params[cmd.name] = {};
            (cmd.parameters || []).forEach(p => {
                params[cmd.name][p.name] = p.default !== undefined ? p.default : '';
            });
        });
        commandParams.value = params;
    }
}

function _handleModalEscape(e) {
    if (e.key === 'Escape') closeDrawer();
}

function closeDrawer() {
    isDrawerOpen.value = false;
    window.removeEventListener('keydown', _handleModalEscape);
}

onUnmounted(() => {
    // Defensive: if the component unmounts while the modal is open, release
    // the global Escape listener.
    window.removeEventListener('keydown', _handleModalEscape);
});

async function toggleActive() {
    isTogglingActive.value = true;
    try {
        const fn = adminStore[actions.value.update];
        if (typeof fn === 'function') {
            await fn.call(adminStore, props.binding.id, { is_active: !props.binding.is_active });
            emit('saved');
        }
    } finally {
        isTogglingActive.value = false;
    }
}

async function saveSettings() {
    if (!form.value.alias.trim() || !form.value.name) {
        uiStore.addNotification('Alias and Engine Type are required.', 'warning');
        return;
    }
    isSaving.value = true;
    try {
        const payload = {
            alias: form.value.alias,
            name: form.value.name,
            config: form.value.config || {},
            is_active: form.value.is_active,
            default_model_name: form.value.default_model_name || null,
        };
        const fn = adminStore[actions.value.update];
        if (typeof fn !== 'function') throw new Error(`Missing store action: ${actions.value.update}`);
        await fn.call(adminStore, props.binding.id, payload);
        emit('saved');
        closeDrawer();
    } catch (e) {
        console.error('BindingCard save failed:', e);
    } finally {
        isSaving.value = false;
    }
}

async function deleteBinding() {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete binding '${props.binding.alias}'?`,
        message: 'This permanently removes the binding and all its model profiles.',
        confirmText: 'Delete',
    });
    if (!confirmed.confirmed && !confirmed) return;
    try {
        const fn = adminStore[actions.value.remove];
        if (typeof fn === 'function') {
            await fn.call(adminStore, props.binding.id);
            emit('deleted');
            closeDrawer();
        }
    } catch (e) {
        uiStore.addNotification('Failed to delete binding.', 'error');
    }
}

async function executeCommand(cmd) {
    currentCommandTaskId.value = null;
    activeCommandResult.value = null;
    lastExecutedCommandName.value = cmd.name;
    try {
        const fn = adminStore[actions.value.executeCommand];
        if (typeof fn !== 'function') throw new Error('Command executor not available');
        const taskInfo = await fn.call(adminStore, props.binding.id, cmd.name, commandParams.value[cmd.name] || {});
        if (taskInfo?.id) {
            currentCommandTaskId.value = taskInfo.id;
            tasksStore.addTask(taskInfo);
            uiStore.addNotification(`Task started: ${cmd.title || cmd.name}`, 'success');
        }
    } catch (e) {
        uiStore.addNotification(`Command failed: ${e.message}`, 'error');
    }
}

function refreshAfterProfilesChange() {
    emit('saved');
}
</script>

<template>
    <div
        class="bg-white dark:bg-gray-800/90 p-5 rounded-2xl shadow-xs border border-gray-200/80 dark:border-gray-700/80 flex flex-col justify-between hover:border-blue-500 transition-all group"
    >
        <div>
            <div class="flex items-start justify-between gap-3 mb-3">
                <button
                    @click="openDrawer('settings')"
                    class="flex items-center gap-3 grow min-w-0 text-left"
                >
                    <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                         :class="binding.is_active
                             ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                             : 'bg-gray-100 dark:bg-gray-700 text-gray-400'">
                        <IconCpuChip class="w-5 h-5" />
                    </div>
                    <div class="min-w-0">
                        <h4 class="font-bold text-sm text-gray-900 dark:text-white truncate">{{ binding.alias }}</h4>
                        <p class="text-[10px] text-gray-500 font-mono capitalize truncate">{{ binding.name }}</p>
                    </div>
                </button>
                <button
                    @click.stop="toggleActive"
                    :disabled="isTogglingActive"
                    type="button"
                    :class="[binding.is_active ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors disabled:opacity-50']"
                    :title="binding.is_active ? 'Deactivate' : 'Activate'"
                >
                    <span :class="[binding.is_active ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                </button>
            </div>

            <div class="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700/60 text-xs space-y-1.5 font-mono">
                <div class="flex justify-between items-center text-[10px]">
                    <span class="text-gray-400">Profiles:</span>
                    <span class="font-bold text-blue-500">{{ Object.keys(binding.model_aliases || {}).length }}</span>
                </div>
                <div v-if="binding.default_model_name" class="flex justify-between items-center text-[10px] truncate">
                    <span class="text-gray-400">Default:</span>
                    <span class="font-bold text-gray-700 dark:text-gray-300 truncate max-w-[140px]">{{ binding.default_model_name }}</span>
                </div>
            </div>
        </div>

        <div class="border-t dark:border-gray-700/60 pt-3 mt-4 flex justify-between items-center text-xs">
            <button @click="openDrawer('settings')" class="text-blue-500 font-bold text-[10px] uppercase tracking-wider hover:underline">
                Configure &rarr;
            </button>
            <button @click="deleteBinding" class="text-rose-500 hover:text-rose-700 font-bold text-[10px] uppercase">Delete</button>
        </div>

        <!-- ── Detail Modal (centered) ── -->
        <Teleport to="body">
            <div v-if="isDrawerOpen" class="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4">
                <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="closeDrawer"></div>
                <div class="relative w-full max-w-5xl max-h-[92vh] bg-white dark:bg-gray-900 shadow-2xl flex flex-col rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                    <!-- Modal header -->
                    <div class="shrink-0 flex items-center justify-between px-6 py-4 border-b dark:border-gray-700">
                        <div class="min-w-0">
                            <span class="text-[9px] font-black uppercase text-blue-500 tracking-widest">{{ cfg.label }} Binding</span>
                            <h3 class="text-lg font-black text-gray-900 dark:text-white truncate">{{ form.alias || binding.alias }}</h3>
                        </div>
                        <button @click="closeDrawer" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
                            <IconClose class="w-5 h-5" />
                        </button>
                    </div>

                    <!-- Tabs -->
                    <div class="shrink-0 flex items-center gap-1 px-6 pt-3 border-b dark:border-gray-700 text-xs font-bold flex-wrap">
                        <button
                            @click="drawerTab = 'settings'"
                            :class="drawerTab === 'settings' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                            class="px-3 py-2 flex items-center gap-1.5"
                        >
                            <IconCog class="w-3.5 h-3.5" />
                            <span>Settings</span>
                        </button>
                        <button
                            @click="drawerTab = 'models'"
                            :class="drawerTab === 'models' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                            class="px-3 py-2 flex items-center gap-1.5"
                        >
                            <IconDatabase class="w-3.5 h-3.5" />
                            <span>Profiles</span>
                        </button>
                        <button
                            v-if="hasCommands"
                            @click="drawerTab = 'commands'"
                            :class="drawerTab === 'commands' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                            class="px-3 py-2 flex items-center gap-1.5"
                        >
                            <IconTerminal class="w-3.5 h-3.5" />
                            <span>Commands</span>
                        </button>
                        <button
                            v-if="hasZoo"
                            @click="drawerTab = 'zoo'"
                            :class="drawerTab === 'zoo' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                            class="px-3 py-2 flex items-center gap-1.5"
                        >
                            <IconPlus class="w-3.5 h-3.5" />
                            <span>Zoo</span>
                        </button>
                    </div>

                    <!-- Body -->
                    <div class="grow min-h-0 overflow-y-auto custom-scrollbar px-6 py-5">
                        <!-- Settings Tab -->
                        <div v-if="drawerTab === 'settings'" class="space-y-5">
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Binding Alias</label>
                                    <input v-model="form.alias" type="text" class="input-field text-xs" />
                                </div>
                                <div>
                                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Engine Type</label>
                                    <select v-model="form.name" disabled class="input-field text-xs">
                                        <option :value="form.name">{{ form.name }}</option>
                                    </select>
                                </div>
                            </div>

                            <div v-if="allFormParameters.length" class="space-y-4 border-t dark:border-gray-700 pt-4">
                                <h4 class="text-xs font-bold uppercase text-gray-500">Engine Parameters</h4>
                                <div v-for="param in allFormParameters" :key="param.name" class="space-y-1">
                                    <label class="block text-xs font-bold uppercase text-gray-500">
                                        {{ param.name.replace(/_/g, ' ') }}
                                        <span v-if="param.mandatory" class="text-red-500">*</span>
                                    </label>
                                    <select
                                        v-if="param.options && param.options.length"
                                        v-model="form.config[param.name]"
                                        class="input-field text-xs"
                                    >
                                        <option v-for="opt in parseOptions(param.options)" :key="opt" :value="opt">{{ opt }}</option>
                                    </select>
                                    <div v-else-if="param.type === 'bool'" class="flex items-center justify-between p-2.5 bg-gray-50 dark:bg-gray-800 rounded-lg border dark:border-gray-700">
                                        <span class="text-xs text-gray-600 dark:text-gray-400">{{ param.description }}</span>
                                        <button
                                            @click="form.config[param.name] = !form.config[param.name]"
                                            type="button"
                                            :class="[form.config[param.name] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors']"
                                        >
                                            <span :class="[form.config[param.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                        </button>
                                    </div>
                                    <div v-else class="relative">
                                        <input
                                            :type="(param.name.includes('key') || param.name.includes('token')) && !isKeyVisible[param.name] ? 'password' : 'text'"
                                            v-model="form.config[param.name]"
                                            class="input-field text-xs"
                                            :placeholder="param.description || param.default || ''"
                                            autocomplete="off"
                                        />
                                        <button
                                            v-if="param.name.includes('key') || param.name.includes('token')"
                                            type="button"
                                            @click="isKeyVisible[param.name] = !isKeyVisible[param.name]"
                                            class="absolute inset-y-0 right-0 px-2 flex items-center text-gray-400 hover:text-gray-600"
                                        >
                                            <IconEyeOff v-if="isKeyVisible[param.name]" class="w-4 h-4" />
                                            <IconEye v-else class="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-700">
                                <span class="text-xs font-bold text-gray-800 dark:text-gray-200">Active Connection</span>
                                <button
                                    @click="form.is_active = !form.is_active"
                                    type="button"
                                    :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors']"
                                >
                                    <span :class="[form.is_active ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                        </div>

                        <!-- Profiles Tab -->
                        <div v-else-if="drawerTab === 'models'">
                            <ModelProfilesGridHost
                                :binding="binding"
                                :binding-type="bindingType"
                                @changed="refreshAfterProfilesChange"
                            />
                        </div>

                        <!-- Commands Tab -->
                        <div v-else-if="drawerTab === 'commands' && hasCommands" class="space-y-4">
                            <div v-for="cmd in (selectedTypeDescriptor?.commands || [])" :key="cmd.name" class="p-4 bg-gray-50 dark:bg-gray-800/60 rounded-2xl border dark:border-gray-700">
                                <div class="flex items-start justify-between gap-3 mb-2">
                                    <div class="min-w-0">
                                        <h5 class="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2">
                                            <IconTerminal class="w-4 h-4 text-blue-500" />
                                            <span>{{ cmd.title || cmd.name }}</span>
                                        </h5>
                                        <p class="text-xs text-gray-500 mt-0.5">{{ cmd.description }}</p>
                                    </div>
                                    <button
                                        @click="executeCommand(cmd)"
                                        class="btn btn-primary btn-sm flex items-center gap-1.5 shrink-0"
                                        :disabled="currentTask && (currentTask.status === 'running' || currentTask.status === 'pending')"
                                    >
                                        <IconPlayCircle class="w-4 h-4" />
                                        <span>Execute</span>
                                    </button>
                                </div>

                                <div v-if="cmd.parameters && cmd.parameters.length" class="space-y-2 bg-white dark:bg-gray-900/40 p-3 rounded-xl border dark:border-gray-700 mt-2">
                                    <div v-for="p in cmd.parameters" :key="p.name">
                                        <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">{{ p.name }}</label>
                                        <input
                                            v-if="p.type !== 'bool'"
                                            type="text"
                                            v-model="commandParams[cmd.name][p.name]"
                                            class="input-field text-xs"
                                            :placeholder="p.default"
                                        />
                                        <button
                                            v-else
                                            @click="commandParams[cmd.name][p.name] = !commandParams[cmd.name][p.name]"
                                            type="button"
                                            :class="[commandParams[cmd.name][p.name] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors']"
                                        >
                                            <span :class="[commandParams[cmd.name][p.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                        </button>
                                    </div>
                                </div>

                                <div v-if="currentTask && lastExecutedCommandName === cmd.name && (currentTask.status === 'running' || currentTask.status === 'pending')" class="mt-3">
                                    <div class="flex justify-between text-xs mb-1 font-semibold text-blue-600">
                                        <span>Running...</span>
                                        <span>{{ currentTask.progress }}%</span>
                                    </div>
                                    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                                        <div class="bg-blue-600 h-1.5 rounded-full transition-all" :style="{ width: currentTask.progress + '%' }"></div>
                                    </div>
                                </div>

                                <div v-if="activeCommandResult && lastExecutedCommandName === cmd.name && currentTask?.status === 'completed'" class="mt-3 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl">
                                    <h6 class="text-xs font-bold text-green-800 dark:text-green-300 mb-2 flex items-center gap-1.5">
                                        <IconCheckCircle class="w-3.5 h-3.5" />
                                        <span>Command Finished</span>
                                    </h6>
                                    <div v-if="typeof activeCommandResult === 'object'">
                                        <JsonRenderer :json="activeCommandResult" />
                                    </div>
                                    <div v-else class="whitespace-pre-wrap text-xs font-mono text-gray-800 dark:text-gray-200">{{ activeCommandResult }}</div>
                                </div>
                            </div>
                        </div>

                        <!-- Zoo Tab -->
                        <div v-else-if="drawerTab === 'zoo' && hasZoo">
                            <BindingZooHost :binding="binding" :binding-type="bindingType" />
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="shrink-0 flex items-center justify-between gap-3 px-6 py-3 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
                        <button @click="deleteBinding" class="btn btn-secondary text-rose-500 flex items-center gap-1.5">
                            <IconTrash class="w-4 h-4" />
                            <span>Delete Binding</span>
                        </button>
                        <div class="flex items-center gap-2">
                            <button @click="closeDrawer" class="btn btn-secondary">
                                <IconClose class="w-4 h-4 mr-1.5" />
                                Close
                            </button>
                            <button
                                v-if="drawerTab === 'settings'"
                                @click="saveSettings"
                                :disabled="isSaving"
                                class="btn btn-primary flex items-center gap-1.5"
                            >
                                <IconAnimateSpin v-if="isSaving" class="w-4 h-4 animate-spin" />
                                <IconSave v-else class="w-4 h-4" />
                                <span>{{ isSaving ? 'Saving...' : 'Save Settings' }}</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </Teleport>
    </div>
</template>

<script>
import { defineAsyncComponent } from 'vue';
// Lazy wrappers break the circular import chain: BindingCard imports
// BindingSettingsPanel's ModelsGrid child indirectly, so we import it async
// inside the component's own script block.
export default {
    components: {
        ModelProfilesGridHost: defineAsyncComponent(() => import('./ModelProfilesGrid.vue')),
        BindingZooHost: defineAsyncComponent(() => import('./BindingZoo.vue')),
    },
};
</script>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>
