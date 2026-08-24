<script setup>
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from './GenericModal.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const modalProps = computed(() => uiStore.modalData('appLog'));
const app = computed(() => modalProps.value?.app);
const logContent = ref('');
const isLoading = ref(false);

async function fetchLogs() {
    if (!app.value || isLoading.value) return;
    isLoading.value = true;
    try {
        logContent.value = await adminStore.fetchAppLog(app.value.id);
    } catch (error) {
        logContent.value = `Failed to load logs: ${error.message}`;
    } finally {
        isLoading.value = false;
    }
}

function ansiToHtml(text) {
    if (!text) return 'No log output available.';
    
    const ansiColors = {
        '30': '#1e293b', '31': '#f87171', '32': '#4ade80', '33': '#facc15',
        '34': '#60a5fa', '35': '#c084fc', '36': '#38bdf8', '37': '#f1f5f9',
        '90': '#94a3b8', '91': '#ef4444', '92': '#22c55e', '93': '#eab308',
        '94': '#3b82f6', '95': '#a855f7', '96': '#06b6d4', '97': '#ffffff',
    };
    
    let html = '';
    let currentStyles = [];
    
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const parts = text.split(/\x1b\[([0-9;]+)m/);
    
    for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
            if (currentStyles.length > 0) {
                html += `<span style="${currentStyles.join(';')}">${parts[i]}</span>`;
            } else {
                html += parts[i];
            }
        } else {
            const codes = parts[i].split(';');
            currentStyles = [];
            for (const code of codes) {
                if (code === '0' || code === '') {
                    currentStyles = [];
                } else if (code === '1') {
                    currentStyles.push('font-weight:bold');
                } else if (ansiColors[code]) {
                    currentStyles.push(`color:${ansiColors[code]}`);
                }
            }
        }
    }
    
    return html;
}

const formattedLogContent = computed(() => ansiToHtml(logContent.value));

watch(
    () => uiStore.isModalOpen('appLog'),
    (isOpen) => {
        if (isOpen && app.value) {
            fetchLogs();
        } else {
            logContent.value = '';
        }
    },
    { immediate: true }
);
</script>

<template>
    <GenericModal modal-name="appLog" :title="`Runtime Logs: ${app?.name || ''}`" max-width-class="max-w-4xl">
        <template #body>
            <div class="relative bg-gray-950 text-gray-100 font-mono text-xs p-4 rounded-2xl border border-gray-800 h-96 overflow-y-auto shadow-inner custom-scrollbar">
                <button 
                    @click="fetchLogs" 
                    class="sticky top-0 float-right p-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg shadow-sm transition-colors z-10" 
                    title="Refresh Logs"
                >
                    <IconAnimateSpin v-if="isLoading" class="w-3.5 h-3.5 animate-spin" />
                    <IconRefresh v-else class="w-3.5 h-3.5" />
                </button>
                <pre class="whitespace-pre-wrap break-words leading-relaxed" v-html="formattedLogContent"></pre>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('appLog')" type="button" class="btn btn-secondary btn-sm">Close</button>
        </template>
    </GenericModal>
</template>