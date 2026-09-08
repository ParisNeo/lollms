<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import { useTasksStore } from '../../../stores/tasks';
import apiClient from '../../../services/api';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconFolder from '../../../assets/icons/IconFolder.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconBookOpen from '../../../assets/icons/IconBookOpen.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();

const {
    zooSkills, isLoadingZooSkills, skillFilters,
    skillZooRepositories, isLoadingSkillZooRepositories
} = storeToRefs(adminStore);

const isRepoFormVisible = ref(false);
const newRepoUrl = ref('');
const isPullingAll = ref(false);

const skillItems = computed(() => zooSkills.value.items || []);
const skillCategories = computed(() => zooSkills.value.categories || []);
const totalPages = computed(() => zooSkills.value.pages || 1);

async function loadData() {
    await Promise.all([
        adminStore.fetchZooSkills(true),
        adminStore.fetchSkillZooRepositories(true)
    ]);
}

onMounted(() => {
    loadData();
});

watch(skillFilters, () => {
    adminStore.fetchZooSkills(true);
}, { deep: true });

function handlePageChange(page) {
    skillFilters.currentPage = page;
}

async function installSkill(item) {
    const repo = item.repository || item.repository_url;
    if (!repo) {
        uiStore.addNotification('Missing repository information.', 'error');
        return;
    }
    try {
        await adminStore.installZooSkill({
            repository: repo,
            folder_name: item.folder_name,
            item_name: item.name
        });
    } catch (e) {
        console.error(e);
    }
}

async function showDocumentation(item) {
    try {
        const res = await apiClient.get('/api/skills_zoo/readme', {
            params: {
                repository: item.repository || item.repository_url,
                folder_name: item.folder_name
            }
        });
        uiStore.openModal('sourceViewer', {
            title: `Skill Documentation: ${item.name}`,
            content: res.data,
            language: 'markdown'
        });
    } catch (e) {
        uiStore.addNotification('Could not load documentation for this skill.', 'warning');
    }
}

async function showLicense(item) {
    try {
        const res = await apiClient.get('/api/skills_zoo/license', {
            params: {
                repository: item.repository || item.repository_url,
                folder_name: item.folder_name
            }
        });
        uiStore.openModal('sourceViewer', {
            title: `License: ${item.name}`,
            content: res.data,
            language: 'text'
        });
    } catch (e) {
        uiStore.addNotification('Could not load license text.', 'warning');
    }
}

async function handleAddRepo() {
    if (!newRepoUrl.value.trim()) return;
    try {
        await adminStore.addSkillZooRepository({ url: newRepoUrl.value.trim(), is_enabled: true });
        newRepoUrl.value = '';
        isRepoFormVisible.value = false;
        uiStore.addNotification('Repository added successfully.', 'success');
    } catch (e) {
        console.error(e);
    }
}

async function handleDeleteRepo(repo) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Remove Repository?',
        message: `Remove skills repository ${repo.url}?`,
        confirmText: 'Remove'
    });
    if (confirmed) {
        await adminStore.deleteSkillZooRepository(repo.id);
    }
}

async function handlePullRepo(repo) {
    try {
        await adminStore.pullSkillZooRepository(repo.id);
        uiStore.addNotification(`Pull started for ${repo.url}`, 'info');
    } catch (e) {
        console.error(e);
    }
}

async function handlePullAll() {
    isPullingAll.value = true;
    try {
        await adminStore.pullAllSkillZooRepositories();
        uiStore.addNotification('Refreshing all skill repositories...', 'info');
    } finally {
        isPullingAll.value = false;
    }
}
</script>

<template>
    <div class="space-y-6">
        <!-- Header -->
        <div class="flex justify-between items-center flex-wrap gap-4 bg-white/60 dark:bg-gray-850/50 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-700/60 backdrop-blur-md">
            <div>
                <h2 class="text-xl font-black tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
                    <IconSparkles class="w-6 h-6 text-teal-500" />
                    <span>Skills Zoo</span>
                    <span class="text-xs font-bold px-2.5 py-0.5 rounded-full bg-teal-50 text-teal-600 dark:bg-teal-900/40 dark:text-teal-300">
                        {{ zooSkills.total || 0 }} Skills
                    </span>
                </h2>
                <p class="text-xs text-gray-500 mt-0.5">Browse, install, and manage skills from remote repositories.</p>
            </div>

            <div class="flex items-center gap-2">
                <button @click="isRepoFormVisible = !isRepoFormVisible" class="btn btn-secondary btn-sm flex items-center gap-1.5">
                    <IconFolder class="w-3.5 h-3.5 text-blue-500" />
                    <span>Repositories</span>
                </button>
                <button @click="handlePullAll" class="btn btn-secondary btn-sm flex items-center gap-1.5" :disabled="isPullingAll">
                    <IconAnimateSpin v-if="isPullingAll" class="w-3.5 h-3.5 animate-spin" />
                    <IconRefresh v-else class="w-3.5 h-3.5 text-purple-500" />
                    <span>Pull All</span>
                </button>
            </div>
        </div>

        <!-- Repository Drawer -->
        <div v-if="isRepoFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-2xl p-5 border border-gray-100 dark:border-gray-700 space-y-4">
            <h3 class="text-sm font-bold uppercase tracking-widest text-gray-500">Skill Repositories</h3>
            <div class="flex gap-2">
                <input v-model="newRepoUrl" type="text" placeholder="https://github.com/user/repo" class="input-field grow text-xs" @keyup.enter="handleAddRepo" />
                <button @click="handleAddRepo" class="btn btn-primary btn-xs shrink-0">Add Repository</button>
            </div>
            <div class="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
                <div v-if="isLoadingSkillZooRepositories" class="text-center text-xs text-gray-500 py-4">Loading repositories...</div>
                <div v-else-if="skillZooRepositories.length === 0" class="text-center text-xs text-gray-400 py-4 border-2 border-dashed rounded-xl">No repositories configured.</div>
                <div v-for="repo in skillZooRepositories" :key="repo.id" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700 text-xs">
                    <span class="font-mono truncate pr-4">{{ repo.url }}</span>
                    <div class="flex items-center gap-2 shrink-0">
                        <button @click="handlePullRepo(repo)" class="p-1.5 rounded-lg text-blue-500 hover:bg-blue-50" title="Pull / Sync">
                            <IconRefresh class="w-3.5 h-3.5" />
                        </button>
                        <button @click="handleDeleteRepo(repo)" class="p-1.5 rounded-lg text-rose-500 hover:bg-rose-50" title="Remove">
                            <IconTrash class="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Filters -->
        <div class="flex flex-col lg:flex-row gap-3 bg-white dark:bg-gray-800 shadow-md rounded-2xl p-4 border border-gray-100 dark:border-gray-700">
            <input v-model="skillFilters.searchQuery" type="text" placeholder="Search skills..." class="input-field text-xs w-full lg:max-w-xs" />
            <select v-model="skillFilters.selectedCategory" class="input-field text-xs w-full lg:w-48">
                <option value="All">All Categories</option>
                <option v-for="cat in skillCategories" :key="cat" :value="cat">{{ cat }}</option>
            </select>
            <select v-model="skillFilters.installationStatusFilter" class="input-field text-xs w-full lg:w-48">
                <option value="All">All Statuses</option>
                <option value="installed">Installed</option>
                <option value="not_installed">Not Installed</option>
            </select>
            <select v-model="skillFilters.sortKey" class="input-field text-xs w-full lg:w-48">
                <option value="name">Sort: Name</option>
                <option value="last_update_date">Sort: Updated</option>
            </select>
        </div>

        <!-- Content: Enhanced Loading State with Informative Status -->
        <div v-if="isLoadingZooSkills || isPullingAll" class="text-center py-20 px-6 bg-white/40 dark:bg-gray-800/40 rounded-3xl border border-gray-200/70 dark:border-gray-700/60 backdrop-blur-sm space-y-4 max-w-lg mx-auto shadow-xs animate-in fade-in duration-300">
            <div class="relative w-14 h-14 mx-auto flex items-center justify-center">
                <div class="absolute inset-0 rounded-2xl bg-teal-500/10 dark:bg-teal-500/20 animate-ping opacity-40"></div>
                <div class="w-12 h-12 rounded-2xl bg-teal-50 dark:bg-teal-900/30 flex items-center justify-center text-teal-600 dark:text-teal-400 border border-teal-200/60 dark:border-teal-700/50 shadow-inner">
                    <IconAnimateSpin class="w-6 h-6 animate-spin" />
                </div>
            </div>

            <div class="space-y-1.5">
                <h3 class="text-base font-black text-gray-900 dark:text-white tracking-tight">
                    {{ isPullingAll ? 'Synchronizing Skills Repositories' : 'Loading Skills Catalog' }}
                </h3>
                <p class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed max-w-md mx-auto">
                    {{ isPullingAll 
                        ? 'Fetching latest updates from remote Git repositories, installing packages, and rebuilding the Zoo cache...' 
                        : 'Scanning skill definitions, parsing XML directives, and indexing categories from configured repositories...' }}
                </p>
            </div>

            <div class="pt-2 flex items-center justify-center gap-3">
                <div class="flex items-center gap-2 px-3 py-1 rounded-full bg-teal-50 dark:bg-teal-900/40 border border-teal-200 dark:border-teal-800">
                    <span class="inline-block w-2 h-2 rounded-full bg-teal-500 animate-pulse"></span>
                    <span class="text-[10px] font-bold uppercase tracking-widest text-teal-700 dark:text-teal-300">
                        {{ isPullingAll ? 'Git Pull in Progress' : 'Cache Indexing Active' }}
                    </span>
                </div>

                <button @click="loadData" class="btn btn-secondary btn-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-200" title="Force reload catalog">
                    <IconRefresh class="w-3 h-3 mr-1" />
                    <span>Refresh</span>
                </button>
            </div>
        </div>

        <div v-else-if="skillItems.length === 0" class="text-center py-16 bg-gray-50 dark:bg-gray-800/40 rounded-2xl border border-dashed dark:border-gray-700">
            <IconSparkles class="w-12 h-12 text-gray-400 mx-auto mb-3 opacity-40" />
            <p class="text-sm font-bold text-gray-700 dark:text-gray-300">No skills found in the Zoo</p>
            <p class="text-xs text-gray-500 mt-1">Try adjusting your filters or pull repositories.</p>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            <div v-for="item in skillItems" :key="item.id" class="bg-white dark:bg-gray-800 p-5 rounded-2xl shadow-xs hover:shadow-lg transition-all border border-gray-200/80 dark:border-gray-700/80 flex flex-col justify-between group">
                <div>
                    <div class="flex items-start justify-between gap-3 mb-3">
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="w-10 h-10 rounded-xl bg-teal-100/50 dark:bg-teal-900/40 flex items-center justify-center text-teal-600 shrink-0 overflow-hidden border border-teal-200 dark:border-teal-800">
                                <img v-if="item.icon" :src="item.icon" class="w-full h-full object-cover" />
                                <IconSparkles v-else class="w-5 h-5" />
                            </div>
                            <div class="min-w-0">
                                <h4 class="font-bold text-sm text-gray-900 dark:text-white truncate">{{ item.name }}</h4>
                                <p class="text-[10px] text-gray-500 font-mono truncate">{{ item.category || 'Generic' }}</p>
                            </div>
                        </div>
                        <span v-if="item.is_installed" class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                            Installed
                        </span>
                    </div>

                    <p class="text-xs text-gray-600 dark:text-gray-400 line-clamp-3 min-h-[3rem]">{{ item.description || 'No description provided.' }}</p>

                    <div class="mt-3 text-[10px] text-gray-500 dark:text-gray-400 space-y-1.5 font-mono">
                        <div class="flex justify-between items-center">
                            <span>Author:</span>
                            <span class="font-bold truncate max-w-[130px]">{{ item.author || 'Community' }}</span>
                        </div>
                        <div v-if="item.license" class="flex justify-between items-center">
                            <span>License:</span>
                            <button 
                                @click.stop="showLicense(item)" 
                                class="font-bold text-amber-600 dark:text-amber-400 hover:underline flex items-center gap-1 truncate max-w-[150px] cursor-pointer"
                                title="Click to inspect license"
                            >
                                <span>📜 {{ item.license }}</span>
                            </button>
                        </div>
                        <div class="flex justify-between items-center">
                            <span>Folder:</span>
                            <span class="truncate max-w-[140px] text-gray-400" :title="item.folder_name">{{ item.folder_name }}</span>
                        </div>
                    </div>
                </div>

                <div class="border-t dark:border-gray-700/60 pt-3 mt-4 flex justify-between items-center gap-2">
                    <div class="flex items-center gap-2">
                        <button v-if="!item.is_installed" @click="installSkill(item)" class="btn btn-primary btn-sm flex items-center gap-1.5">
                            <IconArrowDownTray class="w-3.5 h-3.5" />
                            <span>Install</span>
                        </button>
                        <div v-else class="flex items-center gap-1.5 text-emerald-600 text-xs font-bold">
                            <IconCheckCircle class="w-4 h-4" />
                            <span>Installed</span>
                        </div>

                        <button 
                            @click="showDocumentation(item)" 
                            class="p-1.5 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors"
                            title="View Documentation / Instructions"
                        >
                            <IconBookOpen class="w-3.5 h-3.5" />
                        </button>
                    </div>

                    <span class="text-[10px] text-gray-400 font-mono">v{{ item.version || '1.0' }}</span>
                </div>
            </div>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex justify-center items-center gap-2 pt-4">
            <button @click="handlePageChange(skillFilters.currentPage - 1)" :disabled="skillFilters.currentPage <= 1" class="btn btn-secondary btn-xs">Previous</button>
            <span class="text-xs text-gray-500">Page {{ skillFilters.currentPage }} of {{ totalPages }}</span>
            <button @click="handlePageChange(skillFilters.currentPage + 1)" :disabled="skillFilters.currentPage >= totalPages" class="btn btn-secondary btn-xs">Next</button>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>