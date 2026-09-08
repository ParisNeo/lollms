<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useSkillsStore } from '../../stores/skills';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconShare from '../../assets/icons/IconShare.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';


const props = defineProps({
    searchTerm: { type: String, default: '' }
});

const authStore = useAuthStore();
const skillsStore = useSkillsStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const isAdmin = computed(() => authStore.isAdmin);

const fileInput = ref(null);
const activeMenuId = ref(null);

function toggleMenu(event, skillId) {
    event.stopPropagation();
    activeMenuId.value = activeMenuId.value === skillId ? null : skillId;
}

function closeMenu() {
    activeMenuId.value = null;
}

onMounted(() => {
    skillsStore.fetchSkills();
});

const filteredSystemSkills = computed(() => {
    const list = skillsStore.systemSkills || [];
    if (!props.searchTerm) return list;
    const term = props.searchTerm.toLowerCase();
    return list.filter(s => s.name.toLowerCase().includes(term) || (s.description && s.description.toLowerCase().includes(term)) || (s.category && s.category.toLowerCase().includes(term)));
});

const filteredUserSkills = computed(() => {
    const list = skillsStore.userSkills || [];
    if (!props.searchTerm) return list;
    const term = props.searchTerm.toLowerCase();
    return list.filter(s => s.name.toLowerCase().includes(term) || (s.description && s.description.toLowerCase().includes(term)) || (s.category && s.category.toLowerCase().includes(term)));
});

import { useRouter } from 'vue-router';
const router = useRouter();

function editSkill(skill) {
    if (!skill) return;
    router.push({ path: '/skills-studio', query: { skillId: skill.id } });
    window.dispatchEvent(new CustomEvent('lollms:select-skill', { detail: { id: skill.id } }));
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

async function addToContext(skill) {
    // CRITICAL FIX: Stop using the old string injection logic.
    // Use the versioned artefact system instead.
    try {
        await discussionsStore.addSkillAsArtefact(skill);
        
        // Auto-open the Side Panel container if it's hidden
        if (!uiStore.isDataZoneVisible) {
            uiStore.isDataZoneVisible = true;
        }
        
        // Split view priority logic in ChatView.vue will now automatically
        // show the ArtefactSplitView because addSkillAsArtefact sets 
        // uiStore.activeSplitArtefactTitle.
    } catch (e) {
        console.error("Failed to add skill as artefact:", e);
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
            <div class="flex gap-3 items-center">
                <button @click="triggerImport" class="text-xs text-blue-500 hover:underline font-bold">Import</button>
                <button @click="skillsStore.fetchSkills()" class="text-xs text-gray-400 hover:text-blue-500 transition-colors" title="Refresh Skills">
                    <IconRefresh class="w-3.5 h-3.5" :class="{'animate-spin': skillsStore.isLoading}" />
                </button>
            </div>
            <input type="file" ref="fileInput" @change="handleFileImport" class="hidden" accept=".xml,.md">
        </div>

        <div v-if="skillsStore.isLoading" class="text-center p-4 text-gray-500">Loading skills...</div>
        <div v-else-if="filteredSystemSkills.length === 0 && filteredUserSkills.length === 0" class="empty-state-flat">
            <p class="text-base font-medium text-slate-600 dark:text-gray-300 mb-2">
                 {{ searchTerm ? 'No matches found' : 'No skills yet' }}
            </p>
             <p class="text-sm text-slate-500 dark:text-gray-400">
                Create a skill or install one from the Skills Zoo.
            </p>
        </div>
        <div v-else class="space-y-4 flex-1 overflow-y-auto custom-scrollbar pr-1">

            <!-- 🌐 SECTION 1: SYSTEM SKILLS -->
            <div v-if="filteredSystemSkills.length > 0">
                <div class="flex items-center justify-between px-2 py-1 mb-1">
                    <span class="text-[10px] font-black uppercase tracking-wider text-indigo-600 dark:text-indigo-400 flex items-center gap-1.5">
                        <span>🌐 System Skills</span>
                        <span class="px-1.5 py-0.2 rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-[9px] font-bold">{{ filteredSystemSkills.length }}</span>
                    </span>
                </div>

                <div class="space-y-1">
                    <div v-for="skill in filteredSystemSkills" :key="skill.id" 
                         class="group flex items-center gap-3 p-1.5 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
                         @click="editSkill(skill)">

                        <div class="flex items-center gap-2 min-w-0 grow">
                            <div class="w-7 h-7 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 shrink-0 border border-indigo-100 dark:border-indigo-800 flex items-center justify-center overflow-hidden">
                                <IconSparkles class="w-3.5 h-3.5" />
                            </div>
                            <div class="flex flex-col min-w-0 leading-tight">
                                <span class="text-xs font-bold text-slate-700 dark:text-gray-200 truncate">{{ skill.name }}</span>
                                <span class="text-[9px] text-gray-500 truncate uppercase tracking-tighter">{{ skill.category || 'System' }}</span>
                            </div>
                        </div>

                        <div @click.stop class="opacity-0 group-hover:opacity-100 transition-opacity">
                            <DropdownMenu title="Options" buttonClass="p-1 text-gray-400 hover:text-gray-600">
                                <template #icon>
                                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                                    <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
                                    </svg>
                                </template>
                                <button @click="addToContext(skill)" class="menu-item text-blue-600">
                                    <IconArrowUpTray class="w-4 h-4 mr-2"/> Add to Discussion
                                </button>
                                <button @click="uiStore.openModal('shareDiscussion', { title: skill.name, content: skill.content })" class="menu-item">
                                    <IconUserCircle class="w-4 h-4 mr-2"/> Share with Friend
                                </button>
                                <div class="menu-divider"></div>
                                <button v-if="isAdmin" @click="deleteSkill(skill)" class="menu-item text-red-500 font-bold">
                                    <IconTrash class="w-4 h-4 mr-2"/> Remove
                                </button>
                            </DropdownMenu>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 👤 SECTION 2: MY SKILLS (PERSONAL) -->
            <div v-if="filteredUserSkills.length > 0 || filteredSystemSkills.length === 0">
                <div class="flex items-center justify-between px-2 py-1 mb-1">
                    <span class="text-[10px] font-black uppercase tracking-wider text-teal-600 dark:text-teal-400 flex items-center gap-1.5">
                        <span>👤 My Skills</span>
                        <span class="px-1.5 py-0.2 rounded-full bg-teal-100 dark:bg-teal-900/40 text-[9px] font-bold">{{ filteredUserSkills.length }}</span>
                    </span>
                </div>

                <div class="space-y-1">
                    <div v-for="skill in filteredUserSkills" :key="skill.id" 
                         class="group flex items-center gap-3 p-1.5 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
                         @click="editSkill(skill)">

                        <div class="flex items-center gap-2 min-w-0 grow">
                            <div class="w-7 h-7 rounded-lg bg-teal-50 dark:bg-teal-900/30 text-teal-600 dark:text-teal-400 shrink-0 border border-teal-100 dark:border-teal-800 flex items-center justify-center overflow-hidden">
                                <IconSparkles class="w-3.5 h-3.5" />
                            </div>
                            <div class="flex flex-col min-w-0 leading-tight">
                                <span class="text-xs font-bold text-slate-700 dark:text-gray-200 truncate">{{ skill.name }}</span>
                                <span class="text-[9px] text-gray-500 truncate uppercase tracking-tighter">{{ skill.category || 'Personal' }}</span>
                            </div>
                        </div>

                        <div @click.stop class="opacity-0 group-hover:opacity-100 transition-opacity">
                            <DropdownMenu title="Options" buttonClass="p-1 text-gray-400 hover:text-gray-600">
                                <template #icon>
                                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                                    <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
                                    </svg>
                                </template>
                                <button @click="addToContext(skill)" class="menu-item text-blue-600">
                                    <IconArrowUpTray class="w-4 h-4 mr-2"/> Add to Discussion
                                </button>
                                <button @click="uiStore.openModal('shareDiscussion', { title: skill.name, content: skill.content })" class="menu-item">
                                    <IconUserCircle class="w-4 h-4 mr-2"/> Share with Friend
                                </button>
                                <div class="menu-divider"></div>
                                <button @click="deleteSkill(skill)" class="menu-item text-red-500 font-bold">
                                    <IconTrash class="w-4 h-4 mr-2"/> Remove
                                </button>
                            </DropdownMenu>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
.menu-divider { @apply my-1 border-t border-gray-100 dark:border-gray-700; }
</style>