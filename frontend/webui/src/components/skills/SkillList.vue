<script setup>
import { computed, onMounted, ref } from 'vue';
import { useSkillsStore } from '../../stores/skills';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconShare from '../../assets/icons/IconShare.vue';
import DropdownMenu from '../ui/DropDownMenu/DropdownMenu.vue';


const props = defineProps({
    searchTerm: { type: String, default: '' }
});

const skillsStore = useSkillsStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

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
    // Open the editor modal to allow reading/updating without force-adding to context
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
            <div class="flex gap-3">
                <button @click="triggerImport" class="text-xs text-blue-500 hover:underline font-bold">Import</button>
                <button @click="skillsStore.fetchSkills()" class="text-xs text-gray-400 hover:text-blue-500" title="Refresh">
                    <IconSparkles class="w-3 h-3" :class="{'animate-spin': skillsStore.isLoading}" />
                </button>
            </div>
            <input type="file" ref="fileInput" @change="handleFileImport" class="hidden" accept=".xml,.md">
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
        <div v-else class="space-y-1 flex-1 overflow-y-auto custom-scrollbar pr-1">
                        <div v-for="skill in filteredSkills" :key="skill.id" 
                 class="group flex items-center gap-3 p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors mb-1"
                 @click="editSkill(skill)">
                
                <div class="flex items-center gap-2 min-w-0 flex-grow">
                    <div class="p-1.5 rounded bg-green-50 dark:bg-green-900/30 text-green-600 flex-shrink-0 border border-green-100 dark:border-green-800">
                        <IconSparkles class="w-3.5 h-3.5" />
                    </div>
                    <div class="flex flex-col min-w-0 leading-tight">
                        <span class="text-xs font-bold text-slate-700 dark:text-gray-200 truncate">{{ skill.name }}</span>
                        <span class="text-[9px] text-gray-500 truncate uppercase tracking-tighter">{{ skill.category || 'Uncategorized' }}</span>
                    </div>
                </div>

                <!-- Compact Menu at end of row -->
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
                            <IconUserCircle class="h-4 w-4 mr-2"/> Share with Friend
                        </button>
                        <button @click="uiStore.openModal('shareDiscussion', { title: skill.name, content: skill.content, isGroupShare: true })" class="menu-item">
                            <IconShare class="h-4 w-4 mr-2"/> Share with Group
                        </button>
                        <div class="menu-divider"></div>
                        <button @click="deleteSkill(skill)" class="menu-item text-red-500 font-bold">
                            <IconTrash class="w-4 h-4 mr-2"/> Remove
                        </button>
                    </DropdownMenu>
                </div>
            </div>
            <!-- Click-away overlay -->
            <div v-if="activeMenuId" class="fixed inset-0 z-10" @click="closeMenu"></div>
        </div>
    </div>
</template>