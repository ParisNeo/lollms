<script setup>
import { computed, onMounted, ref } from 'vue';
import { useSkillsStore } from '../../stores/skills';
import { useUiStore } from '../../stores/ui';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const props = defineProps({
    searchTerm: { type: String, default: '' }
});

const skillsStore = useSkillsStore();
const uiStore = useUiStore();

const fileInput = ref(null);

onMounted(() => {
    if (skillsStore.skills.length === 0) {
        skillsStore.fetchSkills();
    }
});

const filteredSkills = computed(() => {
    const term = props.searchTerm.toLowerCase();
    if (!term) return skillsStore.skills;
    return skillsStore.skills.filter(s => s.name.toLowerCase().includes(term) || (s.description && s.description.toLowerCase().includes(term)));
});

function editSkill(skill) {
    uiStore.openModal('skillEditor', { skill });
}

async function deleteSkill(skill) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Skill',
        message: `Are you sure you want to delete '${skill.name}'?`,
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        await skillsStore.deleteSkill(skill.id);
    }
}

function triggerImport() {
    fileInput.value?.click();
}

async function handleFileImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    try {
        await skillsStore.importSkill(file);
    } finally {
        event.target.value = '';
    }
}
</script>

<template>
    <div class="h-full flex flex-col">
        <div class="flex justify-between items-center mb-2 px-2">
            <span class="text-xs font-bold text-gray-500 uppercase tracking-widest">My Skills</span>
            <button @click="triggerImport" class="text-xs text-blue-500 hover:underline">Import File</button>
            <input type="file" ref="fileInput" @change="handleFileImport" class="hidden" accept=".xml,.md,.txt">
        </div>

        <div v-if="skillsStore.isLoading" class="text-center p-4 text-gray-500">Loading skills...</div>
        <div v-else-if="filteredSkills.length === 0" class="empty-state-flat">
            <p class="text-base font-medium text-slate-600 dark:text-gray-300 mb-2">
                 {{ searchTerm ? 'No matches found' : 'No skills yet' }}
            </p>
             <p class="text-sm text-slate-500 dark:text-gray-400">
                Create a new skill to teach the AI new capabilities.
            </p>
        </div>
        <div v-else class="space-y-1 flex-1 overflow-y-auto custom-scrollbar">
            <div v-for="skill in filteredSkills" :key="skill.id" 
                 class="group flex items-center justify-between p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                 @click="editSkill(skill)">
                <div class="flex items-center gap-3 min-w-0">
                    <IconSparkles class="w-4 h-4 flex-shrink-0 text-teal-500" />
                    <div class="flex flex-col min-w-0">
                        <span class="text-sm font-medium text-slate-700 dark:text-gray-200 truncate">{{ skill.name }}</span>
                        <span class="text-[10px] text-gray-500 truncate">{{ skill.category || 'Uncategorized' }}</span>
                    </div>
                </div>
                <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button @click.stop="deleteSkill(skill)" class="p-1 text-gray-400 hover:text-red-500 transition-opacity" title="Delete Skill">
                        <IconTrash class="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>