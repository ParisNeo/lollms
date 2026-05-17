<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('featureInfo'));

const title = computed(() => props.value?.modalTitle || props.value?.label || 'Feature Information');
const description = computed(() => props.value?.modalDescription || '');
const systemPrompt = computed(() => props.value?.systemPrompt || '');
const colorClass = computed(() => props.value?.colorClass || '');
const icon = computed(() => props.value?.icon || null);

</script>

<template>
    <GenericModal modal-name="featureInfo" :title="title" max-width-class="max-w-2xl">
        <template #body>
            <div class="space-y-8 py-2">
                <!-- Header with Icon -->
                <div class="flex items-center gap-6 p-6 rounded-3xl border-2 border-dashed border-gray-100 dark:border-gray-800">
                    <div :class="['p-5 rounded-2xl shadow-xl', colorClass]">
                        <component :is="icon" class="w-10 h-10 fill-current" v-if="icon" />
                    </div>
                    <div class="flex flex-col">
                        <span class="modal-tag">Active Platform Feature</span>
                        <h3 class="text-xl font-bold text-gray-900 dark:text-white">{{ title }}</h3>
                    </div>
                </div>

                <!-- Main Description -->
                <div class="space-y-4">
                    <h4 class="text-xs font-black uppercase tracking-widest text-gray-400">Impact Analysis</h4>
                    <p class="text-base text-gray-600 dark:text-gray-300 leading-relaxed font-serif italic">
                        "{{ description }}"
                    </p>
                </div>

                <!-- Technical Details / System Prompt Injection -->
                <div v-if="systemPrompt" class="space-y-4 pt-6 border-t dark:border-gray-800">
                    <h4 class="text-xs font-black uppercase tracking-widest text-blue-500">Context Augmentation</h4>
                    <div class="bg-gray-50 dark:bg-gray-950 p-5 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-inner">
                        <p class="text-[11px] font-mono text-gray-500 dark:text-gray-400 leading-loose">
                            {{ systemPrompt }}
                        </p>
                    </div>
                    <p class="text-[10px] text-gray-400 italic">
                        Note: This content is dynamically injected into the model's primary directives to guide its behavior.
                    </p>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('featureInfo')" class="welcome-btn !bg-blue-600 text-white !py-3">
                Understood
            </button>
        </template>
    </GenericModal>
</template>
