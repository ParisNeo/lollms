<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useSkillsStore } from '../../stores/skills';
import GenericModal from './GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

const uiStore = useUiStore();
const skillsStore = useSkillsStore();

const modalData = computed(() => uiStore.modalData('skillEditor'));
const skill = computed(() => modalData.value?.skill);

const name = ref('');
const description = ref('');
const category = ref('');
const language = ref('markdown');
const content = ref('');
const isLoading = ref(false);

function initForm() {
    if (skill.value && skill.value.id) {
        name.value = skill.value.name || '';
        description.value = skill.value.description || '';
        category.value = skill.value.category || '';
        language.value = skill.value.language || 'markdown';
        content.value = skill.value.content || '';
    } else {
        name.value = '';
        description.value = '';
        category.value = '';
        language.value = 'markdown';
        content.value = '';
    }
}

watch(() => uiStore.isModalOpen('skillEditor'), (isOpen) => {
    if (isOpen) {
        initForm();
    }
});

async function handleSave() {
    if (!name.value.trim()) {
        uiStore.addNotification('Name is required.', 'warning');
        return;
    }
    if (!content.value.trim()) {
        uiStore.addNotification('Content is required.', 'warning');
        return;
    }
    
    isLoading.value = true;
    try {
        const payload = {
            name: name.value.trim(),
            description: description.value.trim(),
            category: category.value.trim(),
            language: language.value.trim(),
            content: content.value
        };

        if (skill.value && skill.value.id) {
            await skillsStore.updateSkill(skill.value.id, payload);
        } else {
            await skillsStore.createSkill(payload);
        }
        uiStore.closeModal('skillEditor');
    } finally {
        isLoading.value = false;
    }
}

async function exportFormat(format) {
    if (skill.value && skill.value.id) {
        await skillsStore.exportSkill(skill.value.id, format);
    }
}
</script>

<template>
    <GenericModal modalName="skillEditor" :title="skill && skill.id ? 'Edit Skill' : 'New Skill'" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="space-y-4 h-[70vh] flex flex-col p-4">
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="col-span-2">
                        <label class="block text-sm font-medium mb-1">Name</label>
                        <input type="text" v-model="name" class="input-field w-full" placeholder="Skill Name">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-1">Category</label>
                        <input type="text" v-model="category" class="input-field w-full" placeholder="e.g. python/coding">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-1">Language</label>
                        <input type="text" v-model="language" class="input-field w-full" placeholder="markdown">
                    </div>
                    <div class="col-span-4">
                        <label class="block text-sm font-medium mb-1">Description</label>
                        <input type="text" v-model="description" class="input-field w-full" placeholder="Brief description of what this skill does">
                    </div>
                </div>
                <div class="flex-grow min-h-0 border rounded-md overflow-hidden dark:border-gray-700">
                     <CodeMirrorEditor v-model="content" class="h-full" :language="language === 'markdown' ? 'markdown' : 'plaintext'" />
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-between items-center w-full">
                <div class="flex gap-2">
                    <button v-if="skill && skill.id" @click="exportFormat('xml')" class="btn btn-secondary flex items-center gap-2" title="Export as XML">
                        <IconArrowDownTray class="w-4 h-4" /> XML
                    </button>
                    <button v-if="skill && skill.id" @click="exportFormat('claude')" class="btn btn-secondary flex items-center gap-2" title="Export as Claude Markdown">
                        <IconArrowDownTray class="w-4 h-4" /> Claude MD
                    </button>
                </div>
                <div class="flex gap-2">
                    <button @click="uiStore.closeModal('skillEditor')" class="btn btn-secondary">Cancel</button>
                    <button @click="handleSave" class="btn btn-primary" :disabled="isLoading">
                        {{ isLoading ? 'Saving...' : 'Save' }}
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>