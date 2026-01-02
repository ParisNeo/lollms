<script setup>
import { ref, onMounted, defineAsyncComponent, computed, markRaw } from 'vue';
import { useFlowStore } from '../stores/flow';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import IconShare from '../assets/icons/IconShare.vue';
import IconPlayCircle from '../assets/icons/IconPlayCircle.vue';
import IconSave from '../assets/icons/IconSave.vue';
import IconPlus from '../assets/icons/IconPlus.vue';

// Dynamic Components
const FlowEditor = defineAsyncComponent(() => import('../components/flow/FlowEditor.vue'));
const NodeCreatorModal = defineAsyncComponent(() => import('../components/flow/NodeCreatorModal.vue'));

const flowStore = useFlowStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const showCreator = ref(false);
const editorRef = ref(null);
const isAdmin = computed(() => authStore.isAdmin);

onMounted(() => {
    // Ensure definitions are loaded
    flowStore.fetchNodeDefinitions();
    // Update global header
    uiStore.setPageTitle({ title: 'Flow Studio', icon: markRaw(IconShare) });
});

async function saveCurrentFlow() { 
    if (flowStore.currentFlow) {
        await flowStore.saveFlow(flowStore.currentFlow.id, flowStore.currentFlow.data);
    }
}

async function runFlow() { 
    if (flowStore.currentFlow) { 
        await saveCurrentFlow(); 
        // Trigger the runner modal inside the editor
        if (editorRef.value) {
            editorRef.value.openRunner();
        }
    } 
}
</script>

<template>
    <!-- Inject Actions into Global Header -->
    <Teleport to="#global-header-actions-target">
        <div class="flex items-center gap-2">
            <button v-if="isAdmin" @click="showCreator = true" class="btn btn-secondary btn-sm gap-2" title="Define New Node Type">
                <IconPlus class="w-4 h-4" /> Define Node
            </button>
        </div>
    </Teleport>

    <!-- Main Content -->
    <div class="h-full flex flex-col relative bg-gray-50 dark:bg-gray-900">
        <div class="h-12 border-b dark:border-gray-700 flex items-center px-4 gap-2 bg-white dark:bg-gray-800 flex-shrink-0 justify-between">
            <div class="flex items-center gap-2">
                <button @click="saveCurrentFlow" class="btn btn-secondary btn-sm gap-2" :disabled="!flowStore.currentFlow"><IconSave class="w-4 h-4" /> Save</button>
                <button @click="runFlow" class="btn btn-primary btn-sm gap-2" :disabled="!flowStore.currentFlow"><IconPlayCircle class="w-4 h-4" /> Run Flow</button>
            </div>
            <div class="text-xs text-gray-500 font-mono" v-if="flowStore.currentFlow">
                <span class="font-bold hidden sm:inline mr-2">{{ flowStore.currentFlow.name }}</span>
                ID: {{ flowStore.currentFlow.id }}
            </div>
        </div>
        
        <div class="flex-grow relative bg-gray-100 dark:bg-gray-900 overflow-hidden">
            <Suspense>
                <template #default>
                    <FlowEditor ref="editorRef" v-if="flowStore.currentFlow" :flow="flowStore.currentFlow" />
                    <div v-else class="flex flex-col items-center justify-center h-full text-gray-400">
                        <IconShare class="w-16 h-16 mb-4 opacity-50" />
                        <p class="text-lg font-medium">Select or create a flow from the sidebar.</p>
                    </div>
                </template>
                <template #fallback>
                    <div class="flex items-center justify-center h-full text-gray-500">Loading...</div>
                </template>
            </Suspense>
        </div>
    </div>
    
    <Teleport to="body">
        <NodeCreatorModal v-if="showCreator" @close="showCreator = false" />
    </Teleport>
</template>
