<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useSkillsStore } from '../stores/skills';
import { useDiscussionsStore } from '../stores/discussions';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import CodeMirrorComponent from '../components/ui/CodeMirrorComponent/index.vue';

// Icons
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';

const route = useRoute();
const router = useRouter();
const skillsStore = useSkillsStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const { skills, isLoading } = storeToRefs(skillsStore);
const isAdmin = computed(() => authStore.isAdmin);

const selectedSkillId = ref(null);
const isSaving = ref(false);
const fileInput = ref(null);

const form = ref({
    name: '',
    category: 'Development',
    description: '',
    content: '',
    is_system: false,
    author: ''
});

const selectedSkill = computed(() => {
    if (!selectedSkillId.value) return null;
    return skills.value.find(s => s.id === selectedSkillId.value) || null;
});

function selectSkill(skill) {
    if (!skill) return;
    selectedSkillId.value = skill.id;
    form.value = {
        name: skill.name || '',
        category: skill.category || 'Development',
        description: skill.description || '',
        content: skill.content || '',
        is_system: Boolean(skill.is_system),
        author: skill.author || ''
    };
    router.replace({ query: { ...route.query, skillId: skill.id } });
}

function createNewSkill(asSystem = false) {
    selectedSkillId.value = null;
    form.value = {
        name: asSystem ? 'New System Skill' : 'New Skill',
        category: 'Development',
        description: 'Describe what this skill teaches the AI...',
        is_system: asSystem && isAdmin.value,
        author: asSystem ? 'System' : (authStore.user?.username || 'Personal'),
        content: `---\nname: New Skill\ndescription: Describe what this skill does here\n---\n\n# Instructions\n\nStep-by-step cognitive directives for the model go here...`
    };
}

async function saveSkill() {
    if (!form.value.name.trim()) {
        uiStore.addNotification('Skill name is required.', 'warning');
        return;
    }

    isSaving.value = true;
    try {
        const payload = {
            name: form.value.name,
            category: form.value.category,
            description: form.value.description,
            content: form.value.content,
            is_system: Boolean(form.value.is_system),
            author: form.value.author
        };

        if (selectedSkillId.value) {
            await skillsStore.updateSkill(selectedSkillId.value, payload);
            uiStore.addNotification('Skill updated successfully.', 'success');
        } else {
            const created = await skillsStore.createSkill(payload);
            if (created && created.id) selectedSkillId.value = created.id;
            uiStore.addNotification('Skill created successfully.', 'success');
        }
        await skillsStore.fetchSkills();
    } catch (e) {
        uiStore.addNotification('Failed to save skill.', 'error');
    } finally {
        isSaving.value = false;
    }
}

async function deleteCurrentSkill() {
    if (!selectedSkillId.value) return;
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Skill "${form.value.name}"?`,
        message: 'This skill will be removed from your active library.',
        confirmText: 'Delete'
    });
    if (confirmed?.confirmed || confirmed === true) {
        await skillsStore.deleteSkill(selectedSkillId.value);
        if (skills.value.length > 0) selectSkill(skills.value[0]);
        else createNewSkill();
    }
}

async function injectSkillToDiscussion() {
    if (!selectedSkill.value) return;
    try {
        await discussionsStore.addSkillAsArtefact(selectedSkill.value);
        uiStore.isDataZoneVisible = true;
        uiStore.addNotification(`Skill "${selectedSkill.value.name}" bound to active discussion!`, 'success');
    } catch (e) {
        uiStore.addNotification('Could not bind skill to active discussion.', 'error');
    }
}

function triggerImport() {
    fileInput.value?.click();
}

async function handleFileImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    try {
        const imported = await skillsStore.importSkill(file);
        if (imported) selectSkill(imported);
    } finally {
        event.target.value = '';
    }
}

async function handleExport(format) {
    if (!selectedSkillId.value) return;
    await skillsStore.exportSkill(selectedSkillId.value, format);
}

function handleExternalSelectEvent(event) {
    if (event.detail && event.detail.id) {
        const found = skills.value.find(s => String(s.id) === String(event.detail.id));
        if (found) selectSkill(found);
    }
}

onMounted(async () => {
    window.addEventListener('lollms:select-skill', handleExternalSelectEvent);
    if (skills.value.length === 0) {
        await skillsStore.fetchSkills();
    }
    const qId = route.query.skillId;
    if (qId) {
        const found = skills.value.find(s => String(s.id) === String(qId));
        if (found) selectSkill(found);
    } else if (skills.value.length > 0) {
        selectSkill(skills.value[0]);
    } else {
        createNewSkill();
    }
});

onUnmounted(() => {
    window.removeEventListener('lollms:select-skill', handleExternalSelectEvent);
});

watch(() => route.query.skillId, (newId) => {
    if (newId && String(newId) !== String(selectedSkillId.value)) {
        const found = skills.value.find(s => String(s.id) === String(newId));
        if (found) selectSkill(found);
    }
});
</script>

<template>
    <PageViewLayout title="Skills Studio" :title-icon="IconSparkles" :show-sidebar="false">
        <template #main>
            <div class="h-full flex flex-col overflow-hidden bg-bg-app">
                <input type="file" ref="fileInput" @change="handleFileImport" class="hidden" accept=".xml,.md">

                <!-- Header Toolbar -->
                <div class="shrink-0 px-6 py-3.5 border-b border-border-main bg-bg-card/70 backdrop-blur-sm flex items-center justify-between gap-4 flex-wrap">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-8 h-8 rounded-xl bg-teal-50 dark:bg-teal-900/30 text-teal-600 flex items-center justify-center shrink-0 border border-teal-200 dark:border-teal-800">
                            <IconSparkles class="w-4 h-4" />
                        </div>
                        <div class="flex items-center gap-2 min-w-0">
                            <input v-model="form.name" type="text" class="input-field text-sm font-bold w-52 sm:w-72" placeholder="Skill Name..." required />
                            <input v-model="form.category" type="text" class="input-field text-xs w-32 hidden sm:block" placeholder="Category" />

                            <!-- System Skill Indicator / Admin Toggle -->
                            <div v-if="isAdmin" class="flex items-center gap-1.5 px-2.5 py-1 rounded-xl border text-xs font-bold shrink-0 cursor-pointer"
                                 :class="form.is_system ? 'bg-indigo-50 border-indigo-200 text-indigo-700 dark:bg-indigo-950/40 dark:border-indigo-800 dark:text-indigo-300' : 'bg-gray-50 border-gray-200 text-gray-600 dark:bg-gray-800 dark:border-gray-700'"
                                 @click="form.is_system = !form.is_system"
                                 title="Toggle System Skill (Available to all users)">
                                <span>{{ form.is_system ? '🌐 System' : '👤 Personal' }}</span>
                            </div>
                            <span v-else-if="form.is_system" class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300 border border-indigo-200 shrink-0">
                                🌐 System Skill
                            </span>
                        </div>
                    </div>

                    <div class="flex items-center gap-2 shrink-0">
                        <button @click="createNewSkill(false)" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="New Personal Skill">
                            <IconPlus class="w-3.5 h-3.5" />
                            <span class="hidden md:inline">New</span>
                        </button>
                        <button v-if="isAdmin" @click="createNewSkill(true)" class="btn btn-secondary btn-sm flex items-center gap-1.5 border-indigo-300 text-indigo-600 dark:text-indigo-400" title="Create a System Skill manually">
                            <IconPlus class="w-3.5 h-3.5" />
                            <span class="hidden md:inline">+ System Skill</span>
                        </button>
                        <button @click="triggerImport" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Import skill">
                            <IconArrowDownTray class="w-3.5 h-3.5" />
                            <span class="hidden md:inline">Import</span>
                        </button>
                        <button v-if="selectedSkillId" @click="handleExport('xml')" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Export XML">
                            <IconArrowUpTray class="w-3.5 h-3.5 text-blue-500" />
                            <span class="hidden md:inline">Export XML</span>
                        </button>
                        <button v-if="selectedSkillId" @click="injectSkillToDiscussion" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Bind to active chat">
                            <IconSparkles class="w-3.5 h-3.5 text-teal-500" />
                            <span class="hidden md:inline">To Chat</span>
                        </button>
                        <button v-if="selectedSkillId" @click="deleteCurrentSkill" class="btn btn-secondary btn-sm text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30" title="Delete Skill">
                            <IconTrash class="w-3.5 h-3.5" />
                        </button>
                        <button @click="saveSkill" class="btn btn-primary btn-sm flex items-center gap-1.5 shadow-sm" :disabled="isSaving">
                            <IconAnimateSpin v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                            <IconCheckCircle v-else class="w-3.5 h-3.5" />
                            <span>{{ isSaving ? 'Saving...' : 'Save' }}</span>
                        </button>
                    </div>
                </div>

                <!-- Full Width Workspace (No duplicate list) -->
                <div class="grow flex flex-col overflow-hidden bg-bg-app p-4 sm:p-6 space-y-4">
                    <div class="shrink-0 bg-bg-card/50 p-3.5 rounded-2xl border border-border-main space-y-2">
                        <label class="block text-[10px] font-black uppercase tracking-wider text-text-dim">Behavioral Description</label>
                        <input v-model="form.description" type="text" class="input-field text-xs w-full" placeholder="Specify when and how the AI will trigger this capability..." />
                    </div>

                    <div class="grow overflow-hidden flex flex-col">
                        <div class="flex items-center justify-between pb-2 text-[10px] font-black uppercase tracking-widest text-text-dim">
                            <span>Directives, Schemas & XML Definitions</span>
                            <span class="text-teal-600 dark:text-teal-400 font-bold">CodeMirror Native XML / Python</span>
                        </div>
                        <CodeMirrorComponent 
                            v-model="form.content" 
                            language="xml"
                            class="h-full w-full rounded-2xl border border-border-main overflow-hidden shadow-xs"
                        />
                    </div>
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>