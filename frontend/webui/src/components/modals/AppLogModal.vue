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

// Convert ANSI color codes to HTML
function ansiToHtml(text) {
    if (!text) return 'No log output.';
    
    const ansiColors = {
        '30': '#000000', '31': '#ff5555', '32': '#50fa7b', '33': '#f1fa8c',
        '34': '#6272a4', '35': '#ff79c6', '36': '#8be9fd', '37': '#f8f8f2',
        '90': '#6272a4', '91': '#ff6e6e', '92': '#69ff94', '93': '#ffffa5',
        '94': '#d6acff', '95': '#ff92df', '96': '#a4ffff', '97': '#ffffff',
    };
    
    const ansiBgColors = {
        '40': '#000000', '41': '#ff5555', '42': '#50fa7b', '43': '#f1fa8c',
        '44': '#6272a4', '45': '#ff79c6', '46': '#8be9fd', '47': '#f8f8f2',
        '100': '#6272a4', '101': '#ff6e6e', '102': '#69ff94', '103': '#ffffa5',
        '104': '#d6acff', '105': '#ff92df', '106': '#a4ffff', '107': '#ffffff',
    };
    
    let html = '';
    let currentStyles = [];
    
    // Escape HTML special characters
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Split by ANSI escape sequences
    const parts = text.split(/\x1b\[([0-9;]+)m/);
    
    for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
            // This is text content
            if (currentStyles.length > 0) {
                html += `<span style="${currentStyles.join(';')}">${parts[i]}</span>`;
            } else {
                html += parts[i];
            }
        } else {
            // This is an ANSI code
            const codes = parts[i].split(';');
            currentStyles = [];
            
            for (const code of codes) {
                if (code === '0' || code === '') {
                    // Reset
                    currentStyles = [];
                } else if (code === '1') {
                    // Bold
                    currentStyles.push('font-weight:bold');
                } else if (code === '2') {
                    // Dim
                    currentStyles.push('opacity:0.6');
                } else if (code === '3') {
                    // Italic
                    currentStyles.push('font-style:italic');
                } else if (code === '4') {
                    // Underline
                    currentStyles.push('text-decoration:underline');
                } else if (ansiColors[code]) {
                    // Foreground color
                    currentStyles.push(`color:${ansiColors[code]}`);
                } else if (ansiBgColors[code]) {
                    // Background color
                    currentStyles.push(`background-color:${ansiBgColors[code]}`);
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
    <GenericModal modalName="appLog" :title="`Logs: ${app?.name || ''}`" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="relative bg-gray-900 text-white font-mono text-xs p-4 rounded-md h-96 overflow-y-auto">
                <button @click="fetchLogs" class="absolute top-2 right-2 p-1.5 bg-gray-700 rounded-md hover:bg-gray-600" title="Refresh Logs">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4" />
                    <IconRefresh v-else class="w-4 h-4" />
                </button>
                <pre class="whitespace-pre-wrap break-words" v-html="formattedLogContent"></pre>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('appLog')" type="button" class="btn btn-secondary">Close</button>
        </template>
    </GenericModal>
</template>