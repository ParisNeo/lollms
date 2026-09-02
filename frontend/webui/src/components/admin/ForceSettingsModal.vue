<!-- frontend/webui/src/components/admin/ForceSettingsModal.vue -->
<script setup>
import { ref, computed, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { useDataStore } from '../../stores/data';
import { storeToRefs } from 'pinia';
import GenericModal from '../modals/GenericModal.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import apiClient from '../../services/api';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const dataStore = useDataStore();

const { availableLLMModelsGrouped, availableTtiModelsGrouped, availableTtsModelsGrouped, availableSttModelsGrouped, availableVectorizers, availableTtvModelsGrouped, availableTtmModelsGrouped } = storeToRefs(dataStore);
const { globalSettings } = storeToRefs(adminStore);

const selectedModelProfile = ref('');
const selectedTtiProfile = ref('');
const selectedTtsProfile = ref('');
const selectedSttProfile = ref('');
const selectedTtvProfile = ref('');
const selectedTtmProfile = ref('');
const selectedRagProfile = ref('');
const targetMode = ref('force_always'); // 'force_always', 'force_once', 'set_default', 'set_beginner'
const forcedContextSize = ref(null);
const isLoading = ref(false);
const isHealing = ref(false);

const modes = [
    { id: 'force_always', title: 'God Mode (Force Always)', desc: 'Overrides user preferences and locks this exact configuration for all users.' },
    { id: 'force_once', title: 'Force Once (Batch Apply)', desc: 'Applies these profiles to all existing users now, allowing them to adjust it later.' },
    { id: 'set_default', title: 'System Default (New Users & Fallback)', desc: 'Assigned to newly registered accounts and used for fallback routing.' },
    { id: 'set_beginner', title: 'Beginner Default (UI Level 0)', desc: 'Auto-assigned to users operating in beginner mode.' }
];

onMounted(async () => {
    await Promise.allSettled([
        dataStore.fetchAvailableLollmsModels(),
        dataStore.fetchAvailableTtiModels(),
        dataStore.fetchAvailableTtsModels(),
        dataStore.fetchAvailableSttModels(),
        dataStore.fetchAvailableTtvModels(),
        dataStore.fetchAvailableTtmModels(),
        dataStore.fetchAvailableVectorizers(),
        adminStore.fetchGlobalSettings()
    ]);

    const currentGodModel = globalSettings.value.find(s => s.key === 'force_model_name')?.value;
    const currentDefaultModel = globalSettings.value.find(s => s.key === 'default_lollms_model_name')?.value;
    const currentCtx = globalSettings.value.find(s => s.key === 'force_context_size')?.value;
    const currentDefaultRag = globalSettings.value.find(s => s.key === 'default_safe_store_vectorizer')?.value;
    const currentDefaultTti = globalSettings.value.find(s => s.key === 'default_tti_binding_model')?.value;
    const currentDefaultTts = globalSettings.value.find(s => s.key === 'default_tts_binding_model')?.value;
    const currentDefaultStt = globalSettings.value.find(s => s.key === 'default_stt_binding_model')?.value;

    selectedModelProfile.value = currentGodModel || currentDefaultModel || '';
    if (currentCtx) forcedContextSize.value = Number(currentCtx);
    if (currentDefaultRag) selectedRagProfile.value = currentDefaultRag;
    if (currentDefaultTti) selectedTtiProfile.value = currentDefaultTti;
    if (currentDefaultTts) selectedTtsProfile.value = currentDefaultTts;
    if (currentDefaultStt) selectedSttProfile.value = currentDefaultStt;
});

async function handleApply() {
    if (!selectedModelProfile.value && !selectedRagProfile.value && !selectedTtiProfile.value && !selectedTtsProfile.value && !selectedSttProfile.value) {
        uiStore.addNotification('Please select at least one profile or setting to apply.', 'warning');
        return;
    }

    isLoading.value = true;
    try {
        const response = await apiClient.post('/api/admin/force-profiles', {
            mode: targetMode.value,
            lollms_model_name: selectedModelProfile.value || null,
            tti_binding_model_name: selectedTtiProfile.value || null,
            tts_binding_model_name: selectedTtsProfile.value || null,
            stt_binding_model_name: selectedSttProfile.value || null,
            ttv_binding_model_name: selectedTtvProfile.value || null,
            ttm_binding_model_name: selectedTtmProfile.value || null,
            rag_vectorizer_name: selectedRagProfile.value || null,
            context_size: forcedContextSize.value ? Number(forcedContextSize.value) : null
        });

        uiStore.addNotification(response.data.message || 'Profile policy applied successfully.', 'success');
        uiStore.closeModal('forceSettings');
    } catch (e) {
        uiStore.addNotification(e.response?.data?.detail || 'Failed to apply profile policy.', 'error');
    } finally {
        isLoading.value = false;
    }
}

async function handleHealOrphanedUsers() {
    isHealing.value = true;
    try {
        const res = await apiClient.post('/api/admin/bindings/migrate-and-heal');
        uiStore.addNotification(res.data.message || 'Profiles normalized and users healed.', 'success');
        await adminStore.fetchGlobalSettings(true);
    } catch (e) {
        uiStore.addNotification('Self-healing failed.', 'error');
    } finally {
        isHealing.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="forceSettings" title="Global Model Profile & Policy Center" maxWidthClass="max-w-3xl">
        <template #body>
            <div class="space-y-6 p-1">
                <!-- Mode Selector -->
                <div>
                    <label class="block text-xs font-black uppercase tracking-wider text-gray-500 mb-3">Enforcement Mode</label>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div 
                            v-for="m in modes" 
                            :key="m.id"
                            @click="targetMode = m.id"
                            class="p-4 rounded-2xl border-2 cursor-pointer transition-all duration-200 flex flex-col justify-between"
                            :class="targetMode === m.id ? 'border-blue-600 bg-blue-50/60 dark:bg-blue-950/30 text-blue-900 dark:text-blue-100 shadow-sm' : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'"
                        >
                            <div class="flex items-center justify-between mb-1">
                                <span class="font-bold text-xs">{{ m.title }}</span>
                                <IconCheckCircle v-if="targetMode === m.id" class="w-4 h-4 text-blue-600" />
                            </div>
                            <p class="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed">{{ m.desc }}</p>
                        </div>
                    </div>
                </div>

                <!-- Primary LLM Universal Model Profile Selection -->
                <div class="space-y-4 p-4 bg-gray-50 dark:bg-gray-900/40 rounded-2xl border border-gray-100 dark:border-gray-800">
                    <div>
                        <label class="block text-xs font-bold uppercase text-gray-700 dark:text-gray-300 tracking-wider mb-1">Primary LLM Model Profile *</label>
                        <select v-model="selectedModelProfile" class="input-field text-xs font-medium">
                            <option value="" disabled>-- Select Universal Model Profile --</option>
                            <optgroup v-for="group in availableLLMModelsGrouped" :key="group.label" :label="group.label">
                                <option v-for="item in group.items" :key="item.id" :value="item.id">
                                    {{ item.name }} {{ (item.vision_enabled || item.has_vision) ? '👁️' : '' }} ({{ item.id }})
                                </option>
                            </optgroup>
                        </select>
                    </div>

                    <div>
                        <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Forced Context Window Limit (tokens)</label>
                        <input type="number" v-model.number="forcedContextSize" class="input-field text-xs" placeholder="Leave empty to use profile auto-detected size (e.g. 32768)">
                    </div>
                </div>

                <!-- Auxiliary Modalities Defaults -->
                <div class="space-y-4">
                    <h4 class="text-xs font-black uppercase text-gray-400 tracking-widest">Auxiliary Modalities & Knowledge Defaults</h4>
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                        <div>
                            <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Default RAG Vectorizer</label>
                            <select v-model="selectedRagProfile" class="input-field text-xs">
                                <option value="">-- Unchanged --</option>
                                <optgroup v-for="g in availableVectorizers" :key="g.id" :label="g.alias || g.vectorizer_name">
                                    <option v-for="m in g.models" :key="`${g.alias}/${m.value}`" :value="`${g.alias}/${m.value}`">
                                        {{ m.name }}
                                    </option>
                                </optgroup>
                            </select>
                        </div>
                        <div>
                            <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Default TTI (Image)</label>
                            <select v-model="selectedTtiProfile" class="input-field text-xs">
                                <option value="">-- Unchanged --</option>
                                <optgroup v-for="g in availableTtiModelsGrouped" :key="g.label" :label="g.label">
                                    <option v-for="i in g.items" :key="i.id" :value="i.id">{{ i.name }}</option>
                                </optgroup>
                            </select>
                        </div>
                        <div>
                            <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Default TTS (Speech)</label>
                            <select v-model="selectedTtsProfile" class="input-field text-xs">
                                <option value="">-- Unchanged --</option>
                                <optgroup v-for="g in availableTtsModelsGrouped" :key="g.label" :label="g.label">
                                    <option v-for="i in g.items" :key="i.id" :value="i.id">{{ i.name }}</option>
                                </optgroup>
                            </select>
                        </div>
                        <div>
                            <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Default STT (Audio)</label>
                            <select v-model="selectedSttProfile" class="input-field text-xs">
                                <option value="">-- Unchanged --</option>
                                <optgroup v-for="g in availableSttModelsGrouped" :key="g.label" :label="g.label">
                                    <option v-for="i in g.items" :key="i.id" :value="i.id">{{ i.name }}</option>
                                </optgroup>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Self-Healing & Profile Normalization Utility -->
                <div class="flex items-center justify-between p-3.5 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/40 rounded-2xl">
                    <div class="flex flex-col">
                        <span class="text-xs font-bold text-blue-900 dark:text-blue-200">Self-Healing & Profile Normalization</span>
                        <span class="text-[10px] text-gray-500">Scan bindings, upgrade legacy aliases, and repair users assigned to deleted models.</span>
                    </div>
                    <button @click="handleHealOrphanedUsers" type="button" class="btn btn-secondary btn-xs flex items-center gap-1.5 shrink-0" :disabled="isHealing">
                        <IconRefresh class="w-3.5 h-3.5" :class="{ 'animate-spin': isHealing }" />
                        <span>{{ isHealing ? 'Healing...' : 'Heal All Users' }}</span>
                    </button>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-2 w-full">
                <button type="button" @click="uiStore.closeModal('forceSettings')" class="btn btn-secondary" :disabled="isLoading">Cancel</button>
                <button type="button" @click="handleApply" class="btn btn-primary" :disabled="isLoading || !selectedModelProfile">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-1.5 animate-spin" />
                    <span>Apply Policy Settings</span>
                </button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
@reference "tailwindcss";
</style>