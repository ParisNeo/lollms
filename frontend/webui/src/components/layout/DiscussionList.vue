<script setup>
import { computed, ref, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router'; 
import { useDiscussionsStore } from '../../stores/discussions';
import { useNotesStore } from '../../stores/notes';
import { useNotebookStore } from '../../stores/notebooks'; 
import { useDataStore } from '../../stores/data'; 
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { useImageStore } from '../../stores/images';
import { useFlowStore } from '../../stores/flow';
import { useSocialStore } from '../../stores/social';
import apiClient from '../../services/api';
import { storeToRefs } from 'pinia';
import DiscussionItem from './DiscussionItem.vue';
import DiscussionGroupItem from './DiscussionGroupItem.vue';
import NoteList from '../notes/NoteList.vue';
import SkillList from '../skills/SkillList.vue';
import ArtefactGlobalList from './ArtefactGlobalList.vue';
import AlbumList from '../images/AlbumList.vue';
import DataStoreItem from '../datastores/DataStoreItem.vue';

import logoDefault from '../../assets/logo.png';
import IconHome from '../../assets/icons/IconHome.vue';
import IconAdjustmentsHorizontal from '../../assets/icons/IconAdjustmentsHorizontal.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconScissors from '../../assets/icons/IconScissors.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconGitBranch from '../../assets/icons/ui/IconGitBranch.vue'; 
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconMenu from '../../assets/icons/IconMenu.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconMessage from '../../assets/icons/IconMessage.vue'; 
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconServer from '../../assets/icons/IconServer.vue'; 
import IconDatabase from '../../assets/icons/IconDatabase.vue'; 
import IconTrash from '../../assets/icons/IconTrash.vue'; 
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconUser from '../../assets/icons/IconUser.vue';
import IconShare from '../../assets/icons/IconShare.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconArrowsUpDown from '../../assets/icons/IconArrowsUpDown.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';

const store = useDiscussionsStore();
const notesStore = useNotesStore();
const notebookStore = useNotebookStore();
const dataStore = useDataStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const imageStore = useImageStore();
const flowStore = useFlowStore();
const socialStore = useSocialStore();
const router = useRouter();
const route = useRoute();

const { user } = storeToRefs(authStore);
const { isLoadingDiscussions, discussionGroupsTree, sharedWithMe, sortedDiscussions } = storeToRefs(store);
const { notebooks } = storeToRefs(notebookStore);
const { ownedDataStores, sharedDataStores, availableVectorizers, userPersonalities, publicPersonalities } = storeToRefs(dataStore);
const { friends, socialGroups } = storeToRefs(socialStore);
const hasActiveVectorizers = computed(() => Array.isArray(availableVectorizers.value) && availableVectorizers.value.length > 0);
const { flows } = storeToRefs(flowStore);

const newsArticles = ref([]);
const isLoadingNews = ref(false);

async function fetchNewsArticlesList() {
    isLoadingNews.value = true;
    try {
        const response = await apiClient.get('/api/news');
        newsArticles.value = Array.isArray(response.data) ? response.data : [];
    } catch (e) {
        newsArticles.value = [];
    } finally {
        isLoadingNews.value = false;
    }
}

const activeDiscussion = computed(() => store.activeDiscussion);
const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);
const welcomeText = computed(() => authStore.welcomeText || 'LoLLMs');
const welcomeSlogan = computed(() => authStore.welcomeSlogan || 'One tool to rule them all');

const activeTab = ref('chat'); // 'chat', 'notes', 'skills', 'artefacts', 'notebooks', 'data', 'images', 'flows'
const searchTerm = ref('');
const isSearchVisible = ref(false);
const isSharedVisible = ref(false);
const showToolbox = ref(false);
const isUngroupedVisible = ref(true);
const isFoldersVisible = ref(true);
const isStarredVisible = ref(false);
const isRootDragOver = ref(false);

const isUploadingArtefact = ref(false);
const isRefreshingTab = ref(false);
const uploadingMessage = ref('Processing files...');
const artefactFileInput = ref(null);
const bundleFileInput = ref(null);
const currentUploadPdfMode = ref('text_images');

async function handleRefresh() {
    isRefreshingTab.value = true;
    try {
        switch (activeTab.value) {
            case 'chat':
                await Promise.allSettled([
                    store.fetchDiscussions(),
                    store.fetchDiscussionGroups()
                ]);
                uiStore.addNotification('Discussions refreshed.', 'success');
                break;
            case 'notes':
                await notesStore.fetchNotes();
                uiStore.addNotification('Notes refreshed.', 'success');
                break;
            case 'skills':
                uiStore.addNotification('Skills refreshed.', 'success');
                break;
            case 'artefacts':
                if (store.currentDiscussionId) {
                    await store.fetchArtefacts(store.currentDiscussionId);
                }
                uiStore.addNotification('Artefacts refreshed.', 'success');
                break;
            case 'news':
                await fetchNewsArticlesList();
                uiStore.addNotification('News articles refreshed.', 'success');
                break;
            case 'feed':
                await Promise.allSettled([
                    socialStore.fetchFeed(),
                    socialStore.fetchFriends(),
                    socialStore.fetchSocialGroups()
                ]);
                uiStore.addNotification('Feed & Social channels refreshed.', 'success');
                break;
            case 'personalities':
                await dataStore.fetchPersonalities();
                uiStore.addNotification('Personalities refreshed.', 'success');
                break;
            case 'images':
                await Promise.allSettled([
                    imageStore.fetchAlbums(),
                    imageStore.fetchImages()
                ]);
                uiStore.addNotification('Image albums refreshed.', 'success');
                break;
            case 'notebooks':
                await notebookStore.fetchNotebooks();
                uiStore.addNotification('Notebooks refreshed.', 'success');
                break;
            case 'data':
                await dataStore.fetchDataStores();
                uiStore.addNotification('Data stores refreshed.', 'success');
                break;
            case 'flows':
                await flowStore.fetchFlows();
                uiStore.addNotification('Workflows refreshed.', 'success');
                break;
            default:
                await store.fetchDiscussions();
                break;
        }
    } catch (e) {
        console.error("Refresh failed:", e);
        uiStore.addNotification('Failed to refresh list.', 'error');
    } finally {
        isRefreshingTab.value = false;
    }
}

function triggerArtefactFileUpload(mode = 'text_images') { 
    currentUploadPdfMode.value = mode;
    artefactFileInput.value?.click(); 
}

function triggerBundleImport() {
    bundleFileInput.value?.click();
}

async function handleBundleImport(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!store.currentDiscussionId) {
        try {
            await store.createNewDiscussion();
        } catch (e) {
            uiStore.addNotification('Could not start a conversation to host the imported bundle.', 'error');
            return;
        }
    }

    const idToUse = store.currentDiscussionId;
    try {
        const text = await file.text();
        const bundle = JSON.parse(text);
        if (!bundle.main_artefact) {
            uiStore.addNotification('Invalid bundle file. Main artefact is missing.', 'error');
            return;
        }
        isUploadingArtefact.value = true;
        uploadingMessage.value = 'Importing complete artefact bundle...';
        await store.importArtefactBundle({
            discussionId: idToUse,
            bundle
        });
        uiStore.addNotification('Bundle imported successfully!', 'success');
    } catch (e) {
        console.error("Bundle import failed:", e);
        uiStore.addNotification('Failed to parse or import the bundle.', 'error');
    } finally {
        isUploadingArtefact.value = false;
        if (bundleFileInput.value) bundleFileInput.value.value = '';
    }
}

async function handleCreateArtefact() {
    if (activeTab.value === 'artefacts') {
        uiStore.openModal('createArtefact', { isLibraryOnly: true });
        return;
    }
    if (!store.currentDiscussionId) {
        try {
            await store.createNewDiscussion();
        } catch (e) {
            uiStore.addNotification('Could not start a conversation to host the new document.', 'error');
            return;
        }
    }
    const idToUse = store.currentDiscussionId;
    if (idToUse) uiStore.openModal('createArtefact', { discussionId: idToUse });
}

async function handleArtefactFileUpload(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;

    if (!store.currentDiscussionId) {
        try {
            await store.createNewDiscussion();
        } catch (e) {
            uiStore.addNotification('Could not start a conversation to host the imported document.', 'error');
            return;
        }
    }

    const idToUse = store.currentDiscussionId;
    isUploadingArtefact.value = true;
    uploadingMessage.value = 'Uploading and analyzing files...';

    const installHintTimer = setTimeout(() => {
        uploadingMessage.value = 'Preparing environment (this might involve installing required libraries)...';
    }, 5000);

    try {
        await Promise.all(files.map(file => store.addArtefact({ discussionId: idToUse, file, extractImages: true, auto_load: true, pdfMode: currentUploadPdfMode.value })));
        await store.fetchArtefacts(idToUse);
        await store.fetchContextStatus(idToUse);
    } finally {
        clearTimeout(installHintTimer);
        isUploadingArtefact.value = false;
        if (artefactFileInput.value) artefactFileInput.value.value = '';
    }
}

onMounted(() => {
    if (notesStore.notes.length === 0) notesStore.fetchNotes();
    if (notebookStore.notebooks.length === 0) notebookStore.fetchNotebooks();
    if (dataStore.ownedDataStores.length === 0) dataStore.fetchDataStores();
    if (dataStore.userPersonalities.length === 0 && dataStore.publicPersonalities.length === 0) dataStore.fetchPersonalities();
    if (imageStore.albums.length === 0) imageStore.fetchAlbums();
    imageStore.fetchImages();
    if (flowStore.flows.length === 0) flowStore.fetchFlows();
    if (socialStore.friends.length === 0) socialStore.fetchFriends();
    if (socialStore.socialGroups.length === 0) socialStore.fetchSocialGroups();
    fetchNewsArticlesList();
});

function handleTabClick(tab) {
    activeTab.value = tab;
    if (tab === 'feed') {
        uiStore.setMainView('feed');
        if (route.path !== '/') {
            router.push('/');
        }
    } else if (tab === 'news') {
        if (!route.path.startsWith('/news')) {
            router.push('/news');
        }
    } else if (tab === 'chat' || tab === 'notes' || tab === 'skills' || tab === 'artefacts') {
        if (route.path !== '/') {
            router.push('/');
        }
        uiStore.setMainView('chat');
    } else if (tab === 'personalities') {
        if (!route.path.startsWith('/personality-studio')) {
            router.push('/personality-studio');
        }
    } else if (tab === 'notebooks') {
        if (!route.path.startsWith('/notebooks') && !route.path.startsWith('/notebook-studio')) {
            router.push('/notebooks');
        }
    } else if (tab === 'data') {
        if (!route.path.startsWith('/datastores')) {
            router.push('/datastores');
        }
    } else if (tab === 'flows') {
        if (!route.path.startsWith('/flow-studio')) {
            router.push('/flow-studio');
        }
    } else if (tab === 'images') {
        if (!route.path.startsWith('/image-studio')) {
            router.push('/image-studio');
        }
        imageStore.fetchAlbums();
        imageStore.fetchImages();
    }
}

// Watch route changes to automatically select the correct tab
watch(() => route.path, (path) => {
    if (path.startsWith('/profile')) {
        activeTab.value = 'feed';
    } else if (path.startsWith('/news')) {
        activeTab.value = 'news';
    } else if (path.startsWith('/personality-studio')) {
        activeTab.value = 'personalities';
    } else if (path.startsWith('/flow-studio')) {
        activeTab.value = 'flows';
    } else if (path.startsWith('/notebooks') || path.startsWith('/notebook-studio')) {
        activeTab.value = 'notebooks';
    } else if (path.startsWith('/datastores')) {
        activeTab.value = 'data';
    } else if (path.startsWith('/image-studio')) {
        activeTab.value = 'images';
    } else if (path === '/' || path.startsWith('/chat')) {
        activeTab.value = uiStore.mainView === 'feed' ? 'feed' : 'chat';
    }
}, { immediate: true });

watch(() => uiStore.mainView, (view) => {
    if (route.path === '/') {
        activeTab.value = view === 'feed' ? 'feed' : 'chat';
    }
});

const filteredUserPersonalities = computed(() => {
    const list = Array.isArray(userPersonalities.value) ? userPersonalities.value : [];
    if (!searchTerm.value) return list;
    const q = searchTerm.value.toLowerCase();
    return list.filter(p => (p.name || '').toLowerCase().includes(q) || (p.category || '').toLowerCase().includes(q) || (p.description || '').toLowerCase().includes(q));
});

const filteredPublicPersonalities = computed(() => {
    const list = Array.isArray(publicPersonalities.value) ? publicPersonalities.value : [];
    if (!searchTerm.value) return list;
    const q = searchTerm.value.toLowerCase();
    return list.filter(p => (p.name || '').toLowerCase().includes(q) || (p.category || '').toLowerCase().includes(q) || (p.description || '').toLowerCase().includes(q));
});

async function handleSelectPersonality(personality) {
    if (!personality) return;
    await authStore.updateUserPreferences({ active_personality_id: personality.id });
    if (!route.path.startsWith('/personality-studio')) {
        router.push('/personality-studio');
    }
    if (window.innerWidth < 768) uiStore.closeSidebar();
}

function handleEditPersonality(personality) {
    uiStore.openModal('personalityEditor', { personality });
}

const filteredNewsArticles = computed(() => {
    const list = Array.isArray(newsArticles.value) ? newsArticles.value : [];
    if (!searchTerm.value) return list;
    const q = searchTerm.value.toLowerCase();
    return list.filter(a => (a.title || '').toLowerCase().includes(q) || (a.content || '').toLowerCase().includes(q));
});

function handleSelectNewsArticle(article) {
    if (route.path !== '/news') {
        router.push('/news');
    }
    setTimeout(() => {
        window.dispatchEvent(new CustomEvent('lollms:select-news-article', { detail: { id: article.id } }));
    }, 100);
    if (window.innerWidth < 768) uiStore.closeSidebar();
}

const filteredFriends = computed(() => {
    const list = Array.isArray(friends.value) ? friends.value : [];
    if (!searchTerm.value) return list;
    const q = searchTerm.value.toLowerCase();
    return list.filter(f => (f.username || '').toLowerCase().includes(q) || (f.first_name || '').toLowerCase().includes(q) || (f.family_name || '').toLowerCase().includes(q));
});

const filteredSocialGroups = computed(() => {
    const list = Array.isArray(socialGroups.value) ? socialGroups.value : [];
    if (!searchTerm.value) return list;
    const q = searchTerm.value.toLowerCase();
    return list.filter(g => (g.displayName || g.display_name || g.name || '').toLowerCase().includes(q));
});

function selectGeneralFeed() {
    uiStore.setMainView('feed');
    if (route.path !== '/') router.push('/');
    if (window.innerWidth < 768) uiStore.closeSidebar();
}

function selectFriendFeed(friend) {
    router.push(`/profile/${friend.username}`);
    if (window.innerWidth < 768) uiStore.closeSidebar();
}

function selectGroupFeed(group) {
    socialStore.fetchSocialGroupFeed(group.id);
    uiStore.setMainView('feed');
    if (route.path !== '/') router.push('/');
    if (window.innerWidth < 768) uiStore.closeSidebar();
}

const filteredSharedDiscussions = computed(() => {
    if (!searchTerm.value) return sharedWithMe.value;
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return sharedWithMe.value.filter(d => d.title.toLowerCase().includes(lowerCaseSearch));
});

const filteredDiscussionTree = computed(() => {
    if (!searchTerm.value) return discussionGroupsTree.value;
    const lowerCaseSearch = searchTerm.value.toLowerCase();

    const filterDiscussions = (discussions) => discussions.filter(d => d.title.toLowerCase().includes(lowerCaseSearch));

    const filterGroups = (groups) => {
        return groups.map(group => {
            const filteredChildren = filterGroups(group.children || []);
            const filteredDiscussionsInGroup = filterDiscussions(group.discussions || []);
            if (group.name.toLowerCase().includes(lowerCaseSearch) || filteredChildren.length > 0 || filteredDiscussionsInGroup.length > 0) {
                if (group.name.toLowerCase().includes(lowerCaseSearch)) {
                    return group; 
                }
                return { ...group, children: filteredChildren, discussions: filteredDiscussionsInGroup };
            }
            return null;
        }).filter(Boolean);
    };

    return {
        starred: filterDiscussions(discussionGroupsTree.value.starred || []),
        groups: filterGroups(discussionGroupsTree.value.groups || []),
        ungrouped: filterDiscussions(discussionGroupsTree.value.ungrouped || [])
    };
});

const filteredNotebooks = computed(() => {
    const list = Array.isArray(notebooks.value) ? notebooks.value : [];
    if (!searchTerm.value) return list;
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return list.filter(n => (n.title || '').toLowerCase().includes(lowerCaseSearch));
});

// Data Store Filtering
const filteredOwnedStores = computed(() => {
    if (!searchTerm.value) return ownedDataStores.value;
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return ownedDataStores.value.filter(s => s.name.toLowerCase().includes(lowerCaseSearch));
});

const filteredSharedStores = computed(() => {
    if (!searchTerm.value) return sharedDataStores.value;
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return sharedDataStores.value.filter(s => s.name.toLowerCase().includes(lowerCaseSearch));
});

const filteredFlows = computed(() => {
    if (!searchTerm.value) return flows.value;
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return flows.value.filter(f => f.name.toLowerCase().includes(lowerCaseSearch));
});

function handleNewGroup() {
    if (activeTab.value === 'chat') {
        uiStore.openModal('discussionGroup', { parentGroup: null });
    } else if (activeTab.value === 'notes') {
        uiStore.openModal('noteGroup', { parentGroup: null });
    }
}

async function goToFeed() { 
    uiStore.setMainView('feed'); 
    if (route.path !== '/') {
        await router.push('/');
    }
}

async function handleRootDrop(event) {
    isRootDragOver.value = false;
    const data = event.dataTransfer.getData('application/lollms-item');
    if (!data) return;
    try {
        const { type, id } = JSON.parse(data);
        if (activeTab.value === 'chat') {
             if (type === 'group') {
                const group = store.discussionGroups.find(g => g.id === id);
                if (group && group.parent_id !== null) await store.updateGroup(id, group.name, null);
            } else if (type === 'discussion') {
                const discussion = store.discussions[id];
                if(discussion && discussion.group_id !== null) await store.moveDiscussionToGroup(id, null);
            }
        } else if (activeTab.value === 'notes') {
            if (type === 'noteGroup') {
                 const group = notesStore.groups.find(g => g.id === id);
                 if (group && group.parent_id !== null) await notesStore.updateGroup(id, group.name, null);
            } else if (type === 'note') {
                 const note = notesStore.notes.find(n => n.id === id);
                 if (note && note.group_id !== null) await notesStore.updateNote(id, { group_id: null });
            }
        }
    } catch (e) { console.error("Root drop failed:", e); }
}

async function handleNewItem() { 
    if (route.path.startsWith('/personality-studio')) {
        uiStore.openModal('personalityEditor', { 
            personality: { id: null, name: '', category: '', description: '', prompt_text: '', is_public: false, icon_base64: null } 
        });
        if (window.innerWidth < 768) uiStore.closeSidebar();
        return;
    }
    if (activeTab.value === 'chat') {
        store.createNewDiscussion(store.currentGroupId); 
        if (window.innerWidth < 768) uiStore.closeSidebar();
    } else if (activeTab.value === 'artefacts') {
        // [FIX] Open Create Artefact modal when on the Files/Artefacts tab
        uiStore.openModal('createArtefact', { isLibraryOnly: true });
        if (window.innerWidth < 768) uiStore.closeSidebar();
    } else if (activeTab.value === 'notes') {
        uiStore.openModal('noteEditor');
        if (window.innerWidth < 768) uiStore.closeSidebar();
    } else if (activeTab.value === 'skills') {
        uiStore.openModal('skillEditor');
        if (window.innerWidth < 768) uiStore.closeSidebar();
    } else if (activeTab.value === 'notebooks') {
        uiStore.openModal('notebookWizard');
    } else if (activeTab.value === 'data') {
        await router.push('/datastores');
        setTimeout(() => {
            const event = new CustomEvent('lollms:open-new-datastore');
            window.dispatchEvent(event);
        }, 100);
        if (window.innerWidth < 768) uiStore.closeSidebar();
    } else if (activeTab.value === 'images') {
        const { confirmed, value } = await uiStore.showConfirmation({
            title: 'New Album',
            message: 'Enter a name for your new album:',
            confirmText: 'Create',
            inputType: 'text',
            inputPlaceholder: 'Album Name'
        });
        if (confirmed && value) {
            await imageStore.createAlbum(value);
        }
    } else if (activeTab.value === 'flows') {
        uiStore.openModal('flowWizard');
    }
}

async function openNotebook(notebook) {
    await notebookStore.selectNotebook(notebook.id);
    router.push('/notebooks');
    if (window.innerWidth < 768) uiStore.closeSidebar();
}

// Data Store Handlers
function handleDataStoreSelect(store) {
    router.push({ path: '/datastores', query: { storeId: store.id } });
    if (window.innerWidth < 768) uiStore.closeSidebar();
}

function onEditStore(store) { uiStore.openModal('editDataStore', { store }); }
async function onDeleteStore(store) {
    const { confirmed } = await uiStore.showConfirmation({ title: `Delete Data Store '${store.name}'?`, message: 'This will permanently delete the data store and all its indexed documents.', confirmText: 'Delete' });
    if (confirmed) {
        await dataStore.deleteDataStore(store.id);
        // Clear selection if deleted store was selected
        if (route.query.storeId === store.id) {
            router.push('/datastores');
        }
    }
}
function onShareStore(store) { uiStore.openModal('shareDataStore', { store }); }
async function onLeaveStore(store) {
    const { confirmed } = await uiStore.showConfirmation({ title: `Leave '${store.name}'?`, message: 'You will lose access to this shared Data Store.', confirmText: 'Leave' });
    if (confirmed) {
        await dataStore.leaveDataStore(store.id);
        if (route.query.storeId === store.id) {
            router.push('/datastores');
        }
    }
}

async function openFlow(flow) {
    flowStore.currentFlow = flow;
    router.push('/flow-studio');
    if (window.innerWidth < 768) uiStore.closeSidebar();
}

async function handleDeleteNotebook(notebook) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Notebook "${notebook.title}"?`,
        message: 'This will permanently delete this notebook.',
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        await notebookStore.deleteNotebook(notebook.id);
    }
}

async function handleDeleteFlow(flow) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Flow "${flow.name}"?`,
        message: 'This will permanently delete this workflow.',
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        await flowStore.deleteFlow(flow.id);
    }
}

function handleSelectUngrouped() {
    store.currentGroupId = null;
    isUngroupedVisible.value = !isUngroupedVisible.value;
}

function handleImportClick() { uiStore.openModal('import'); }
function handleExportClick() { uiStore.openModal('export', { allDiscussions: store.sortedDiscussions }); }
function handlePrune() { store.pruneDiscussions(); }
function handleShowTree() { if (activeDiscussion.value) uiStore.openModal('discussionTree', { discussionId: activeDiscussion.value.id }); else uiStore.addNotification('Please select a discussion first.', 'warning'); }
function handleClone() { if (activeDiscussion.value) store.cloneDiscussion(activeDiscussion.value.id); else uiStore.addNotification('Please select a discussion to clone.', 'warning'); }
function handleCopyDiscussionMarkdown() {
    if (activeDiscussion.value) {
        store.copyDiscussionAsMarkdown(activeDiscussion.value.id);
    }
}
</script>

<template>
    <div 
      class="h-full flex flex-col bg-white dark:bg-gray-900 w-full shrink-0"
      @dragover.prevent="isRootDragOver = true"
      @dragleave="isRootDragOver = false"
      @drop.prevent="handleRootDrop"
      :class="{'bg-blue-50 dark:bg-blue-900/20': isRootDragOver}"
    >
        <input type="file" ref="artefactFileInput" @change="handleArtefactFileUpload" multiple class="hidden">
        <input type="file" ref="bundleFileInput" @change="handleBundleImport" accept=".json" class="hidden">

        <div class="p-4 border-b border-slate-200 dark:border-gray-700 shrink-0 space-y-3">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3 min-w-0 grow">
                    <button @click="uiStore.toggleSidebar" class="p-1 rounded text-slate-500 dark:text-gray-400 hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors md:hidden" title="Toggle Menu">
                        <IconMenu class="w-5 h-5" />
                    </button>
                    <img :src="logoSrc" alt="LoLLMs Logo" class="h-8 w-8 shrink-0 object-contain rounded-md transition-transform group-hover:scale-110" @error="($event.target.src=logoDefault)">
                    <div class="min-w-0 grow">
                        <h1 class="text-base font-semibold text-slate-900 dark:text-gray-100 truncate" :title="welcomeText">{{ welcomeText }}</h1>
                        <p class="text-xs text-slate-500 dark:text-gray-400 truncate" :title="welcomeSlogan">{{ welcomeSlogan }}</p>
                    </div>
                </div>
                <div class="flex items-center gap-1 shrink-0">
                    <button 
                        @click="uiStore.toggleSidebarPin" 
                        class="btn-icon-flat hidden md:inline-flex" 
                        :class="{'!text-blue-600 !bg-blue-50 dark:!bg-blue-900/30': uiStore.isSidebarPinned}"
                        :title="uiStore.isSidebarPinned ? 'Sidebar pinned: Auto-collapse disabled' : 'Pin sidebar: Keep open permanently'"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 transition-transform duration-200" :class="{'rotate-45 opacity-60': !uiStore.isSidebarPinned}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="12" y1="17" x2="12" y2="22"></line>
                            <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"></path>
                        </svg>
                    </button>
                    <button @click="uiStore.toggleSidebar" class="btn-icon-flat hidden md:inline-flex" title="Collapse sidebar">
                        <IconArrowLeft class="h-5 h-5" />
                    </button>
                </div>
            </div>

                        <!-- Tab Switcher -->
            <div class="flex space-x-1 bg-slate-100 dark:bg-gray-800 p-1 rounded-lg overflow-x-auto custom-scrollbar pb-1">
                <button 
                    @click="handleTabClick('chat')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'chat' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Chats"
                >
                    <IconMessage class="w-3.5 h-3.5 mb-0.5" />
                    <span>CHAT</span>
                </button>
                <button 
                    v-if="user && user.user_ui_level >= 2"
                    @click="handleTabClick('feed')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'feed' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Feed"
                >
                    <IconHome class="w-3.5 h-3.5 mb-0.5" />
                    <span>FEED</span>
                </button>
                <button 
                    @click="handleTabClick('news')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'news' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Articles & News"
                >
                    <IconFileText class="w-3.5 h-3.5 mb-0.5" />
                    <span>NEWS</span>
                </button>
                <button 
                    @click="handleTabClick('notes')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'notes' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Notes"
                >
                    <IconPencil class="w-3.5 h-3.5 mb-0.5" />
                    <span>NOTE</span>
                </button>
                <button 
                    @click="handleTabClick('skills')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'skills' ? 'bg-white dark:bg-gray-700 text-teal-600 dark:text-teal-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Skills"
                >
                    <IconSparkles class="w-3.5 h-3.5 mb-0.5" />
                    <span>SKILL</span>
                </button>
                <button 
                    @click="handleTabClick('artefacts')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'artefacts' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Artefacts"
                >
                    <IconFileText class="w-3.5 h-3.5 mb-0.5" />
                    <span>ART</span>
                </button>
                <button 
                    @click="handleTabClick('personalities')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'personalities' ? 'bg-white dark:bg-gray-900/50 text-amber-600 dark:text-amber-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Personality Studio"
                >
                    <IconUser class="w-3.5 h-3.5 mb-0.5" />
                    <span>PERS</span>
                </button>
                <button 
                    @click="handleTabClick('images')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'images' ? 'bg-white dark:bg-gray-900/50 text-pink-600 dark:text-pink-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Images"
                >
                    <IconPhoto class="w-3.5 h-3.5 mb-0.5" />
                    <span>IMG</span>
                </button>
                <button 
                    @click="handleTabClick('notebooks')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'notebooks' ? 'bg-white dark:bg-gray-900/50 text-purple-600 dark:text-purple-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Notebooks"
                >
                    <IconServer class="w-3.5 h-3.5 mb-0.5" />
                    <span>BOOK</span>
                </button>
                <button 
                    v-if="hasActiveVectorizers"
                    @click="handleTabClick('data')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'data' ? 'bg-white dark:bg-gray-900/50 text-green-600 dark:text-green-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Data Stores"
                >
                    <IconDatabase class="w-3.5 h-3.5 mb-0.5" />
                    <span>DATA</span>
                </button>
                <button 
                    @click="handleTabClick('flows')" 
                    class="flex-1 py-1.5 px-2 text-[9px] font-bold rounded-md transition-colors flex flex-col items-center justify-center min-w-[50px]"
                    :class="activeTab === 'flows' ? 'bg-white dark:bg-gray-900/50 text-cyan-600 dark:text-cyan-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    title="Workflows"
                >
                    <IconShare class="w-3.5 h-3.5 mb-0.5" />
                    <span>FLOW</span>
                </button>
            </div>

            <div class="flex items-center justify-between">
                 <div class="flex items-center space-x-1">
                    <button @click="isSearchVisible = !isSearchVisible" class="btn-icon-flat" title="Search" :class="{'bg-slate-100 dark:bg-gray-700': isSearchVisible}">
                        <IconMagnifyingGlass class="h-4 w-4" />
                    </button>
                    <button v-if="activeTab !== 'notebooks' && activeTab !== 'data' && activeTab !== 'flows' && activeTab !== 'personalities' && activeTab !== 'news' && activeTab !== 'feed'" @click="handleNewGroup" class="btn-icon-flat" :title="activeTab === 'images' ? 'New Album' : 'New Group'">
                        <IconFolder class="w-4 h-4" />
                    </button>
                    <button v-if="activeTab !== 'notebooks' && activeTab !== 'data' && activeTab !== 'flows'" @click="handleNewGroup" class="btn-icon-flat" :title="activeTab === 'images' ? 'New Album' : 'New Group'">
                        <IconFolder class="w-4 h-4" />
                    </button>
                    <button v-if="activeTab === 'chat' && user && user.user_ui_level >= 4" @click="showToolbox = !showToolbox" class="btn-icon-flat" :class="{ 'bg-slate-100 dark:bg-gray-700': showToolbox }" title="Toggle Toolbox">
                        <IconAdjustmentsHorizontal class="h-4 w-4" />
                    </button>

                    <!-- Universal Refresh Button -->
                    <button @click="handleRefresh" class="btn-icon-flat" :title="`Refresh ${activeTab}`" :disabled="isRefreshingTab">
                        <IconRefresh class="h-4 w-4" :class="{'animate-spin text-blue-500': isRefreshingTab}" />
                    </button>

                    <!-- Sorting Tool -->
                    <div v-if="activeTab === 'chat' && user" @click.stop>
                        <DropdownMenu icon="arrows-up-down" buttonClass="btn-icon-flat" title="Organization Settings">
                            <div class="px-3 py-1.5 flex items-center justify-between border-b dark:border-gray-700">
                                <span class="text-[9px] font-black text-gray-400 uppercase tracking-widest">Direction</span>
                                <button @click="authStore.updateUserPreferences({ discussion_sorting_order: user.discussion_sorting_order === 'asc' ? 'desc' : 'asc' })" 
                                        class="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-[10px] font-bold text-blue-600 hover:bg-blue-50 transition-colors">
                                    {{ user.discussion_sorting_order === 'asc' ? 'Ascending' : 'Descending' }}
                                </button>
                            </div>
                            
                            <button @click="authStore.updateUserPreferences({ discussion_sorting_mode: 'date' })" class="menu-item justify-between" :class="{'text-blue-600 bg-blue-50/50 dark:bg-blue-900/10 font-bold': user.discussion_sorting_mode === 'date'}">
                                <div class="flex items-center gap-3">
                                    <IconPlus class="w-4 h-4 opacity-50" />
                                    <div class="flex flex-col">
                                        <span>Last Created</span>
                                        <span class="text-[9px] opacity-60">By record creation date</span>
                                    </div>
                                </div>
                                <IconCheckCircle v-if="user.discussion_sorting_mode === 'date'" class="w-4 h-4" />
                            </button>

                            <button @click="authStore.updateUserPreferences({ discussion_sorting_mode: 'activity' })" class="menu-item justify-between" :class="{'text-blue-600 bg-blue-50/50 dark:bg-blue-900/10 font-bold': user.discussion_sorting_mode === 'activity'}">
                                <div class="flex items-center gap-3">
                                    <IconRefresh class="w-4 h-4 opacity-50" />
                                    <div class="flex flex-col">
                                        <span>Last Updated</span>
                                        <span class="text-[9px] opacity-60">By recent activity/views</span>
                                    </div>
                                </div>
                                <IconCheckCircle v-if="user.discussion_sorting_mode === 'activity'" class="w-4 h-4" />
                            </button>

                            <button @click="authStore.updateUserPreferences({ discussion_sorting_mode: 'alpha' })" class="menu-item justify-between" :class="{'text-blue-600 bg-blue-50/50 dark:bg-blue-900/10 font-bold': user.discussion_sorting_mode === 'alpha'}">
                                <div class="flex items-center gap-3">
                                    <IconFileText class="w-4 h-4 opacity-50" />
                                    <div class="flex flex-col">
                                        <span>Alphabetical</span>
                                        <span class="text-[9px] opacity-60">By discussion title (A-Z)</span>
                                    </div>
                                </div>
                                <IconCheckCircle v-if="user.discussion_sorting_mode === 'alpha'" class="w-4 h-4" />
                            </button>
                        </DropdownMenu>
                    </div>
                </div>

                <!-- Dropdown + Button for Artefacts/ART tab to show all options -->
                <DropdownMenu 
                    v-if="activeTab === 'artefacts'"
                    icon="plus" 
                    title="Add Document" 
                    buttonClass="btn-primary-flat !px-2.5"
                >
                    <template #icon>
                        <IconPlus class="h-4 w-4" stroke-width="2.5" />
                    </template>
                    <div class="p-1 min-w-[260px]">
                        <button @click="triggerArtefactFileUpload('as_is')" class="menu-item"><IconFolder class="w-4 h-4 mr-3 text-emerald-500" /> <span>Native File (as-is)</span></button>
                        <button @click="triggerArtefactFileUpload('text_images')" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-blue-500" /> <span>Text + Pages as Images</span></button>
                        <button @click="triggerArtefactFileUpload('text_embedded_images')" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-blue-600" /> <span>Text + Embedded Images</span></button>
                        <button @click="triggerArtefactFileUpload('text')" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-gray-500" /> <span>Text Only</span></button>
                        <button @click="triggerArtefactFileUpload('images_only')" class="menu-item"><IconPhoto class="w-4 h-4 mr-3 text-purple-500" /> <span>Images Only</span></button>
                        <button @click="triggerArtefactFileUpload('ocr')" class="menu-item border-t dark:border-gray-700 mt-1 pt-2"><IconEye class="w-4 h-4 mr-3 text-indigo-500" /> <span>OCR (Vision Transcript)</span></button>
                        <button @click="triggerArtefactFileUpload('data')" class="menu-item border-t dark:border-gray-700 mt-1 pt-2"><IconDatabase class="w-4 h-4 mr-3 text-green-500" /> <span>Data / Spreadsheet</span></button>
                        <button @click="triggerBundleImport" class="menu-item border-t dark:border-gray-700 mt-1 pt-2"><IconRefresh class="w-4 h-4 mr-3 text-teal-500" /> <span>Import Bundle (.json)</span></button>
                        <button @click="handleCreateArtefact" class="menu-item border-t dark:border-gray-700 mt-1 pt-2"><IconPencil class="w-4 h-4 mr-3 text-orange-500" /> <span>Create Document (Manual)</span></button>
                    </div>
                </DropdownMenu>

                <button v-else @click="handleNewItem()" class="btn-primary-flat !px-2.5" :title="route.path.startsWith('/personality-studio') ? 'New Personality' : (activeTab === 'chat' ? 'New Discussion' : (activeTab === 'notes' ? 'New Note' : (activeTab === 'skills' ? 'New Skill' : (activeTab === 'data' ? 'New Data Store' : (activeTab === 'images' ? 'New Album' : (activeTab === 'flows' ? 'New Workflow' : 'New Notebook'))))))">
                    <IconPlus class="h-4 w-4" stroke-width="2.5" />
                </button>
            </div>
            
            <div v-if="isSearchVisible" class="relative mt-2">
                <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <IconMagnifyingGlass class="h-4 w-4 text-slate-400 dark:text-gray-500" />
                </div>
                <input type="text" v-model="searchTerm" :placeholder="activeTab === 'chat' ? 'Search discussions...' : (activeTab === 'notes' ? 'Search notes...' : 'Search...')" class="search-input-flat">
                <button v-if="searchTerm" @click="searchTerm = ''" class="absolute inset-y-0 right-0 flex items-center pr-3" title="Clear search">
                    <IconXMark class="h-4 w-4 text-slate-400 hover:text-slate-600 dark:hover:text-gray-300 transition-colors" />
                </button>
            </div>

            <div v-if="activeTab === 'chat' && user && user.user_ui_level >= 4 && showToolbox" class="overflow-hidden transition-all duration-300 ease-out">
                <div class="p-3 bg-slate-50 dark:bg-gray-800 rounded-md border border-slate-200 dark:border-gray-700">
                    <div class="grid grid-cols-6 gap-2">
                        <button @click="handleCopyDiscussionMarkdown" class="btn-toolbox-flat" title="Copy Discussion as Markdown" :disabled="!activeDiscussion"><IconCopy class="h-4 w-4 text-blue-500" /><span class="text-xs mt-1 font-medium">Copy MD</span></button>
                        <button @click="handleImportClick" class="btn-toolbox-flat" title="Import"><IconArrowDownTray class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Import</span></button>
                        <button @click="handleExportClick" class="btn-toolbox-flat" title="Export"><IconArrowUpTray class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Export</span></button>
                        <button @click="handleClone" class="btn-toolbox-flat" title="Clone Discussion" :disabled="!activeDiscussion"><IconCopy class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Clone</span></button>
                        <button @click="handleShowTree" class="btn-toolbox-flat" title="Show Discussion Tree" :disabled="!activeDiscussion"><IconGitBranch class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Tree</span></button>
                        <button @click="handlePrune" class="btn-toolbox-danger-flat" title="Prune Empty"><IconScissors class="h-4 w-4" /><span class="text-xs mt-1 font-medium">Prune</span></button>
                    </div>
                </div>
            </div>
        </div>
        
        <div ref="scrollComponent" class="grow overflow-y-auto p-2 space-y-1 custom-scrollbar">
            <!-- Active Processing Item -->
            <div v-if="isUploadingArtefact" class="mb-4 p-2 animate-in fade-in slide-in-from-top-2">
                 <div class="flex items-center gap-4 p-3 bg-blue-50/50 dark:bg-blue-900/10 rounded-xl border border-blue-100 dark:border-blue-800 shadow-sm">
                    <IconAnimateSpin class="w-5 h-5 text-blue-500 animate-spin shrink-0" />
                    <div class="flex flex-col min-w-0">
                        <span class="text-[9px] font-black uppercase tracking-widest text-blue-500 mb-0.5">Workspace Ingestion</span>
                        <p class="text-[11px] font-bold text-gray-700 dark:text-gray-300 leading-tight">
                            {{ uploadingMessage }}
                        </p>
                    </div>
                 </div>
            </div>

            <!-- CHATS TAB -->
            <template v-if="activeTab === 'chat'">
                <div v-if="isLoadingDiscussions" class="space-y-2 animate-pulse">
                    <div v-for="i in 8" :key="'skel-' + i" class="loading-skeleton-flat"></div>
                </div>
                
                <div v-else class="space-y-3">
                    <!-- SECTION 1: STARRED -->
                    <div v-if="filteredDiscussionTree.starred && filteredDiscussionTree.starred.length > 0">
                        <button @click="isStarredVisible = !isStarredVisible" class="section-header-flat">
                            <div class="flex items-center space-x-2">
                                <span class="font-bold text-slate-700 dark:text-gray-300">Starred</span>
                                <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-[10px] font-bold">
                                    {{ filteredDiscussionTree.starred.length }}
                                </div>
                            </div>
                            <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isStarredVisible}" />
                        </button>
                        <div v-if="isStarredVisible" class="space-y-1 mt-2">
                            <DiscussionItem v-for="discussion in filteredDiscussionTree.starred" :key="discussion.id" :discussion="discussion" />
                        </div>
                    </div>

                    <!-- SECTION 2: UNGROUPED (Now prioritized at top) -->
                    <div v-if="filteredDiscussionTree.ungrouped && filteredDiscussionTree.ungrouped.length > 0">
                        <button @click="handleSelectUngrouped" class="section-header-flat" :class="{'bg-blue-50 dark:bg-blue-900/20': store.currentGroupId === null && !store.currentDiscussionId}">
                            <div class="flex items-center space-x-2">
                                <span class="font-bold text-slate-700 dark:text-gray-300">Discussions</span>
                                <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-[10px] font-bold">
                                    {{ filteredDiscussionTree.ungrouped.length }}
                                </div>
                            </div>
                            <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isUngroupedVisible}" />
                        </button>
                        <div v-if="isUngroupedVisible" class="space-y-1 mt-2">
                            <DiscussionItem v-for="discussion in filteredDiscussionTree.ungrouped" :key="discussion.id" :discussion="discussion" />
                        </div>
                    </div>

                    <!-- SECTION 3: FOLDERS (Groups) -->
                    <div v-if="filteredDiscussionTree.groups && filteredDiscussionTree.groups.length > 0">
                        <button @click="isFoldersVisible = !isFoldersVisible" class="section-header-flat mt-4">
                            <div class="flex items-center space-x-2">
                                <span class="font-bold text-slate-700 dark:text-gray-300">Folders</span>
                                <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-[10px] font-bold">
                                    {{ filteredDiscussionTree.groups.length }}
                                </div>
                            </div>
                            <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isFoldersVisible}" />
                        </button>
                        <div v-if="isFoldersVisible" class="space-y-1 mt-2">
                            <DiscussionGroupItem 
                                v-for="group in filteredDiscussionTree.groups" 
                                :key="group.id" 
                                :group="group" 
                            />
                        </div>
                    </div>

                    <!-- SECTION 4: SHARED -->
                    <div v-if="filteredSharedDiscussions.length > 0">
                        <button @click="isSharedVisible = !isSharedVisible" class="section-header-flat mt-4">
                            <div class="flex items-center space-x-2">
                                <span class="font-bold text-slate-700 dark:text-gray-300">Shared with me</span>
                                <div class="px-1.5 py-0.5 bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-[10px] font-bold">
                                    {{ filteredSharedDiscussions.length }}
                                </div>
                            </div>
                            <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isSharedVisible}" />
                        </button>
                        <div v-if="isSharedVisible" class="space-y-1 mt-2">
                            <DiscussionItem v-for="discussion in filteredSharedDiscussions" :key="discussion.share_id" :discussion="discussion" />
                        </div>
                    </div>

                    <div v-if="!isLoadingDiscussions && sortedDiscussions.length === 0 && sharedWithMe.length === 0" class="empty-state-flat">
                        <p class="text-base font-medium text-slate-600 dark:text-gray-300 mb-2">
                            {{ searchTerm ? 'No matches found' : 'Start your first conversation' }}
                        </p>
                        <p class="text-sm text-slate-500 dark:text-gray-400">
                            {{ searchTerm ? 'Try different keywords' : 'Click the "+" button to begin' }}
                        </p>
                    </div>
                </div>
            </template>
            
            <!-- NOTES TAB -->
            <template v-else-if="activeTab === 'notes'">
                <NoteList :search-term="searchTerm" />
            </template>

            <!-- SKILLS TAB -->
            <template v-else-if="activeTab === 'skills'">
                <SkillList :search-term="searchTerm" />
            </template>

            <!-- ARTEFACTS TAB -->
            <template v-else-if="activeTab === 'artefacts'">
                <ArtefactGlobalList :search-term="searchTerm" />
            </template>

            <!-- NEWS TAB -->
            <template v-else-if="activeTab === 'news'">
                <div class="space-y-2 mb-3">
                    <button @click="fetchNewsArticlesList" class="w-full flex items-center space-x-3 text-left px-3 py-2 rounded-lg text-xs font-bold text-blue-700 dark:text-blue-300 bg-blue-50/70 hover:bg-blue-100 dark:bg-blue-900/30 dark:hover:bg-blue-900/40 transition-colors">
                        <IconRefresh class="w-4 h-4 shrink-0" :class="{'animate-spin': isLoadingNews}" />
                        <span>Refresh News</span>
                    </button>
                </div>

                <div v-if="isLoadingNews" class="text-center p-4 text-xs text-gray-500">
                    <IconAnimateSpin class="w-5 h-5 text-blue-500 mx-auto mb-2 animate-spin" />
                    <span>Loading news articles...</span>
                </div>
                <div v-else-if="filteredNewsArticles.length === 0" class="empty-state-flat">
                    <p class="text-sm font-medium text-slate-600 dark:text-gray-300 mb-1">
                        {{ searchTerm ? 'No news match your search' : 'No news articles available' }}
                    </p>
                    <p class="text-xs text-slate-500 dark:text-gray-400">
                        {{ searchTerm ? 'Try different keywords' : 'Configure RSS feeds in Admin panel' }}
                    </p>
                </div>
                <div v-else class="space-y-1">
                    <div v-for="article in filteredNewsArticles" :key="article.id"
                         @click="handleSelectNewsArticle(article)"
                         class="group flex items-start justify-between p-2.5 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-all border border-transparent hover:border-gray-200 dark:hover:border-gray-700 shadow-xs">
                        <div class="flex items-start gap-2.5 min-w-0">
                            <div class="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center shrink-0 mt-0.5 border border-blue-200 dark:border-blue-800">
                                <IconFileText class="w-4 h-4 text-blue-600 dark:text-blue-400" />
                            </div>
                            <div class="flex flex-col min-w-0">
                                <span class="text-xs font-bold text-slate-800 dark:text-gray-200 line-clamp-2 leading-tight">{{ article.title }}</span>
                                <span v-if="article.publication_date" class="text-[9px] text-gray-400 mt-1 font-mono">
                                    {{ new Date(article.publication_date).toLocaleDateString() }}
                                </span>
                            </div>
                        </div>
                        <a v-if="article.url" :href="article.url" target="_blank" @click.stop class="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-blue-500 transition-opacity shrink-0" title="Open source URL">
                            <IconShare class="w-3.5 h-3.5" />
                        </a>
                    </div>
                </div>
            </template>

            <!-- FEED TAB -->
            <template v-else-if="activeTab === 'feed'">
                <div class="space-y-3">
                    <!-- General Feed Button -->
                    <button @click="selectGeneralFeed"
                            class="w-full text-left p-2.5 rounded-xl flex items-center justify-between transition-all border shadow-xs"
                            :class="uiStore.mainView === 'feed' ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 border-blue-200 dark:border-blue-800 font-bold' : 'hover:bg-gray-100 dark:hover:bg-gray-800 border-transparent hover:border-gray-200 dark:hover:border-gray-700 text-gray-800 dark:text-gray-200'">
                        <div class="flex items-center gap-2.5 min-w-0">
                            <div class="w-7 h-7 rounded-lg bg-blue-100/60 dark:bg-blue-900/40 flex items-center justify-center shrink-0 border border-blue-200 dark:border-blue-800">
                                <IconHome class="w-4 h-4 text-blue-600 dark:text-blue-400" />
                            </div>
                            <div class="flex flex-col min-w-0">
                                <span class="text-xs">Main Community Feed</span>
                                <span class="text-[9px] text-gray-400">All public posts & updates</span>
                            </div>
                        </div>
                        <IconChevronRight class="w-4 h-4 text-gray-400 shrink-0" />
                    </button>

                    <!-- By Friends Section -->
                    <div class="space-y-1.5 pt-1">
                        <div class="flex items-center justify-between px-2">
                            <h3 class="text-[10px] font-black uppercase tracking-wider text-gray-400 dark:text-gray-500">
                                Friends ({{ filteredFriends.length }})
                            </h3>
                            <router-link to="/friends" class="text-[10px] text-blue-500 hover:underline">Manage</router-link>
                        </div>

                        <div v-if="filteredFriends.length === 0" class="p-3 text-center text-xs text-gray-400 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
                            {{ searchTerm ? 'No friends match search' : 'No friends added yet' }}
                        </div>
                        <div v-else class="space-y-1">
                            <div v-for="friend in filteredFriends" :key="friend.id"
                                 @click="selectFriendFeed(friend)"
                                 class="group flex items-center justify-between p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-all border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
                                 :class="{'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800 font-bold': route.params.username === friend.username}">
                                <div class="flex items-center gap-2.5 min-w-0">
                                    <div class="w-7 h-7 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-700 flex items-center justify-center shrink-0 border border-gray-200 dark:border-gray-600">
                                        <img v-if="friend.icon" :src="friend.icon" class="w-full h-full object-cover" />
                                        <IconUser v-else class="w-4 h-4 text-gray-500" />
                                    </div>
                                    <div class="flex flex-col min-w-0">
                                        <span class="text-xs text-slate-800 dark:text-gray-200 font-medium truncate">{{ friend.username }}</span>
                                        <span v-if="friend.first_name || friend.family_name" class="text-[9px] text-gray-400 truncate">{{ [friend.first_name, friend.family_name].filter(Boolean).join(' ') }}</span>
                                    </div>
                                </div>
                                <IconChevronRight class="w-3.5 h-3.5 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                        </div>
                    </div>

                    <!-- By Social Groups Section -->
                    <div v-if="socialGroups.length > 0 || !searchTerm" class="space-y-1.5 pt-1">
                        <div class="flex items-center justify-between px-2">
                            <h3 class="text-[10px] font-black uppercase tracking-wider text-gray-400 dark:text-gray-500">
                                Groups ({{ filteredSocialGroups.length }})
                            </h3>
                        </div>

                        <div v-if="filteredSocialGroups.length === 0" class="p-3 text-center text-xs text-gray-400 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
                            {{ searchTerm ? 'No groups match search' : 'No social groups' }}
                        </div>
                        <div v-else class="space-y-1">
                            <div v-for="group in filteredSocialGroups" :key="group.id"
                                 @click="selectGroupFeed(group)"
                                 class="group flex items-center justify-between p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-all border border-transparent hover:border-gray-200 dark:hover:border-gray-700">
                                <div class="flex items-center gap-2.5 min-w-0">
                                    <div class="w-7 h-7 rounded-lg bg-purple-50 dark:bg-purple-900/30 flex items-center justify-center shrink-0 border border-purple-200 dark:border-purple-800">
                                        <IconShare class="w-4 h-4 text-purple-600 dark:text-purple-400" />
                                    </div>
                                    <div class="flex flex-col min-w-0">
                                        <span class="text-xs text-slate-800 dark:text-gray-200 font-medium truncate">{{ group.displayName || group.display_name || group.name }}</span>
                                        <span class="text-[9px] text-gray-400 truncate">{{ group.members?.length || 0 }} members</span>
                                    </div>
                                </div>
                                <IconChevronRight class="w-3.5 h-3.5 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                        </div>
                    </div>
                </div>
            </template>

            <!-- PERSONALITIES TAB -->
            <template v-else-if="activeTab === 'personalities'">
                <div class="space-y-2 mb-3">
                    <button @click="handleNewItem" class="w-full flex items-center space-x-3 text-left px-3 py-2 rounded-lg text-xs font-bold text-amber-700 dark:text-amber-300 bg-amber-50/70 hover:bg-amber-100 dark:bg-amber-950/30 dark:hover:bg-amber-900/40 transition-colors">
                        <IconPlus class="w-4 h-4 shrink-0" />
                        <span>New Personality</span>
                    </button>
                </div>

                <div v-if="filteredUserPersonalities.length === 0 && filteredPublicPersonalities.length === 0" class="empty-state-flat">
                    <p class="text-sm font-medium text-slate-600 dark:text-gray-300 mb-1">
                        {{ searchTerm ? 'No personalities found' : 'No personalities yet' }}
                    </p>
                    <p class="text-xs text-slate-500 dark:text-gray-400">
                        Click "+ New Personality" to create one
                    </p>
                </div>

                <div v-else class="space-y-4">
                    <!-- Personal Section -->
                    <div v-if="filteredUserPersonalities.length > 0">
                        <h3 class="text-[10px] font-black uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-1.5 px-2">
                            Personal ({{ filteredUserPersonalities.length }})
                        </h3>
                        <div class="space-y-1">
                            <div v-for="p in filteredUserPersonalities" :key="p.id" 
                                 @click="handleSelectPersonality(p)"
                                 class="group flex items-center justify-between p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-all border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
                                 :class="{'bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800/60 font-bold': user?.active_personality_id === p.id}">
                                <div class="flex items-center gap-2.5 min-w-0">
                                    <div class="w-7 h-7 rounded-lg overflow-hidden bg-gray-100 dark:bg-gray-700 flex items-center justify-center shrink-0 border border-gray-200 dark:border-gray-600">
                                        <img v-if="p.icon_base64" :src="p.icon_base64" class="w-full h-full object-cover" />
                                        <IconUser v-else class="w-4 h-4 text-amber-500" />
                                    </div>
                                    <div class="flex flex-col min-w-0">
                                        <span class="text-xs text-slate-800 dark:text-gray-200 truncate">{{ p.name }}</span>
                                        <span v-if="p.category" class="text-[9px] text-gray-400 truncate">{{ p.category }}</span>
                                    </div>
                                </div>
                                <div class="flex items-center gap-1 shrink-0">
                                    <IconCheckCircle v-if="user?.active_personality_id === p.id" class="w-4 h-4 text-emerald-500" />
                                    <button @click.stop="handleEditPersonality(p)" class="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-blue-500 transition-opacity" title="Edit Personality">
                                        <IconPencil class="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Public / System Section -->
                    <div v-if="filteredPublicPersonalities.length > 0">
                        <h3 class="text-[10px] font-black uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-1.5 px-2">
                            Public ({{ filteredPublicPersonalities.length }})
                        </h3>
                        <div class="space-y-1">
                            <div v-for="p in filteredPublicPersonalities" :key="p.id" 
                                 @click="handleSelectPersonality(p)"
                                 class="group flex items-center justify-between p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-all border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
                                 :class="{'bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800/60 font-bold': user?.active_personality_id === p.id}">
                                <div class="flex items-center gap-2.5 min-w-0">
                                    <div class="w-7 h-7 rounded-lg overflow-hidden bg-gray-100 dark:bg-gray-700 flex items-center justify-center shrink-0 border border-gray-200 dark:border-gray-600">
                                        <img v-if="p.icon_base64" :src="p.icon_base64" class="w-full h-full object-cover" />
                                        <IconUser v-else class="w-4 h-4 text-amber-500" />
                                    </div>
                                    <div class="flex flex-col min-w-0">
                                        <span class="text-xs text-slate-800 dark:text-gray-200 truncate">{{ p.name }}</span>
                                        <span v-if="p.category" class="text-[9px] text-gray-400 truncate">{{ p.category }}</span>
                                    </div>
                                </div>
                                <div class="flex items-center gap-1 shrink-0">
                                    <IconCheckCircle v-if="user?.active_personality_id === p.id" class="w-4 h-4 text-emerald-500" />
                                    <button @click.stop="handleEditPersonality(p)" class="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-blue-500 transition-opacity" title="Inspect Personality">
                                        <IconEye class="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </template>

            <!-- IMAGES TAB -->
            <template v-else-if="activeTab === 'images'">
                <AlbumList :search-term="searchTerm" />
            </template>

            <!-- NOTEBOOKS TAB -->
            <template v-else-if="activeTab === 'notebooks'">
                <div v-if="notebookStore.isLoading" class="text-center p-4 text-gray-500">Loading notebooks...</div>
                <div v-else-if="filteredNotebooks.length === 0" class="empty-state-flat">
                    <p class="text-base font-medium text-slate-600 dark:text-gray-300 mb-2">
                         {{ searchTerm ? 'No matches found' : 'No notebooks yet' }}
                    </p>
                     <p class="text-sm text-slate-500 dark:text-gray-400">
                        {{ searchTerm ? 'Try different keywords' : 'Create a new notebook to start research' }}
                    </p>
                </div>
                <div v-else class="space-y-1">
                    <div v-for="nb in filteredNotebooks" :key="nb.id" 
                         class="group flex items-center justify-between p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                         :class="{'bg-purple-50 dark:bg-purple-900/20': notebookStore.activeNotebook?.id === nb.id}"
                         @click="openNotebook(nb)">
                        <div class="flex items-center gap-3 min-w-0">
                            <IconServer class="w-4 h-4 shrink-0 text-purple-500" />
                            <div class="flex flex-col min-w-0">
                                <span class="text-sm font-medium text-slate-700 dark:text-gray-200 truncate">{{ nb.title || 'Untitled Notebook' }}</span>
                                <span class="text-[10px] text-gray-500 uppercase font-black tracking-widest">{{ (nb.type || 'generic').replace('_', ' ') }}</span>
                            </div>
                        </div>
                        <button @click.stop="handleDeleteNotebook(nb)" class="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-opacity" title="Delete Notebook">
                            <IconTrash class="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </template>

            <!-- DATA TAB -->
            <template v-else-if="activeTab === 'data'">
                <div class="space-y-2 mb-4">
                    <button @click="handleNewItem" class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/50 transition-colors">
                        <IconPlus class="w-5 h-5 shrink-0" />
                        <span>New Data Store</span>
                    </button>
                    <button @click="dataStore.fetchDataStores()" class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                        <IconRefresh class="w-5 h-5 shrink-0" />
                        <span>Refresh All Stores</span>
                    </button>
                </div>

                <div v-if="dataStore.isLoading" class="text-center p-4 text-gray-500">Loading stores...</div>
                <div v-else-if="filteredOwnedStores.length === 0 && filteredSharedStores.length === 0" class="empty-state-flat">
                    <p class="text-base font-medium text-slate-600 dark:text-gray-300 mb-2">
                         {{ searchTerm ? 'No matches found' : 'No data stores yet' }}
                    </p>
                     <p class="text-sm text-slate-500 dark:text-gray-400">
                        Create a data store to index your documents for RAG.
                    </p>
                </div>
                <div v-else class="space-y-4">
                    <!-- Owned Stores -->
                    <div v-if="filteredOwnedStores.length > 0">
                        <h3 class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 mb-2 px-2">Your Stores</h3>
                        <div class="space-y-1">
                            <DataStoreItem 
                                v-for="ds in filteredOwnedStores" 
                                :key="ds.id" 
                                :store="ds"
                                :is-selected="route.query.storeId === ds.id"
                                @select="handleDataStoreSelect"
                                @edit="onEditStore"
                                @delete="onDeleteStore"
                                @share="onShareStore"
                            />
                        </div>
                    </div>
                    
                    <!-- Shared Stores -->
                    <div v-if="filteredSharedStores.length > 0">
                        <h3 class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 mb-2 px-2">Shared With You</h3>
                        <div class="space-y-1">
                            <DataStoreItem 
                                v-for="ds in filteredSharedStores" 
                                :key="ds.id" 
                                :store="ds"
                                :is-selected="route.query.storeId === ds.id"
                                @select="handleDataStoreSelect"
                                @leave="onLeaveStore"
                            />
                        </div>
                    </div>
                </div>
            </template>
            
            <!-- FLOWS TAB -->
            <template v-else-if="activeTab === 'flows'">
                <div v-if="flowStore.isLoading" class="text-center p-4 text-gray-500">Loading flows...</div>
                <div v-else-if="filteredFlows.length === 0" class="empty-state-flat">
                    <p class="text-base font-medium text-slate-600 dark:text-gray-300 mb-2">
                         {{ searchTerm ? 'No matches found' : 'No workflows yet' }}
                    </p>
                     <p class="text-sm text-slate-500 dark:text-gray-400">
                        Create a new workflow to automate tasks.
                    </p>
                </div>
                <div v-else class="space-y-1">
                    <div v-for="flow in filteredFlows" :key="flow.id" 
                         class="group flex items-center justify-between p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                         :class="{'bg-cyan-50 dark:bg-cyan-900/20': flowStore.currentFlow?.id === flow.id}"
                         @click="openFlow(flow)">
                        <div class="flex items-center gap-3 min-w-0">
                            <IconShare class="w-4 h-4 shrink-0 text-cyan-500" />
                            <div class="flex flex-col min-w-0">
                                <span class="text-sm font-medium text-slate-700 dark:text-gray-200 truncate">{{ flow.name }}</span>
                                <span class="text-[10px] text-gray-500 truncate" v-if="flow.description">{{ flow.description }}</span>
                            </div>
                        </div>
                        <button @click.stop="handleDeleteFlow(flow)" class="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-opacity" title="Delete Workflow">
                            <IconTrash class="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </template>
        </div>

    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
.menu-divider { @apply my-1 border-t border-gray-100 dark:border-gray-700; }
</style>
