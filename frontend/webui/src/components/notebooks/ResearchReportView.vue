<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';

// Icons
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconWeb from '../../assets/icons/IconWeb.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';
import IconTableCells from '../../assets/icons/IconTableCells.vue';
import IconChartBar from '../../assets/icons/IconChartBar.vue';
import IconListBullet from '../../assets/icons/IconListBullet.vue';
import IconDocumentText from '../../assets/icons/IconDocumentText.vue';

const props = defineProps({
    notebook: { type: Object, required: true }
});

const notebookStore = useNotebookStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const { tasks } = storeToRefs(tasksStore);

const activeTabId = ref(null);
const isRenderMode = ref(true);
const aiPrompt = ref('');
const modifyCurrentTab = ref(false);
const selectedArtefactNames = ref([]);
const logsContainerRef = ref(null);
const editingArtefact = ref(null);
const showSectionEditor = ref(false);
const editingSection = ref(null);
const sectionEditorContent = ref('');

// Report-specific state
const reportSections = ref([]);
const activeSection = ref(null);
const showTableOfContents = ref(true);

// Standardized Active Task Lookup
const activeTask = computed(() => {
    return tasks.value.find(t =>
        (t.name.includes(props.notebook.title) || t.description.includes(props.notebook.id)) &&
        (t.status === 'running' || t.status === 'pending')
    );
});

const currentTab = computed(() => {
    if (!props.notebook.tabs?.length) return null;
    return props.notebook.tabs.find(t => t.id === activeTabId.value) || props.notebook.tabs[0];
});

const currentHtmlSrc = computed(() => {
    if (currentTab.value?.type === 'html' && currentTab.value.content) {
        const blob = new Blob([currentTab.value.content], { type: 'text/html' });
        return URL.createObjectURL(blob);
    }
    return null;
});

// Parse report sections from markdown content
const parseReportSections = (content) => {
    if (!content) return [];

    // Extract sections based on markdown headers
    const headerRegex = /^(#{1,6})\s+(.*?)\s*$/gm;
    const sections = [];
    let lastHeaderLevel = 0;
    let lastSection = null;
    let match;

    // First pass: extract all headers
    while ((match = headerRegex.exec(content)) !== null) {
        const level = match[1].length;
        const title = match[2].trim();
        const section = {
            id: `section-${sections.length}`,
            title,
            level,
            content: '',
            startIndex: match.index,
            endIndex: 0,
            children: []
        };

        if (sections.length === 0) {
            // First section
            sections.push(section);
            lastSection = section;
            lastHeaderLevel = level;
        } else {
            if (level > lastHeaderLevel) {
                // Child section
                lastSection.children.push(section);
                section.parent = lastSection;
            } else if (level === lastHeaderLevel) {
                // Sibling section
                if (lastSection.parent) {
                    lastSection.parent.children.push(section);
                } else {
                    sections.push(section);
                }
            } else {
                // Higher level section - find the right parent
                let parent = lastSection;
                while (parent && parent.level >= level) {
                    parent = parent.parent;
                }
                if (parent) {
                    parent.children.push(section);
                    section.parent = parent;
                } else {
                    sections.push(section);
                }
            }
            lastSection = section;
            lastHeaderLevel = level;
        }
    }

    // Second pass: extract content for each section
    if (sections.length > 0) {
        for (let i = 0; i < sections.length; i++) {
            const section = sections[i];
            const nextSection = i < sections.length - 1 ? sections[i + 1] : null;
            const nextSectionStart = nextSection ? nextSection.startIndex : content.length;

            section.content = content.substring(section.startIndex, nextSectionStart).trim();
            section.endIndex = nextSectionStart;
        }
    }

    return sections;
};

// Watch for content changes to update sections
watch(() => currentTab.value?.content, (newContent) => {
    if (currentTab.value?.type === 'markdown' && newContent) {
        reportSections.value = parseReportSections(newContent);
        if (reportSections.value.length > 0 && !activeSection.value) {
            activeSection.value = reportSections.value[0].id;
        }
    }
}, { immediate: true });

const initTabs = () => {
    if (props.notebook.tabs?.length > 0) {
        if (!activeTabId.value || !props.notebook.tabs.find(t => t.id === activeTabId.value)) {
            activeTabId.value = props.notebook.tabs[0].id;
        }
    }
};

watch(() => props.notebook.id, initTabs, { immediate: true });
watch(() => props.notebook.tabs, initTabs, { deep: true });

watch(() => activeTask.value?.logs?.length, () => {
    nextTick(() => {
        if (logsContainerRef.value) {
            logsContainerRef.value.scrollTop = logsContainerRef.value.scrollHeight;
        }
    });
});

// Find section by ID
const findSectionById = (id, sections = reportSections.value) => {
    for (const section of sections) {
        if (section.id === id) return section;
        if (section.children && section.children.length > 0) {
            const found = findSectionById(id, section.children);
            if (found) return found;
        }
    }
    return null;
};

// Get section content for editing
const getSectionContent = (sectionId) => {
    const section = findSectionById(sectionId);
    return section ? section.content : '';
};

// Update section content
const updateSectionContent = (sectionId, newContent) => {
    const section = findSectionById(sectionId);
    if (section) {
        section.content = newContent;

        // Rebuild the full content
        const rebuildContent = (sections) => {
            let content = '';
            for (const section of sections) {
                content += section.content + '\n\n';
                if (section.children && section.children.length > 0) {
                    content += rebuildContent(section.children);
                }
            }
            return content;
        };

        const fullContent = rebuildContent(reportSections.value);
        if (currentTab.value) {
            currentTab.value.content = fullContent;
        }
    }
};

// Open section editor
const openSectionEditor = (sectionId) => {
    editingSection.value = sectionId;
    sectionEditorContent.value = getSectionContent(sectionId);
    showSectionEditor.value = true;
};

// Save section edits
const saveSectionEdit = () => {
    if (editingSection.value) {
        updateSectionContent(editingSection.value, sectionEditorContent.value);
        showSectionEditor.value = false;
        editingSection.value = null;
        notebookStore.saveActive();
    }
};

// --- AI ACTIONS ---
async function handleAction(actionType) {
    const target = modifyCurrentTab.value ? activeTabId.value : null;
    let prompt = aiPrompt.value;

    if (actionType === 'summarize' && !prompt) {
        prompt = "Summarize the selected information into a comprehensive research report.";
    }

    if (!prompt.trim() && !selectedArtefactNames.value.length) {
        uiStore.addNotification("Please enter a prompt or select artefacts.", "warning");
        return;
    }

    await notebookStore.processWithAi(prompt, [], actionType, target, false, selectedArtefactNames.value);
    aiPrompt.value = '';
}

// Generate a specific section
async function generateSection(sectionTitle) {
    const prompt = `Generate a detailed ${sectionTitle} section for this research report based on the selected artefacts.`;
    await notebookStore.processWithAi(prompt, [], 'text_processing', currentTab.value.id, false, selectedArtefactNames.value);
}

// Generate table of contents
async function generateTableOfContents() {
    const prompt = "Generate a table of contents for this research report based on the existing headings.";
    await notebookStore.processWithAi(prompt, [], 'text_processing', currentTab.value.id, false, []);
}

// --- HELPERS ---
function getSlideImageInfo(slide) {
    if (slide.images && slide.images.length > 0) {
        const idx = slide.selected_image_index || 0;
        const safeIdx = Math.min(Math.max(0, idx), slide.images.length - 1);
        return {
            info: slide.images[safeIdx],
            path: slide.images[safeIdx]?.path,
            index: safeIdx,
            total: slide.images.length
        };
    }
    return null;
}

// --- ARTEFACTS & CONVERSION ---
function toggleArtefact(name) {
    const idx = selectedArtefactNames.value.indexOf(name);
    if (idx === -1) selectedArtefactNames.value.push(name);
    else selectedArtefactNames.value.splice(idx, 1);
}

function openImportWizard() {
    uiStore.openModal('artefactImportWizard', { notebookId: props.notebook.id });
}

async function saveTabAsArtefact() {
    if (!currentTab.value) return;
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'Save as Artefact',
        message: 'Enter a name for this new source:',
        confirmText: 'Save',
        inputType: 'text',
        inputValue: currentTab.value.title
    });

    if (confirmed && value) {
        await notebookStore.createManualArtefact(value, currentTab.value.content);
    }
}

async function convertToProject(type) {
    let context = "";
    if (currentTab.value && currentTab.value.content) {
        context += `\n\n[Primary Content from ${currentTab.value.title}]\n${currentTab.value.content}\n`;
    }

    for (const name of selectedArtefactNames.value) {
        const art = props.notebook.artefacts.find(a => a.filename === name);
        if (art) context += `\n\n[Source: ${name}]\n${art.content}\n`;
    }

    if (!context.trim()) {
        uiStore.addNotification("Please select artefacts or open a tab with content to use as a base.", "warning");
        return;
    }

    const title = type === 'slides_making' ? 'New Presentation' :
                 type === 'youtube_video' ? 'New Video Project' :
                 type === 'book_building' ? 'New Book' : 'New Project';

    const newNotebook = await notebookStore.createStructuredNotebook({
        title: title,
        type: type,
        initialPrompt: "Initialize project from previous research.",
        raw_text: context
    });

    if (newNotebook) {
        uiStore.addNotification("Project created! Switching views...", "success");
        await notebookStore.selectNotebook(newNotebook.id);
    }
}

// --- TAB MANAGEMENT ---
function handleCloseTab(id) {
    if (confirm("Delete this tab?")) {
        notebookStore.removeTab(id);
        if (activeTabId.value === id) activeTabId.value = null;
    }
}

// --- ARTEFACT EDITING ---
function viewArtefact(art) {
    uiStore.openModal('artefactViewer', {
        artefact: {
            title: art.filename,
            content: art.content
        }
    });
}

function openArtefactEditor(art) {
    editingArtefact.value = {
        originalName: art.filename,
        name: art.filename,
        content: art.content
    };
}

async function saveArtefactEdit() {
    if (!editingArtefact.value) return;
    try {
        await notebookStore.updateArtefact(
            editingArtefact.value.originalName,
            editingArtefact.value.name,
            editingArtefact.value.content
        );
        editingArtefact.value = null;
    } catch (e) {
        console.error(e);
    }
}

async function deleteArtefact(filename) {
    await notebookStore.deleteArtefact(filename);
}

// Render table of contents
const renderTableOfContents = () => {
    if (!reportSections.value || reportSections.value.length === 0) return null;

    const renderSection = (section, depth = 0) => {
        return (
            <div key={section.id} class={`toc-section toc-depth-${depth}`}>
                <a
                    href={`#${section.id}`}
                    class="toc-link"
                    onClick={(e) => {
                        e.preventDefault();
                        activeSection.value = section.id;
                        document.getElementById(section.id)?.scrollIntoView({ behavior: 'smooth' });
                    }}
                >
                    {section.title}
                </a>
                {section.children && section.children.length > 0 && (
                    <div class="toc-children">
                        {section.children.map(child => renderSection(child, depth + 1))}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div class="table-of-contents">
            <h3 class="toc-title">Table of Contents</h3>
            {reportSections.value.map(section => renderSection(section))}
        </div>
    );
};

// Scroll to section
const scrollToSection = (sectionId) => {
    activeSection.value = sectionId;
    document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth' });
};

</script>

<template>
    <div class="h-full flex overflow-hidden bg-gray-50 dark:bg-gray-950 relative">
        <!-- PRODUCTION CONSOLE OVERLAY -->
        <transition enter-active-class="transition ease-out duration-300" enter-from-class="opacity-0" enter-to-class="opacity-100" leave-active-class="transition ease-in duration-200" leave-from-class="opacity-100" leave-to-class="opacity-0">
            <div v-if="activeTask" class="absolute inset-0 z-50 bg-white/95 dark:bg-gray-900/95 backdrop-blur-md flex flex-col p-10">
                <div class="max-w-4xl mx-auto w-full flex flex-col h-full animate-in fade-in zoom-in-95 duration-500">
                    <div class="flex items-center justify-between mb-8">
                        <div class="flex items-center gap-6">
                            <div class="p-4 bg-blue-600 rounded-3xl shadow-xl shadow-blue-500/20">
                                <IconAnimateSpin class="w-10 h-10 animate-spin text-white"/>
                            </div>
                            <div>
                                <h2 class="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tighter">{{ activeTask.name }}</h2>
                                <p class="text-sm font-bold text-blue-500 opacity-80 uppercase tracking-widest">{{ activeTask.description }}</p>
                            </div>
                        </div>
                        <div class="text-4xl font-black text-blue-600 font-mono">{{ activeTask.progress }}%</div>
                    </div>

                    <div class="w-full bg-gray-200 dark:bg-gray-800 h-3 rounded-full overflow-hidden mb-10 shadow-inner">
                        <div class="h-full bg-blue-600 transition-all duration-500 progress-bar-animated" :style="{width: activeTask.progress + '%'}"></div>
                    </div>

                    <div class="flex-grow flex flex-col min-h-0 bg-black rounded-3xl shadow-2xl border border-gray-800 overflow-hidden">
                        <div class="px-6 py-3 bg
