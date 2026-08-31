<template>
    <GenericModal modal-name="modelCard" :title="model?.alias?.title || 'Universal Model Profile'" maxWidthClass="max-w-lg">
        <template #body>
            <div v-if="model && model.alias" class="space-y-4 p-1">
                <div class="flex items-center gap-4 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-800">
                    <img v-if="model.alias.icon" :src="model.alias.icon" class="w-14 h-14 rounded-xl object-cover border dark:border-gray-700 shadow-sm">
                    <IconCpuChip v-else class="w-14 h-14 text-gray-400 p-2.5 border dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800" />
                    <div class="min-w-0">
                        <h2 class="text-base font-bold text-gray-900 dark:text-white truncate">{{ model.alias.title || model.name }}</h2>
                        <p class="text-xs font-mono text-blue-600 dark:text-blue-400 truncate">{{ model.id }}</p>
                    </div>
                </div>

                <div v-if="model.alias.description" class="space-y-1">
                    <h3 class="text-xs font-bold uppercase text-gray-400 tracking-wider">Description</h3>
                    <p class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed">{{ model.alias.description }}</p>
                </div>

                <div class="grid grid-cols-2 gap-3 pt-2 border-t dark:border-gray-800 text-xs">
                    <div class="p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-800">
                        <span class="block text-[10px] font-bold uppercase text-gray-400 mb-0.5">Vision Support</span>
                        <span :class="(model.alias.vision_enabled || model.alias.has_vision) ? 'text-emerald-600 dark:text-emerald-400 font-bold' : 'text-gray-400'">
                            {{ (model.alias.vision_enabled || model.alias.has_vision) ? '✓ Multimodal Vision' : 'Text Only' }}
                        </span>
                    </div>
                    <div class="p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-800">
                        <span class="block text-[10px] font-bold uppercase text-gray-400 mb-0.5">Context Window</span>
                        <span class="font-mono font-bold text-blue-600 dark:text-blue-400">
                            {{ (model.alias.forced_context_size || model.alias.ctx_size) ? `${(model.alias.forced_context_size || model.alias.ctx_size).toLocaleString()} tokens` : 'Auto-detected' }}
                        </span>
                    </div>
                </div>

                <div v-if="model.alias.routing_config && Object.keys(model.alias.routing_config).length > 0" class="p-3 bg-purple-50/50 dark:bg-purple-950/20 rounded-xl border border-purple-100 dark:border-purple-900/40 text-xs space-y-1.5">
                    <span class="text-[10px] font-bold uppercase tracking-wider text-purple-900 dark:text-purple-300 block">Smart Router Profile</span>
                    <p v-if="model.alias.routing_config.description" class="text-[11px] text-gray-600 dark:text-gray-300 italic">"{{ model.alias.routing_config.description }}"</p>
                    <div class="flex items-center gap-4 text-[10px] font-mono text-purple-700 dark:text-purple-300">
                        <span>Tier: <b>{{ model.alias.routing_config.complexity_tier || 2 }}</b></span>
                        <span>Priority: <b>{{ model.alias.routing_config.priority || 1 }}</b></span>
                        <span>Latency: <b>{{ model.alias.routing_config.avg_latency_ms || 200 }}ms</b></span>
                    </div>
                </div>
            </div>
            <div v-else class="text-center p-6 text-xs text-gray-400">
                Model profile details not available.
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('modelCard')" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>
</template>

<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';

const uiStore = useUiStore();
const model = computed(() => uiStore.modalData('modelCard')?.model);
</script>