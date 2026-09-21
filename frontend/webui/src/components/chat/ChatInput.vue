<script setup>
// ... existing imports ...
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useRouter } from 'vue-router'; 
import { keymap } from '@codemirror/view';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useTasksStore } from '../../stores/tasks';
import { usePromptsStore } from '../../stores/prompts';
import { useNotesStore } from '../../stores/notes';
import { useSkillsStore } from '../../stores/skills';
import placeholderParser from '../../services/placeholderParser';
import { storeToRefs } from 'pinia';
import apiClient from '../../services/api';
import useEventBus from '../../services/eventBus';

import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';
import DropdownSubmenu from '../ui/DropdownMenu/DropdownSubmenu.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';

// Icons
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconClock from '../../assets/icons/IconClock.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconMcp from '../../assets/icons/IconMcp.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconLollms from '../../assets/icons/IconLollms.vue';
import IconUser from '../../assets/icons/IconUser.vue';
import IconToken from '../../assets/icons/IconToken.vue';
import IconSquares2x2 from '../../assets/icons/IconSquares2x2.vue';
import IconCircle from '../../assets/icons/IconCircle.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconWeb from '../../assets/icons/ui/IconWeb.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue'; 
import IconObservation from '../../assets/icons/IconObservation.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue'; 
import IconSettings from '../../assets/icons/IconSettings.vue';
import IconFilePlus from '../../assets/icons/IconPlusCircle.vue';
import IconMap from '../../assets/icons/IconMap.vue';
import IconGoogleDrive from '../../assets/icons/IconGoogleDrive.vue';
import IconCalendar from '../../assets/icons/IconCalendar.vue';
import IconGoogle from '../../assets/icons/IconGoogle.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconGitBranch from '../../assets/icons/ui/IconGitBranch.vue';
import IconCog from '../../assets/icons/IconCog.vue';
import IconAdjustmentsHorizontal from '../../assets/icons/IconAdjustmentsHorizontal.vue';

const discussionsStore = useDiscussionsStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const tasksStore = useTasksStore();
const promptsStore = usePromptsStore();
const notesStore = useNotesStore();
const skillsStore = useSkillsStore();
const { on, off } = useEventBus();
const router = useRouter();

const dStoreRefs = storeToRefs(discussionsStore);
const activeDiscussionArtefacts = computed(() => dStoreRefs.activeDiscussionArtefacts?.value || []);
const loadedContextItems = computed(() => discussionsStore.loadedContextItems || []);
const attachedSkills = computed(() => dStoreRefs.attachedSkills?.value || []);
const activeDiscussion = computed(() => dStoreRefs.activeDiscussion?.value || null);
const generationInProgress = computed(() => dStoreRefs.generationInProgress?.value || false);
const generationState = computed(() => dStoreRefs.generationState?.value || { status: 'idle', details: '' });
const activeDiscussionContextStatus = computed(() => dStoreRefs.activeDiscussionContextStatus?.value || null);
const dataZonesTokensFromContext = computed(() => dStoreRefs.dataZonesTokensFromContext?.value || 0);
const currentModelVisionSupport = computed(() => dStoreRefs.currentModelVisionSupport?.value ?? true);
const activeAiTasks = computed(() => dStoreRefs.activeAiTasks?.value || {});

const { availableRagStores, availableMcpToolsForSelector } = storeToRefs(dataStore);
const { lollmsPrompts, userPromptsByCategory, systemPromptsByZooCategory } = storeToRefs(promptsStore);
const { notes } = storeToRefs(notesStore);
const { skills } = storeToRefs(skillsStore);

const messageText = ref('');
const isUploading = ref(false);
const uploadingMessage = ref('Processing files...');
const fileInput = ref(null);
const imageInput = ref(null);
const isRecording = ref(false);
const currentUploadPdfMode = ref('text_images');
const userPromptSearchTerm = ref('');
const inputTokenCount = ref(0);
let tokenizeInputDebounceTimer = null;
const isDraggingOver = ref(false);
const isAdvancedEditor = ref(false);
const textareaRef = ref(null);

const isWebSearchActive = ref(false); 
const stagedImages = ref([]); 
const user = computed(() => authStore.user);

// --- Generation Parameter Controls (Temperature, Rounds, Reasoning Effort) ---
const isTuningOpen = ref(false);
const tuningMenuRef = ref(null);

const isCustomTemp = ref(localStorage.getItem('lollms_input_custom_temp') === 'true');
const customTemp = ref(parseFloat(localStorage.getItem('lollms_input_temp_val') || '0.7'));

const isCustomRounds = ref(localStorage.getItem('lollms_input_custom_rounds') === 'true');
const customRounds = ref(parseInt(localStorage.getItem('lollms_input_rounds_val') || '20', 10));

const isReasoningEffortActive = ref(
    localStorage.getItem('lollms_input_reasoning_active') !== null
        ? localStorage.getItem('lollms_input_reasoning_active') === 'true'
        : Boolean(user.value?.reasoning_activation || user.value?.reasoning_effort)
);
const reasoningEffort = ref(
    localStorage.getItem('lollms_input_reasoning_effort') || 
    (user.value?.reasoning_effort ? user.value.reasoning_effort.toLowerCase() : 'low')
);

watch(isCustomTemp, (val) => {
    localStorage.setItem('lollms_input_custom_temp', val ? 'true' : 'false');
});
watch(customTemp, (val) => {
    localStorage.setItem('lollms_input_temp_val', String(val));
});
watch(isCustomRounds, (val) => {
    localStorage.setItem('lollms_input_custom_rounds', val ? 'true' : 'false');
});
watch(customRounds, (val) => {
    localStorage.setItem('lollms_input_rounds_val', String(val));
});
watch(isReasoningEffortActive, (val) => {
    localStorage.setItem('lollms_input_reasoning_active', val ? 'true' : 'false');
});
watch(reasoningEffort, (val) => {
    localStorage.setItem('lollms_input_reasoning_effort', val);
});

watch(user, (u) => {
    if (u && localStorage.getItem('lollms_input_reasoning_active') === null) {
        isReasoningEffortActive.value = Boolean(u.reasoning_activation || u.reasoning_effort);
        if (u.reasoning_effort) reasoningEffort.value = u.reasoning_effort.toLowerCase();
    }
});

const isTuningActive = computed(() => {
    return isCustomTemp.value || isCustomRounds.value || isReasoningEffortActive.value;
});

function resetTuningDefaults() {
    isCustomTemp.value = false;
    customTemp.value = 0.7;
    isCustomRounds.value = false;
    customRounds.value = 20;
    isReasoningEffortActive.value = false;
    reasoningEffort.value = 'low';
}

function setReasoningEffort(effort) {
    reasoningEffort.value = effort;
    isReasoningEffortActive.value = true;
}

// --- Reworked Workspace & Knowledge Hub Menu State ---
const isWorkspaceMenuOpen = ref(false);
const workspaceMenuRef = ref(null);
const activeWorkspaceTab = ref('attach'); // 'attach', 'notes', 'skills', 'prompts', 'context'
const noteSearchTerm = ref('');
const skillSearchTerm = ref('');

function openWorkspaceMenu(tab = 'attach') {
    activeWorkspaceTab.value = tab;
    isWorkspaceMenuOpen.value = true;
    isTuningOpen.value = false;
    // Guaranteed fresh fetch of notes and skills whenever menu opens
    notesStore.fetchNotes();
    skillsStore.fetchSkills();
}

const filteredNotes = computed(() => {
    const list = notesStore.notes || [];
    if (!noteSearchTerm.value.trim()) return list;
    const q = noteSearchTerm.value.toLowerCase().trim();
    return list.filter(n => (n.title || '').toLowerCase().includes(q) || (n.content || '').toLowerCase().includes(q));
});

const filteredSkills = computed(() => {
    const list = skillsStore.skills || [];
    if (!skillSearchTerm.value.trim()) return list;
    const q = skillSearchTerm.value.toLowerCase().trim();
    return list.filter(s => (s.name || '').toLowerCase().includes(q) || (s.description || '').toLowerCase().includes(q) || (s.category || '').toLowerCase().includes(q));
});

function isNoteActiveInContext(note) {
    if (!note || !activeDiscussionArtefacts.value) return false;
    return activeDiscussionArtefacts.value.some(a => 
        a.title === note.title && a.artefact_type === 'note' && a.is_loaded
    );
}

function isSkillActiveInContext(skill) {
    if (!skill) return false;
    const inArtefacts = (activeDiscussionArtefacts.value || []).some(a => 
        (a.title === skill.name || a.title === `${skill.name}.md`) && a.artefact_type === 'skill' && a.is_loaded
    );
    const inAttached = (discussionsStore.attachedSkills || []).some(s => s.id === skill.id || s.name === skill.name);
    return inArtefacts || inAttached;
}

async function handleToggleNoteInDiscussion(note) {
    if (!activeDiscussion.value) {
        await discussionsStore.createNewDiscussion();
    }
    const existing = (activeDiscussionArtefacts.value || []).find(a => 
        a.title === note.title && a.artefact_type === 'note'
    );
    if (existing) {
        if (existing.is_loaded) {
            await discussionsStore.unloadArtefactFromContext({
                discussionId: activeDiscussion.value.id,
                artefactTitle: existing.title,
                version: existing.version
            });
            uiStore.addNotification(`Note '${note.title}' excluded from prompt context.`, 'info');
        } else {
            await discussionsStore.loadArtefactToContext({
                discussionId: activeDiscussion.value.id,
                artefactTitle: existing.title,
                version: existing.version
            });
            uiStore.addNotification(`Note '${note.title}' loaded into prompt context.`, 'success');
        }
    } else {
        await discussionsStore.addNoteAsArtefact(note);
    }
}

async function handleToggleSkillInDiscussion(skill) {
    if (!activeDiscussion.value) {
        await discussionsStore.createNewDiscussion();
    }
    const existingArt = (activeDiscussionArtefacts.value || []).find(a => 
        (a.title === skill.name || a.title === `${skill.name}.md`) && a.artefact_type === 'skill'
    );
    if (existingArt) {
        if (existingArt.is_loaded) {
            await discussionsStore.unloadArtefactFromContext({
                discussionId: activeDiscussion.value.id,
                artefactTitle: existingArt.title,
                version: existingArt.version
            });
            uiStore.addNotification(`Skill '${skill.name}' unloaded from context.`, 'info');
        } else {
            await discussionsStore.loadArtefactToContext({
                discussionId: activeDiscussion.value.id,
                artefactTitle: existingArt.title,
                version: existingArt.version
            });
            uiStore.addNotification(`Skill '${skill.name}' loaded into context.`, 'success');
        }
    } else {
        await discussionsStore.addSkillAsArtefact(skill);
    }
}

// --- AMUSING AI VIBE & RPG LOADOUT COCKPIT ---
const isLoadoutModalOpen = ref(false);

const activeBuffs = computed(() => {
    const buffs = [];

    // 1. Reasoning Effort
    if (isReasoningEffortActive.value) {
        const effort = reasoningEffort.value || 'low';
        const descriptions = {
            low: "Snack Break Thinker: Doing a quick sanity check before answering.",
            medium: "Pondering the Orb: Substantial deep analytical chain of thought.",
            high: "Galaxy Brain Mode: Maximum cognitive tokens expended.",
            max: "Cosmic Translucence: Consulting parallel universe nodes."
        };
        buffs.push({
            id: 'reasoning',
            icon: '🧠',
            name: `Reasoning (${effort.toUpperCase()})`,
            type: 'cognitive',
            badge: 'Mental Boost',
            description: descriptions[effort] || "Reasoning effort active.",
            actionText: 'Deactivate',
            action: () => { isReasoningEffortActive.value = false; }
        });
    }

    // 2. Temperature
    if (isCustomTemp.value) {
        const temp = customTemp.value;
        let flavor = "Balanced Coffee (0.7)";
        if (temp < 0.35) flavor = "Ice Cold Logic 🧊 (Zero hallucinations, 100% strict)";
        else if (temp > 1.0) flavor = "Disco Inferno 🌋 (Maximum spicy creativity)";
        buffs.push({
            id: 'temperature',
            icon: '🌡️',
            name: `Spiciness: ${temp.toFixed(2)}`,
            type: 'vibe',
            badge: 'Heat Override',
            description: flavor,
            actionText: 'Reset',
            action: () => { isCustomTemp.value = false; }
        });
    }

    // 3. Rounds
    if (isCustomRounds.value) {
        buffs.push({
            id: 'rounds',
            icon: '⏱️',
            name: `Stamina: ${customRounds.value} Rounds`,
            type: 'limit',
            badge: 'Loop Limit',
            description: customRounds.value > 25 ? "Marathon runner: Will loop until perfected." : "Sprint runner: Bounded reasoning steps.",
            actionText: 'Reset',
            action: () => { isCustomRounds.value = false; }
        });
    }

    // 4. Web Search
    if (isWebSearchActive.value) {
        buffs.push({
            id: 'web',
            icon: '🛰️',
            name: `Orbital Recon (${currentProviderName.value})`,
            type: 'recon',
            badge: 'Live Satellite',
            description: `Live web scouting and claim verification armed via ${currentProviderList.value}.`,
            actionText: 'Disable',
            action: () => toggleWebSearch()
        });
    }

    // 5. Long-Term Memory
    if (user.value?.memory_enabled) {
        buffs.push({
            id: 'memory',
            icon: '🐘',
            name: 'Elephant Memory',
            type: 'memory',
            badge: 'Deep Recall',
            description: 'Cognitive memory active: pulls past facts and automatically forms new associations.',
            actionText: 'Settings',
            action: () => toggleUserPref('memory_enabled')
        });
    }

    // 6. RAG DataStores
    if (ragStoreSelection.value && ragStoreSelection.value.length > 0) {
        buffs.push({
            id: 'rag',
            icon: '🧽',
            name: `Knowledge Sponge (${ragStoreSelection.value.length} DB${ragStoreSelection.value.length > 1 ? 's' : ''})`,
            type: 'rag',
            badge: 'Vectorized Memory',
            description: `Grounding answers in: ${activeRagStoresInfo.value.map(s => s.name).join(', ')}.`,
            actionText: 'Manage',
            action: () => openWorkspaceMenu('context')
        });
    }

    // 7. MCP Tools
    if (mcpToolSelection.value && mcpToolSelection.value.length > 0) {
        buffs.push({
            id: 'mcp',
            icon: '🛠️',
            name: `Swiss Army Arm (${mcpToolSelection.value.length} tools)`,
            type: 'tools',
            badge: 'Cybernetic Tools',
            description: 'Can trigger external function execution via Model Context Protocol.',
            actionText: 'Manage',
            action: () => openWorkspaceMenu('context')
        });
    }

    // 8. Loaded Notes
    const loadedNotesList = (activeDiscussionArtefacts.value || []).filter(a => a.artefact_type === 'note' && a.is_loaded);
    if (loadedNotesList.length > 0) {
        buffs.push({
            id: 'notes',
            icon: '📝',
            name: `Cheat Sheet (${loadedNotesList.length} note${loadedNotesList.length > 1 ? 's' : ''})`,
            type: 'notes',
            badge: 'Direct Reference',
            description: `Loaded: ${loadedNotesList.map(n => n.title).join(', ')}.`,
            actionText: 'View',
            action: () => openWorkspaceMenu('notes')
        });
    }

    // 9. Loaded Skills
    const loadedSkillsList = (activeDiscussionArtefacts.value || []).filter(a => a.artefact_type === 'skill' && a.is_loaded);
    const attachedSkillsList = discussionsStore.attachedSkills || [];
    const totalSkillsCount = loadedSkillsList.length + attachedSkillsList.length;
    if (totalSkillsCount > 0) {
        const skillTitles = [...loadedSkillsList.map(s => s.title), ...attachedSkillsList.map(s => s.name)];
        buffs.push({
            id: 'skills',
            icon: '✨',
            name: `Superpower Capsule (${totalSkillsCount} skill${totalSkillsCount > 1 ? 's' : ''})`,
            type: 'skills',
            badge: '+10 Architecture',
            description: `Trained behaviors: ${skillTitles.join(', ')}.`,
            actionText: 'View',
            action: () => openWorkspaceMenu('skills')
        });
    }

    // 10. Workspace Documents
    const loadedDocsList = (activeDiscussionArtefacts.value || []).filter(a => ['document', 'file', 'code'].includes(a.artefact_type) && a.is_loaded);
    if (loadedDocsList.length > 0) {
        buffs.push({
            id: 'docs',
            icon: '📜',
            name: `Scroll Stash (${loadedDocsList.length} doc${loadedDocsList.length > 1 ? 's' : ''})`,
            type: 'docs',
            badge: 'Active Context',
            description: `Reading: ${loadedDocsList.map(d => d.title).join(', ')}.`,
            actionText: 'View',
            action: () => openWorkspaceMenu('attach')
        });
    }

    // 11. Herd Mode
    if (user.value?.herd_mode_enabled) {
        buffs.push({
            id: 'herd',
            icon: '🐺',
            name: `Wolfpack Consensus (${user.value.herd_rounds || 2} rounds)`,
            type: 'herd',
            badge: 'Multi-Agent',
            description: 'Multiple autonomous AI agents debate and critique before answering.',
            actionText: 'Disable',
            action: () => toggleUserPref('herd_mode_enabled')
        });
    }

    return buffs;
});

const activeBuffsCount = computed(() => activeBuffs.value.length);

const aiCharacterClass = computed(() => {
    const isBigBrain = isReasoningEffortActive.value && ['high', 'max'].includes(reasoningEffort.value);
    const isSpicy = isCustomTemp.value && customTemp.value >= 1.0;
    const isCold = isCustomTemp.value && customTemp.value <= 0.35;
    const isWeb = isWebSearchActive.value;
    const isHerd = user.value?.herd_mode_enabled;
    const hasManyDocs = (activeDiscussionArtefacts.value || []).filter(a => a.is_loaded).length >= 3;
    const hasSkills = (activeDiscussionArtefacts.value || []).some(a => a.artefact_type === 'skill' && a.is_loaded) || (discussionsStore.attachedSkills || []).length > 0;

    if (isHerd) return "Wolfpack Overlord";
    if (isBigBrain && isWeb && (ragStoreSelection.value || []).length > 0) return "Archmage of the Digital Spire";
    if (isBigBrain && hasSkills) return "Senior Polymath Wizard";
    if (isSpicy) return "Caffeinated Chaos Goblin";
    if (isCold && isBigBrain) return "Vulcan Ice Calculator";
    if (hasManyDocs) return "Grand Scroll Archivist";
    if (isWeb) return "Cybernetic Recon Scout";
    if (isBigBrain) return "Zen Master Philosopher";
    if (hasSkills) return "Augmented Cyber-Specialist";
    return "Eager Digital Familiar";
});

const aiVibeEmoji = computed(() => {
    const cls = aiCharacterClass.value;
    if (cls.includes("Archmage")) return "🧙‍♂️";
    if (cls.includes("Wolfpack")) return "🐺";
    if (cls.includes("Chaos Goblin")) return "👺";
    if (cls.includes("Vulcan")) return "🧊";
    if (cls.includes("Archivist")) return "📜";
    if (cls.includes("Scout")) return "🛰️";
    if (cls.includes("Philosopher")) return "🧘";
    if (cls.includes("Wizard")) return "🔮";
    if (cls.includes("Cyber")) return "🤖";
    return "✨";
});

const aiVibeQuote = computed(() => {
    const cls = aiCharacterClass.value;
    if (cls.includes("Archmage")) return "I see through the fabric of the web and synthesize truth from the void.";
    if (cls.includes("Wolfpack")) return "My agents have debated your request and forged a battle-tested response.";
    if (cls.includes("Chaos Goblin")) return "Hold onto your keyboard, we're taking the scenic, unhinged route!";
    if (cls.includes("Vulcan")) return "Emotion is irrelevant. Logical probability of optimal solution: 99.8%.";
    if (cls.includes("Archivist")) return "I have unrolled your ancient scrolls and committed every line to memory.";
    if (cls.includes("Scout")) return "Radar spinning. Pinging satellite constellations for real-time intel.";
    if (cls.includes("Philosopher")) return "I think, therefore I ponder, therefore I generate.";
    return "Ready to assist! Tell me what we are conquering today.";
});

function closeMenusIfOutside(e) {
    if (isTuningOpen.value && tuningMenuRef.value && !tuningMenuRef.value.contains(e.target)) {
        isTuningOpen.value = false;
    }
    if (isWorkspaceMenuOpen.value && workspaceMenuRef.value && !workspaceMenuRef.value.contains(e.target)) {
        isWorkspaceMenuOpen.value = false;
    }
}

const detectedPlaceholders = computed(() => {
    if (!messageText.value || typeof messageText.value !== 'string') return [];
    return placeholderParser.parse(messageText.value);
});

function openFillPlaceholders(autoSend = false) {
    if (detectedPlaceholders.value.length === 0) return;
    uiStore.openModal('fillPlaceholders', {
        promptTemplate: messageText.value,
        onConfirm: (filledText) => {
            messageText.value = filledText;
            adjustTextareaHeight();
            if (autoSend) {
                nextTick(() => {
                    handleSendMessage();
                });
            }
        }
    });
}

async function handleCreateDiscussionWithAttachedArtefacts() {
    if (!activeDiscussion.value) return;
    const titles = groupedAttachedFiles.value.map(g => g.title);
    if (!titles.length) return;
    await discussionsStore.createDiscussionWithArtefacts({
        sourceDiscussionId: activeDiscussion.value.id,
        artefactTitles: titles
    });
}
const isSavedLibraryItem = computed(() => discussionsStore.currentDiscussionId === 'saved');
const hoveredRagStoreId = ref(null);


const providerNames = {
    google: 'Google',
    duckduckgo: 'DDG',
    wikipedia: 'Wiki',
    reddit: 'Reddit',
    stackoverflow: 'SO',
    x: 'X',
    github: 'GitHub'
};

const currentProviderName = computed(() => {
    const providers = user.value?.web_search_providers || [];
    if (providers.length === 0) return 'None';
    if (providers.length === 1) return providerNames[providers[0]] || 'Web';
    return `Multi (${providers.length})`;
});

const currentProviderList = computed(() => {
    return (user.value?.web_search_providers || [])
        .map(p => providerNames[p] || p)
        .join(', ');
});

watch(user, (newUser) => {
    if (newUser) {
        isWebSearchActive.value = !!newUser.web_search_enabled;
    }
}, { immediate: true });

const attachedFiles = computed(() => activeDiscussionArtefacts.value || []);

// Group artefacts by title, showing latest version by default with version selector
const groupedAttachedFiles = computed(() => {
    const groups = {};
    
    // Group all files by title
    (activeDiscussionArtefacts.value || []).forEach(file => {
        if (!groups[file.title]) {
            groups[file.title] = {
                title: file.title,
                artefact_type: file.artefact_type,
                versions: [],
                latest: null,
                isAnyLoaded: false,
                selectedVersion: file.version,
                selectedFile: null
            };
        }
        groups[file.title].versions.push(file);
        if (file.is_loaded) {
            groups[file.title].isAnyLoaded = true;
        }
    });
    
    // Sort versions and determine latest
    Object.values(groups).forEach(group => {
        // Sort by version desc (highest first)
        group.versions.sort((a, b) => b.version - a.version);
        group.latest = group.versions[0];
        // Default to latest version selected
        group.selectedVersion = group.latest.version;
        group.selectedFile = group.latest;
    });
    
    return Object.values(groups);
});

function onVersionSelect(title, version) {
    const group = groupedAttachedFiles.value.find(g => g.title === title);
    if (group) {
        group.selectedVersion = parseInt(version);
        group.selectedFile = group.versions.find(v => v.version === parseInt(version));
    }
}

const isSttActive = computed(() => {
    return !!user.value?.stt_binding_model_name && 
           user.value.stt_binding_model_name.includes('/') && 
           dataStore.availableSttModels.length > 0;
});
const isTtsActive = computed(() => {
    return !!user.value?.tts_binding_model_name && 
           user.value.tts_binding_model_name.includes('/') && 
           dataStore.availableTtsModels.length > 0;
});
const isTtiConfigured = computed(() => {
    return !!user.value?.tti_binding_model_name && 
           user.value.tti_binding_model_name.includes('/') && 
           dataStore.availableTtiModels.length > 0;
});
const isGoogleSearchConfigured = computed(() => !!user.value?.google_api_key && !!user.value?.google_cse_id);

const canEnableHerd = computed(() => {
    if (!user.value) return false;
    const u = user.value;
    if (u.herd_dynamic_mode) {
        return Array.isArray(u.herd_model_pool) && u.herd_model_pool.length > 0;
    }
    const hasPre = Array.isArray(u.herd_precode_participants) && u.herd_precode_participants.length > 0;
    const hasPost = Array.isArray(u.herd_postcode_participants) && u.herd_postcode_participants.length > 0;
    const hasLegacy = Array.isArray(u.herd_participants) && u.herd_participants.length > 0;
    return hasPre || hasPost || hasLegacy;
});

const showContextBar = computed(() => user.value?.show_token_counter && activeDiscussionContextStatus.value);
const maxTokens = computed(() => {
    const activeModel = dataStore.availableLLMModelsGrouped?.flatMap(g => g.items)?.find(m => m.id === user.value?.lollms_model_name);
    const modelCtx = activeModel?.forced_context_size || activeModel?.ctx_size || activeModel?.alias?.forced_context_size || activeModel?.alias?.ctx_size || user.value?.llm_ctx_size;
    if (modelCtx && Number(modelCtx) > 1) {
        return Number(modelCtx);
    }

    const rawMax = activeDiscussionContextStatus.value?.max_tokens;
    if (rawMax && Number(rawMax) > 1) {
        return Number(rawMax);
    }

    return 4096;
});

const totalCurrentTokens = computed(() => {
    // Backend 'current_tokens' represents the last known stable state.
    // We add the 'inputTokenCount' (real-time typing) for a live projection.
    return (activeDiscussionContextStatus.value?.current_tokens || 0) + inputTokenCount.value;
});

const getPercentage = (tokens) => maxTokens.value > 0 ? (tokens / maxTokens.value) * 100 : 0;

const contextParts = computed(() => {
    if (!activeDiscussionContextStatus.value) return [];
    
    // Safety check for zone existence
    const zones = activeDiscussionContextStatus.value.zones || {};
    const sys = zones.system_context?.breakdown || {};
    const history = zones.message_history?.breakdown || {};
    const globalImages = zones.discussion_images?.tokens || 0;
    
    const parts = [];

    // 1. Directives (Indigo): System Prompt + Pruning Summaries
    const directiveTokens = (sys.system_prompt?.tokens || 0) + (sys.pruning_summary?.tokens || 0);
    if (directiveTokens > 0) parts.push({ label: 'Directives', value: directiveTokens, colorClass: 'bg-indigo-600' });

    // 2. Memory (Teal): Long-term facts
    const memoryTokens = sys.memory?.tokens || 0;
    if (memoryTokens > 0) parts.push({ label: 'Memory Bank', value: memoryTokens, colorClass: 'bg-teal-500' });

    // 3. Dynamic Data Zones (Amber): User Prefs + Discussion Zone + Personality data
    const zoneTokens = (sys.user_data_zone?.tokens || 0) + (sys.discussion_data_zone?.tokens || 0) + (sys.personality_data_zone?.tokens || 0);
    if (zoneTokens > 0) parts.push({ label: 'Context Zones', value: zoneTokens, colorClass: 'bg-amber-500' });

    // 4. Workspace Artefacts (Blue): Active documents in workspace
    const artefactTokens = sys.artefacts?.tokens || 0;
    if (artefactTokens > 0) parts.push({ label: 'Workspace Files', value: artefactTokens, colorClass: 'bg-blue-600' });

    // 5. Message Text History (Emerald): Previous conversation text
    const historyTextTokens = history.text_tokens || 0;
    if (historyTextTokens > 0) parts.push({ label: 'Conversation History', value: historyTextTokens, colorClass: 'bg-emerald-600' });

    // 6. All Images (Rose): Message attachments + Global images
    const totalImageTokens = (history.image_tokens || 0) + globalImages;
    if (totalImageTokens > 0) parts.push({ label: 'Visual Data', value: totalImageTokens, colorClass: 'bg-rose-500' });

    // 7. Agentic Scratchpad (Slate): Plan and thoughts
    const scratchpadTokens = sys.scratchpad?.tokens || 0;
    if (scratchpadTokens > 0) parts.push({ label: 'Agent Scratchpad', value: scratchpadTokens, colorClass: 'bg-slate-500' });

    // 8. Live User Input (Violet): The text you are currently typing
    if (inputTokenCount.value > 0) parts.push({ label: 'Current Message Draft', value: inputTokenCount.value, colorClass: 'bg-violet-600' });

    return parts;
});

const totalPercentage = computed(() => getPercentage(totalCurrentTokens.value));
const progressBorderColorClass = computed(() => {
    if (totalPercentage.value >= 100) return 'border-red-600 dark:border-red-500';
    if (totalPercentage.value >= 90) return 'border-red-400 dark:border-red-400';
    if (totalPercentage.value >= 75) return 'border-yellow-500 dark:border-yellow-400';
    return 'border-gray-200 dark:border-gray-700';
});

const ragStoreSelection = computed({
    get: () => activeDiscussion.value?.rag_datastore_ids || [],
    set: (newIds) => { if (activeDiscussion.value) discussionsStore.updateDiscussionRagStores({ discussionId: activeDiscussion.value.id, ragDatastoreIds: newIds }); }
});

const activeRagStoresInfo = computed(() => {
    const ids = ragStoreSelection.value || [];
    if (!ids.length) return [];
    const allStores = [...(dataStore.ownedDataStores || []), ...(dataStore.sharedDataStores || [])];
    return ids.map(id => {
        const found = allStores.find(s => s.id === id);
        return {
            id,
            name: found ? found.name : `DataStore (${id.substring(0, 8)})`,
            mode: user.value?.rag_retrieval_mode || 'hybrid'
        };
    });
});

const mcpToolSelection = computed({
    get: () => activeDiscussion.value?.active_tools || [],
    set: (newIds) => { if (activeDiscussion.value) discussionsStore.updateDiscussionMcps({ discussionId: activeDiscussion.value.id, mcp_tool_ids: newIds }); }
});

const currentActiveTask = computed(() => {
    if (!activeDiscussion.value) return null;
    const tracked = activeAiTasks.value[activeDiscussion.value.id];
    if (!tracked || !tracked.taskId) return null;
    return tasksStore.tasks.find(t => t.id === tracked.taskId) || null;
});

function toggleRagStore(storeId) {
    const current = new Set(ragStoreSelection.value);
    if (current.has(storeId)) current.delete(storeId);
    else current.add(storeId);
    ragStoreSelection.value = Array.from(current);
}

function toggleMcpTool(toolId) {
    const current = new Set(mcpToolSelection.value);
    if (current.has(toolId)) current.delete(toolId);
    else current.add(toolId);
    mcpToolSelection.value = Array.from(current);
}

async function toggleWebSearch() {
    // Check against providers list (plural) as defined in model
    const providers = user.value?.web_search_providers || [];
    if (providers.includes('google') && !isGoogleSearchConfigured.value) {
        uiStore.addNotification("Google Web Search is not configured. Please add your API Key in Settings > User Context.", "error");
        return;
    }

    const newState = !isWebSearchActive.value;
    isWebSearchActive.value = newState; // Optimistic UI update
    
    try {
        await authStore.updateUserPreferences({ web_search_enabled: newState });
    } catch (e) {
        console.error("Failed to save web search preference", e);
        uiStore.addNotification("Failed to save settings.", "error");
        // Revert on failure
        isWebSearchActive.value = !newState;
    }
}

async function toggleUserPref(key) {
    if (!authStore.user) return;
    
    const currentValue = !!authStore.user[key];
    const newValue = !currentValue;
    
    if (key === 'herd_mode_enabled' && !currentValue && !canEnableHerd.value) {
        uiStore.addNotification("Please configure Herd participants in Settings > User Context first.", "warning");
        return;
    }
    
    try {
        // Store action now handles optimistic update and API call internally
        await authStore.updateUserPreferences({ [key]: newValue }, true);
    } catch (e) {
        console.error(`Failed to toggle preference [${key}]:`, e);
        uiStore.addNotification(`Failed to save ${key.replace(/_/g, ' ')} setting.`, "error");
    }
}

function navigateToContextSettings() {
    router.push('/settings?section=context');
}

function handleOpenCreateDatastoreModal() {
    uiStore.openModal('createDataStoreFromArtefacts', {
        discussionId: activeDiscussion.value?.id,
        initialMode: 'create',
        titles: []
    });
}

function handleDragEnterRagChip(storeId) {
    hoveredRagStoreId.value = storeId;
}

function handleDragLeaveRagChip(storeId) {
    if (hoveredRagStoreId.value === storeId) {
        hoveredRagStoreId.value = null;
    }
}

function handleDropOnRagChip(event, targetStoreId, targetStoreName) {
    event.preventDefault();
    event.stopPropagation();
    hoveredRagStoreId.value = null;
    const artefactTitle = event.dataTransfer.getData('text/lollms-artefact-title');
    if (artefactTitle && activeDiscussion.value) {
        uiStore.openModal('createDataStoreFromArtefacts', {
            discussionId: activeDiscussion.value.id,
            titles: [artefactTitle],
            initialMode: 'existing',
            targetDatastoreId: targetStoreId,
            defaultName: targetStoreName
        });
    }
}

function showFeatureInfo(feature) {
    if (feature.id === 'rag') {
        if (ragStoreSelection.value.length > 0) {
            router.push({ path: '/datastores', query: { storeId: ragStoreSelection.value[0] } });
            return;
        } else {
            router.push('/datastores');
            return;
        }
    }
    // We now use a dedicated modal for a richer editorial experience
    uiStore.openModal('featureInfo', feature);
}

function showHiddenFeaturesModal() {
    let content = "";
    hiddenFeatures.value.forEach(feat => {
        content += `### ${feat.modalTitle || feat.label}\n`;
        if (feat.modalDescription) content += `${feat.modalDescription}\n`;
        if (feat.systemPrompt) {
            content += `\n**System Prompt**\n\`\`\`text\n${feat.systemPrompt}\n\`\`\``;
        }
        content += `\n\n---\n\n`;
    });
    
    // Remove trailing separator
    content = content.replace(/\n\n---\n\n$/, '');

    uiStore.openModal('interactiveOutput', {
        title: `Additional Active Features (+${hiddenFeatures.value.length})`,
        content: content
    });
}

const activeFeatures = computed(() => {
    const features = [];
    if (user.value?.herd_mode_enabled) {
        features.push({
            id: 'herd',
            icon: IconUserGroup,
            label: `Herd Mode (${user.value.herd_rounds} rounds)`,
            colorClass: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800',
            title: `Herd Mode Active.`,
            modalTitle: 'Herd Mode Orchestration',
            modalDescription: 'A collaborative multi-agent workflow. Your request is processed by a "Pre-code" crew (Brainstorming), synthesized by a Leader, critiqued by a "Post-code" crew, and refined into a final answer.',
            systemPrompt: '(Dynamic Context) The system orchestrates multiple agent interactions. It injects specific system prompts for each agent (e.g., "You are a creative thinker...") and manages the debate history context.'
        });
    }
    if (ragStoreSelection.value.length > 0) {
        const storeNames = activeRagStoresInfo.value.map(s => s.name);
        const labelText = storeNames.length === 1 
            ? `RAG: ${storeNames[0]}` 
            : `RAG: ${storeNames.length} DBs (${storeNames.join(', ')})`;
        features.push({ 
            id: 'rag', 
            icon: IconDatabase, 
            label: labelText, 
            colorClass: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800', 
            title: `Active Knowledge Bases: ${storeNames.join(', ')}`,
            modalTitle: 'RAG (Retrieval-Augmented Generation)',
            modalDescription: `Active Knowledge Bases: ${storeNames.join(', ')}. Strategy: ${user.value?.rag_retrieval_mode || 'hybrid'}. Retrieves relevant document chunks to ground the AI in factual data.`,
            systemPrompt: '## Context from Data Stores\n[Chunk 1] content...\n[Chunk 2] content...'
        });
    }
    if (mcpToolSelection.value.length > 0) {
        features.push({ 
            id: 'tools', 
            icon: IconMcp, 
            label: 'Tools', 
            colorClass: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800', 
            title: `${mcpToolSelection.value.length} Tool(s) Active`,
            modalTitle: 'MCP Tools',
            modalDescription: `Active Tools: ${mcpToolSelection.value.length}. Allows the AI to execute external functions (e.g., file system access, API calls) via the Model Context Protocol.`,
            systemPrompt: '(Tool Definitions injected as JSON Schema). The model outputs tool calls which are executed by the system.'
        });
    }
    if (isWebSearchActive.value) {
        features.push({
            id: 'web_search',
            icon: IconGlobeAlt,
            label: currentProviderName.value,
            colorClass: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
            title: `Web Search Active (${currentProviderName.value}).`,
            modalTitle: 'Web Search',
            modalDescription: `Provider: ${currentProviderName.value}. The AI can search the internet for real-time information if it determines the query requires it.`,
            systemPrompt: 'User: "..." Do you need to search? -> [Search Action] -> ## Web Search Context:\n### Title\nContent...'
        });
    }
    if (isReasoningEffortActive.value) {
        features.push({ 
            id: 'thinking', 
            icon: IconThinking, 
            label: `Reasoning (${reasoningEffort.value || 'low'})`, 
            colorClass: 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800', 
            title: `Reasoning Effort: ${reasoningEffort.value || 'low'}.`,
            modalTitle: 'Thinking / Reasoning Effort',
            modalDescription: `Enables Chain-of-Thought reasoning. Effort: ${reasoningEffort.value || 'low'}.`,
            systemPrompt: `Reasoning effort set to '${reasoningEffort.value || 'low'}'.`
        });
    }
    if (isCustomTemp.value) {
        features.push({ 
            id: 'temperature', 
            icon: IconAdjustmentsHorizontal, 
            label: `Temp: ${customTemp.value}`, 
            colorClass: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800', 
            title: `Custom Temperature: ${customTemp.value}`,
            modalTitle: 'Custom Temperature',
            modalDescription: `Sampling temperature overridden to ${customTemp.value}.`,
            systemPrompt: `Sampling temperature set to ${customTemp.value}.`
        });
    }
    if (isCustomRounds.value) {
        features.push({ 
            id: 'rounds', 
            icon: IconClock, 
            label: `Rounds: ${customRounds.value}`, 
            colorClass: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800', 
            title: `Max Reasoning Rounds: ${customRounds.value}`,
            modalTitle: 'Max Reasoning Rounds',
            modalDescription: `Agentic reasoning loop budget limited to ${customRounds.value} rounds.`,
            systemPrompt: `max_nb_rounds set to ${customRounds.value}.`
        });
    }
    if (user.value?.image_annotation_enabled) {
        features.push({ 
            id: 'annotation', 
            icon: IconObservation, 
            label: 'Annotate', 
            colorClass: 'text-pink-600 dark:text-pink-400 bg-pink-50 dark:bg-pink-900/20 border-pink-200 dark:border-pink-800', 
            title: 'Image Annotation Enabled.',
            modalTitle: 'Image Annotation',
            modalDescription: 'Enables the AI to detect objects in images and provide coordinates.',
            systemPrompt: '## Image Annotation: Use <annotate>[JSON]</annotate> for bounding boxes/points.'
        });
    }
    if (user.value?.memory_enabled) {
        features.push({ 
            id: 'memory', 
            icon: IconThinking, 
            label: user.value.auto_memory_enabled ? 'Memory (Auto)' : 'Memory', 
            colorClass: 'text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-900/20 border-teal-200 dark:border-teal-800', 
            title: 'Long-Term Memory Active.',
            modalTitle: 'Long-Term Memory',
            modalDescription: 'Injects stored memories into context and allows the AI to save new facts.',
            systemPrompt: '## Long-Term Memory Bank\n[Memory #1] ...\n## Memory Management\nManage memories using these tags:\n- Add: <new_memory>...'
        });
    }
    if (user.value?.skills_library_enabled) {
        features.push({ 
            id: 'skills_lib', 
            icon: IconDatabase, 
            label: 'Skill Auto-Search', 
            colorClass: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800', 
            title: 'Skill Auto-Search Active.',
            modalTitle: 'Skill Auto-Search',
            modalDescription: 'Automatically searches your Skills library and injects relevant skills into the context.',
            systemPrompt: '## Relevant Skills Retrieved:\n--- Skill: Name ---\n...'
        });
    }
    if (user.value?.skills_building_enabled) {
        features.push({ 
            id: 'skills_build', 
            icon: IconPencil, 
            label: 'Skill Builder', 
            colorClass: 'text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-900/20 border-sky-200 dark:border-sky-800', 
            title: 'Skill Builder Enabled.',
            modalTitle: 'Skill Builder',
            modalDescription: 'Allows the AI to save new skills to your library based on conversations.',
            systemPrompt: '## Skill Building: Use <skill title="..." description="..." category="...">content</skill> to remember reusable code patterns or rules.'
        });
    }
    if (currentModelVisionSupport.value) {
        features.push({ 
            id: 'vision', 
            icon: IconEye, 
            label: 'Vision', 
            colorClass: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800', 
            title: 'Vision Supported.',
            modalTitle: 'Computer Vision',
            modalDescription: 'The currently selected model supports image input analysis.',
            systemPrompt: '(Images are encoded and passed directly to the model\'s visual encoder).'
        });
    }
    if (user.value?.image_generation_enabled) {
        features.push({ 
            id: 'img_gen', 
            icon: IconPhoto, 
            label: 'ImgGen', 
            colorClass: 'text-fuchsia-600 dark:text-fuchsia-400 bg-fuchsia-50 dark:bg-fuchsia-900/20 border-fuchsia-200 dark:border-fuchsia-800', 
            title: 'Image Generation Enabled.',
            modalTitle: 'Image Generation',
            modalDescription: 'Allows the AI to generate images from text descriptions.',
            systemPrompt: `## Image Gen: Use <generate_image width="W" height="H" n="N">prompt</generate_image>.${user.value.image_generation_system_prompt ? '\n(Plus user system prompt)' : ''}`
        });
    }
    if (user.value?.image_editing_enabled) {
        features.push({ 
            id: 'img_edit', 
            icon: IconPencil, 
            label: 'ImgEdit', 
            colorClass: 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-900/20 border-violet-200 dark:border-violet-800', 
            title: 'Image Editing Enabled.',
            modalTitle: 'Image Editing',
            modalDescription: 'Allows the AI to modify existing images.',
            systemPrompt: '## Image Edit: Use <edit_image source_index="-1" strength="0.8">prompt</edit_image>.'
        });
    }
    if (user.value?.slide_maker_enabled) {
        features.push({ 
            id: 'slides', 
            icon: IconPresentationChartBar, 
            label: 'Slides', 
            colorClass: 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800', 
            title: 'Slide Maker Enabled.',
            modalTitle: 'Slide Maker',
            modalDescription: 'Allows the AI to generate presentations (PPTX/PDF).',
            systemPrompt: '## Slides: Use <generate_slides><Slide>desc</Slide></generate_slides>.'
        });
    }
    if (user.value?.note_generation_enabled) {
        features.push({ 
            id: 'notes', 
            icon: IconFileText, 
            label: 'Note Building', 
            colorClass: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800', 
            title: 'Note Building Enabled.',
            modalTitle: 'Note Building',
            modalDescription: 'Allows the AI to create structured research notes saved directly to your library.',
            systemPrompt: '## Notes: Use <note title="Title">...</note> for structured data.'
        });
    }
    if (user.value?.book_generation_enabled) {
        features.push({ 
            id: 'books', 
            icon: IconBookOpen, 
            label: 'Book Building', 
            colorClass: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-900/20 border-rose-200 dark:border-rose-800', 
            title: 'Book Building Enabled.',
            modalTitle: 'Digital Books',
            modalDescription: 'Allows the AI to write and format complete digital books with automatic PDF conversion.',
            systemPrompt: '## Books: Use <artifact type="book" title="Title">...</artifact> using semantic HTML5.'
        });
    }
    if (user.value?.artefacts_enabled) {
        features.push({ 
            id: 'artefacts', 
            icon: IconFileText, 
            label: 'Artefacts', 
            colorClass: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800', 
            title: 'Artefacts Generation Enabled.',
            modalTitle: 'Artefacts',
            modalDescription: 'Enables high-fidelity modular file, code, and document creation inside your workspace.',
            systemPrompt: 'Allows generation of structured workspace artefacts.'
        });
    }
    if (user.value && user.value.inline_widgets_enabled === true) {
        features.push({ 
            id: 'widgets', 
            icon: IconCpuChip, 
            label: 'Widgets', 
            colorClass: 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800', 
            title: 'Widget Building Enabled.',
            modalTitle: 'Interactive Widgets',
            modalDescription: 'Allows the AI to create live, interactive HTML components for visualizations and tools.',
            systemPrompt: '## Widgets: Use <lollms_inline title="...">...</lollms_inline> for HTML apps.'
        });
    }
    if (isTtsActive.value || isSttActive.value) {
        features.push({ 
            id: 'audio', 
            icon: IconMicrophone, 
            label: 'Audio', 
            colorClass: 'text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-900/20 border-cyan-200 dark:border-cyan-800', 
            title: 'Audio Features Enabled.',
            modalTitle: 'Audio Features',
            modalDescription: 'Speech-to-Text (STT) and/or Text-to-Speech (TTS) are configured and active.',
            systemPrompt: '(Handled by audio processing modules, no text prompt injection)'
        });
    }
    if (user.value?.street_view_enabled && user.value?.google_api_key) {
        features.push({
            id: 'street_view',
            icon: IconMap,
            label: 'Street View',
            colorClass: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800',
            title: 'Street View Enabled.',
            modalTitle: 'Google Street View',
            modalDescription: 'Allows the AI to retrieve street view images for a given location using Google Maps Static API.',
            systemPrompt: '## Street View: Use <street_view>location</street_view>.'
        });
    }
    if (user.value?.scheduler_enabled) {
        features.push({
            id: 'scheduler',
            icon: IconClock,
            label: 'Scheduler',
            colorClass: 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800',
            title: 'Task Scheduler Enabled.',
            modalTitle: 'Proactive Scheduler',
            modalDescription: 'Allows the AI to schedule recurrent tasks using CRON syntax.',
            systemPrompt: '## Scheduler: Use <schedule_task name="..." cron="...">Prompt</schedule_task>.'
        });
    }
    if (user.value?.google_drive_enabled) {
        features.push({
            id: 'gdrive',
            icon: IconGoogleDrive,
            label: 'Drive',
            colorClass: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
            title: 'Google Drive Access.',
            modalTitle: 'Google Drive',
            modalDescription: 'Allows reading and listing files from your Google Drive.',
            systemPrompt: '## Drive: <google_drive_list>id</google_drive_list>'
        });
    }
    if (user.value?.google_calendar_enabled) {
        features.push({
            id: 'gcal',
            icon: IconCalendar,
            label: 'Calendar',
            colorClass: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
            title: 'Google Calendar Access.',
            modalTitle: 'Google Calendar',
            modalDescription: 'Allows managing events on your Google Calendar.',
            systemPrompt: '## Calendar: <calendar_add>...</calendar_add>'
        });
    }
    return features;
});

const showHeaderRow = computed(() => showContextBar.value || activeFeatures.value.length > 0);
const maxVisibleBadges = 5;
const visibleFeatures = computed(() => activeFeatures.value.slice(0, maxVisibleBadges));
const hiddenFeatures = computed(() => activeFeatures.value.slice(maxVisibleBadges));

function openStagedImageViewer(startIndex) { uiStore.openImageViewer({ imageList: stagedImages.value.map((img) => ({ src: img.previewUrl, prompt: `Uploaded image: ${img.file.name}` })), startIndex }); }
function viewAttachedSkill(skill) { uiStore.openModal('skillEditor', { skill }); }

function viewLoadedContextItem(item) {
    if (item.type === 'skill') {
        uiStore.openModal('skillEditor', { skill: item });
    } else {
        uiStore.openModal('noteEditor', { note: item });
    }
}

function viewAttachedFile(file) {
    if (!activeDiscussion.value || !file?.title) return;

    // Ensure data zone is visible and focus on the workspace document
    uiStore.openWorkspaceArtefact(file.title);
}
function getGroupExtension(group) {
    const title = group?.title || '';
    const parts = title.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
}

function isGroupExecutable(group) {
    const ext = getGroupExtension(group);
    return ['html', 'mermaid', 'svg', 'py', 'js', 'json', 'python', 'javascript'].includes(ext);
}

function getGroupExecuteTitle(group) {
    const ext = getGroupExtension(group);
    if (['html', 'mermaid', 'svg'].includes(ext)) return 'Show Render / Preview';
    return 'Execute Code';
}

async function handleExecuteGroup(group) {
    const targetFile = group.selectedFile || group.latest;
    if (!targetFile) return;

    uiStore.addNotification("Fetching content for execution...", "info");
    try {
        const data = await discussionsStore.fetchArtefactContent({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: targetFile.title,
            version: targetFile.version,
            strategy: 'raw'
        });

        let content = '';
        if (typeof data === 'string') {
            content = data;
        } else if (data && typeof data === 'object') {
            content = data.content ?? '';
        }

        const ext = getGroupExtension(group);
        const title = targetFile.title;
        const cleanContent = content.trim();

        if (ext === 'html') {
            const blob = new Blob([cleanContent], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank');
            setTimeout(() => URL.revokeObjectURL(url), 60000);
            uiStore.addNotification("HTML opened in a new tab.", "success");
        } else if (ext === 'svg') {
            const htmlContent = `<div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 1rem;">${cleanContent}</div>`;
            uiStore.openModal('interactiveOutput', { htmlContent, title: `SVG Preview: ${title}`, contentType: 'svg' });
        } else if (ext === 'mermaid') {
            uiStore.openModal('interactiveOutput', {
                title: `Mermaid Diagram: ${title}`,
                contentType: 'mermaid',
                sourceCode: cleanContent
            });
        } else if (ext === 'js' || ext === 'javascript') {
            const createDynamicFn = window.Function;
            try {
                let capturedOutput = '';
                const originalLog = console.log;
                console.log = (...args) => { capturedOutput += args.map(String).join(' ') + '\n'; };

                const result = (new createDynamicFn(cleanContent))();
                if (result !== undefined && result !== null) {
                    capturedOutput += String(result);
                }
                console.log = originalLog;

                const outputText = capturedOutput.trim() || 'Execution finished with no output.';
                uiStore.openModal('interactiveOutput', { content: `### Execution Output\n\`\`\`\n${outputText}\n\`\`\``, title: `JS Output: ${title}` });
            } catch (e) {
                uiStore.openModal('interactiveOutput', { content: `### Execution Error\n\`\`\`\n${e.toString()}\n\`\`\``, title: `JS Error: ${title}` });
            }
        } else if (ext === 'py' || ext === 'python') {
            const pyodideStore = (await import('../../stores/pyodide')).usePyodideStore();
            uiStore.addNotification("Loading Python environment...", "info");
            if (!pyodideStore.isReady) {
                await pyodideStore.initialize();
            }

            const canvasId = `code-canvas-${Date.now()}`;
            const result = await pyodideStore.runCode(cleanContent, {
                canvasSelector: `#${canvasId}`
            });

            const outputText = result.error || result.output || (result.image || result.usesCanvas ? '' : 'Execution finished with no output.');

            if (result.usesCanvas) {
                uiStore.openModal('interactiveOutput', { canvasId: canvasId, title: `Python Canvas: ${title}` });
            } else if (result.image) {
                const htmlContent = `<div style="text-align: center;"><img src="data:image/png;base64,${result.image}" class="max-w-full h-auto mx-auto" /></div>`;
                uiStore.openModal('interactiveOutput', { htmlContent, title: `Python Output: ${title}` });
            } else {
                uiStore.openModal('interactiveOutput', { content: `### Python Output\n\`\`\`\n${outputText}\n\`\`\``, title: `Python Output: ${title}` });
            }
        } else {
            uiStore.openModal('interactiveOutput', { content: cleanContent, title: `Viewer: ${title}` });
        }
    } catch (e) {
        console.error("Execution failed:", e);
        uiStore.addNotification("Execution failed: " + e.message, "error");
    }
}

async function toggleArtefactLoad(file) { 
    if (!activeDiscussion.value) return; 
    if (file.is_loaded) 
        await discussionsStore.unloadArtefactFromContext({ 
            discussionId: activeDiscussion.value.id, 
            artefactTitle: file.title, 
            version: file.version,
            artefactType: file.artefact_type
        }); 
    else 
        await discussionsStore.loadArtefactToContext({ 
            discussionId: activeDiscussion.value.id, 
            artefactTitle: file.title, 
            version: file.version 
        }); 
}
async function removeArtefact(file) { 
    if (!activeDiscussion.value) return; 
    const confirmed = await uiStore.showConfirmation({ 
        title: 'Delete Document', 
        message: `Are you sure you want to permanently delete "${file.title}" and all its versions from this discussion?`, 
        confirmText: 'Delete',
        danger: true
    }); 

    if (confirmed.confirmed) {
        // We don't 'await' here so the modal closes and the chip disappears instantly 
        // while the background request in the store handles the rest.
        discussionsStore.deleteArtefact({ 
            discussionId: activeDiscussion.value.id, 
            artefactTitle: file.title 
        }); 
    }
}
function removeStagedImage(index) { const removed = stagedImages.value.splice(index, 1)[0]; if (removed && removed.previewUrl) URL.revokeObjectURL(removed.previewUrl); }
function triggerFileUpload(mode = 'text_and_embedded_images') { currentUploadPdfMode.value = mode; fileInput.value?.click(); }
function triggerImageUpload() { imageInput.value?.click(); }
async function handleFilesInput(files) {
    if (files.length === 0) return;
    const images = files.filter(f => f.type.startsWith('image/'));
    const others = files.filter(f => !f.type.startsWith('image/'));
    if (images.length > 0) images.forEach(file => { stagedImages.value.push({ file, previewUrl: URL.createObjectURL(file) }); });
    if (others.length > 0) {
        if (!activeDiscussion.value) await discussionsStore.createNewDiscussion();
        if (activeDiscussion.value) { 
            isUploading.value = true; 
            uploadingMessage.value = 'Adding files to workspace...';

            const hintTimer = setTimeout(() => {
                uploadingMessage.value = 'Preparing ingestion environment (might be installing required libraries)...';
            }, 5000);

            try { 
                await Promise.all(others.map(file => discussionsStore.addArtefact({ discussionId: activeDiscussion.value.id, file, extractImages: true, auto_load: true, pdfMode: currentUploadPdfMode.value }))); 
                await discussionsStore.fetchArtefacts(activeDiscussion.value.id);
                await discussionsStore.fetchContextStatus(activeDiscussion.value.id);
            } finally { 
                clearTimeout(hintTimer);
                isUploading.value = false; 
            } 
        }
    }
}
async function handleFileUpload(event) { const files = Array.from(event.target.files || []); await handleFilesInput(files); event.target.value = ''; }
async function handleImageUpload(event) { const files = Array.from(event.target.files || []); await handleFilesInput(files); event.target.value = ''; }
async function handleDrop(event) { event.stopPropagation(); isDraggingOver.value = false; const files = Array.from(event.dataTransfer.files); if (files.length > 0) { await handleFilesInput(files); } }
async function handlePaste(event) {
    event.stopPropagation();
    const items = (event.clipboardData || window.clipboardData).items;
    const imageFiles = [];
    for (let i = 0; i < items.length; i++) { if (items[i].type.indexOf("image") !== -1) { const blob = items[i].getAsFile(); if (blob) { const extension = (blob.type.split('/')[1] || 'png').toLowerCase().replace('jpeg', 'jpg'); imageFiles.push(new File([blob], `pasted_image_${Date.now()}.${extension}`, { type: blob.type })); } } }
    if (imageFiles.length > 0) { event.preventDefault(); await handleFilesInput(imageFiles); }
}
async function handleImportFromInternet() { if (!activeDiscussion.value) { uiStore.addNotification('Please start a discussion first.', 'warning'); return; } uiStore.openModal('importFromInternet', { discussionId: activeDiscussion.value.id, mode: 'url' }); }
async function handleCreateManualArtefact() { if (!activeDiscussion.value) { uiStore.addNotification('Please start a discussion first.', 'warning'); return; } uiStore.openModal('createArtefact', { discussionId: activeDiscussion.value.id }); }
function handlePromptSelection(content) {
    const placeholders = placeholderParser.parse(content);
    if (placeholders.length > 0) {
        uiStore.openModal('fillPlaceholders', {
            promptTemplate: content,
            onConfirm: (filled) => {
                messageText.value = (messageText.value ? messageText.value + '\n' : '') + filled;
                adjustTextareaHeight();
            }
        });
    } else {
        messageText.value = (messageText.value ? messageText.value + '\n' : '') + content;
        adjustTextareaHeight();
    }
}

const filteredUserPromptsByCategory = computed(() => {
    if (!userPromptSearchTerm.value) return userPromptsByCategory.value;
    const term = userPromptSearchTerm.value.toLowerCase();
    const result = {};
    for (const [cat, prompts] of Object.entries(userPromptsByCategory.value)) { const filtered = prompts.filter(p => p.name.toLowerCase().includes(term)); if (filtered.length > 0) result[cat] = filtered; }
    return result;
});

let mediaRecorder = null;
let audioChunks = [];
async function toggleRecording() {
    if (isRecording.value) { mediaRecorder?.stop(); isRecording.value = false; } else {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
            mediaRecorder.onstop = async () => { const audioBlob = new Blob(audioChunks, { type: 'audio/wav' }); const text = await discussionsStore.transcribeAudio(audioBlob); if (text) messageText.value += (messageText.value ? ' ' : '') + text; stream.getTracks().forEach(track => track.stop()); };
            mediaRecorder.start();
            isRecording.value = true;
        } catch (err) { uiStore.addNotification('Microphone access denied.', 'error'); }
    }
}

async function handleSendMessage() {
    if (generationInProgress.value) return;
    const text = messageText.value.trim();
    if (!text && attachedFiles.value.length === 0 && stagedImages.value.length === 0) return;

    if (detectedPlaceholders.value.length > 0) {
        openFillPlaceholders(true);
        return;
    }

    // Reset height after sending
    if (textareaRef.value) textareaRef.value.style.height = '42px';
    const imagesToUpload = stagedImages.value.map(item => item.file);
    const localPreviews = stagedImages.value.map(item => item.previewUrl);
    messageText.value = '';
    inputTokenCount.value = 0;
    stagedImages.value = []; 
    try { 
        await discussionsStore.sendMessage({ 
            prompt: text, 
            image_server_paths: [], 
            localImageUrls: localPreviews, 
            image_files: imagesToUpload, 
            webSearchEnabled: isWebSearchActive.value,
            temperature: isCustomTemp.value ? Number(customTemp.value) : null,
            max_nb_rounds: isCustomRounds.value ? parseInt(customRounds.value, 10) : null,
            reasoning_effort: isReasoningEffortActive.value ? (reasoningEffort.value || 'low') : 'none'
        }); 
    } catch(err) { 
        console.error("SendMessage failed:", err); 
        uiStore.addNotification('Failed to send message.', 'error'); 
        messageText.value = text; 
        imagesToUpload.forEach((file, i) => { stagedImages.value.push({ file, previewUrl: localPreviews[i] }); }); 
    }
}

function handleKeyDown(event) { 
    if (event.key === 'Enter') {
        if (!event.shiftKey) {
            // Regular Enter = Validate/Send
            event.preventDefault();
            handleSendMessage();
        }
        // Shift+Enter falls through to native behavior (New Line)
    }
}

const adjustTextareaHeight = () => {
    const el = textareaRef.value;
    if (el) {
        // Reset height to calculate true scrollHeight
        el.style.height = 'auto';

        // Cap growth at a reasonable height (e.g., 300px)
        const newHeight = Math.min(el.scrollHeight, 300);
        el.style.height = newHeight + 'px';
    }
};
async function fetchInputTokenCount(text) { if (!text.trim()) { inputTokenCount.value = 0; return; } try { const response = await apiClient.post('/api/discussions/tokenize', { text }); inputTokenCount.value = response.data.tokens; } catch (error) {} }
function handleStopGeneration() { discussionsStore.stopGeneration(); }

watch(messageText, (newText) => { 
    clearTimeout(tokenizeInputDebounceTimer); 
    if (!newText.trim()) { 
        inputTokenCount.value = 0; 
    } else if (showContextBar.value) { 
        // Increased debounce from 500ms to 1200ms to reduce backend load while typing
        tokenizeInputDebounceTimer = setTimeout(() => fetchInputTokenCount(newText), 1200); 
    } 
});

onMounted(() => { 
    promptsStore.fetchPrompts(); 
    notesStore.fetchNotes();
    skillsStore.fetchSkills();
    if (dataStore.availableRagStores.length === 0) dataStore.fetchDataStores(); 
    if (dataStore.availableMcpToolsForSelector.length === 0) dataStore.fetchMcpTools(); 
    on('files-dropped-in-chat', handleFilesInput); 
    on('files-pasted-in-chat', handleFilesInput); 
    document.addEventListener('mousedown', closeMenusIfOutside);
});
onUnmounted(() => { 
    off('files-dropped-in-chat', handleFilesInput); 
    off('files-pasted-in-chat', handleFilesInput); 
    stagedImages.value.forEach(img => URL.revokeObjectURL(img.previewUrl)); 
    document.removeEventListener('mousedown', closeMenusIfOutside);
});
</script>

<template>
    <div class="shrink-0 bg-white/95 dark:bg-gray-800/95 backdrop-blur border-t dark:border-gray-700 shadow-lg relative">

        <!-- Vision Warning -->
        <div v-if="!currentModelVisionSupport && stagedImages.length > 0" class="px-4 py-1.5 bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800 text-[10px] text-yellow-700 dark:text-yellow-300 flex items-center gap-2">
            <IconInfo class="w-3.5 h-3.5 shrink-0" />
            <p>Model lacks vision support. Your uploaded images will be ignored.</p>
        </div>

        <!-- Context Bar / Feature Badges Row -->
        <!-- Fixed: Removed overflow-x-auto to prevent clipping the tooltip, added relative z-40 -->
        <div v-if="showHeaderRow" class="px-3 py-1 bg-gray-50 dark:bg-gray-900 border-b dark:border-gray-700 relative z-40">
             <div class="max-w-4xl mx-auto flex items-center gap-3">
                <template v-if="showContextBar">
                    <div @click="uiStore.openModal('contextViewer')" 
                         class="grow flex items-center gap-3 cursor-pointer group/context select-none active:scale-[0.99] transition-transform relative">
                        
                        <!-- ── [NEW] Rich Tooltip Overlay ── -->
                        <!-- Fixed: Increased z-index to 50 and ensured background is solid enough to read -->
                        <div class="absolute bottom-full left-0 mb-4 w-80 opacity-0 translate-y-2 pointer-events-none group-hover/context:opacity-100 group-hover/context:translate-y-0 group-hover/context:pointer-events-auto transition-all duration-300 z-50">
                            <div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.3)] overflow-hidden p-4 space-y-3">
                                <div class="flex justify-between items-center border-b dark:border-gray-800 pb-2 mb-2">
                                    <span class="text-[10px] font-black uppercase tracking-widest text-gray-400">Context Usage</span>
                                    <span class="text-xs font-mono font-bold" :class="totalPercentage > 90 ? 'text-red-500' : 'text-blue-500'">{{ Math.round(totalPercentage) }}%</span>
                                </div>
                                <div class="space-y-2.5">
                                    <div v-for="part in contextParts" :key="part.label" class="flex items-center justify-between group/item">
                                        <div class="flex items-center gap-2">
                                            <div class="w-2.5 h-2.5 rounded-full shadow-sm" :class="part.colorClass"></div>
                                            <span class="text-[11px] font-bold text-gray-700 dark:text-gray-300">{{ part.label }}</span>
                                        </div>
                                        <div class="flex items-center gap-2">
                                            <span class="text-[10px] font-mono text-gray-500 dark:text-gray-400">{{ part.value.toLocaleString() }}</span>
                                            <span class="text-[9px] text-gray-400 w-8 text-right">{{ Math.round(getPercentage(part.value)) }}%</span>
                                        </div>
                                    </div>
                                </div>
                                <div class="pt-2 border-t dark:border-gray-800 flex justify-between items-center text-[9px] font-black uppercase text-gray-400 tracking-tighter">
                                    <span>Total Used</span>
                                    <span class="font-mono text-gray-600 dark:text-gray-200">{{ totalCurrentTokens.toLocaleString() }} / {{ maxTokens.toLocaleString() }}</span>
                                </div>
                            </div>
                            <!-- Tooltip Arrow -->
                            <div class="absolute left-6 top-full -mt-1 w-3 h-3 bg-white dark:bg-gray-900 border-r border-b border-gray-200 dark:border-gray-700 transform rotate-45"></div>
                        </div>

                        <div class="flex items-center gap-1 text-gray-500 shrink-0 group-hover/context:text-blue-500 transition-colors">
                            <IconToken class="w-3.5 h-3.5" />
                            <span class="text-[10px] font-black uppercase tracking-tight hidden sm:inline">Context</span>
                        </div>

                        <!-- Progress Bar with improved contrast and segment dividers -->
                        <div :class="['grow h-2.5 rounded-full overflow-hidden flex border dark:border-gray-800 transition-all shadow-inner', totalPercentage >= 100 ? 'bg-red-600/20 group-hover/context:ring-red-500/50 border-red-500' : 'bg-gray-200 dark:bg-gray-700 group-hover/context:ring-blue-400/50', progressBorderColorClass]">
                            <div v-for="part in contextParts" :key="part.label" 
                                :class="[totalPercentage >= 100 ? 'bg-red-600' : part.colorClass, 'h-full transition-all duration-500 ease-out border-r border-black/5 last:border-0']" 
                                :style="{ width: `${getPercentage(part.value)}%` }" 
                            ></div>
                        </div>

                        <div class="font-mono text-[10px] text-gray-500 whitespace-nowrap shrink-0 group-hover/context:text-blue-600 dark:group-hover/context:text-blue-400 transition-colors">
                            <span class="font-bold">{{ totalCurrentTokens }}</span><span class="opacity-30 mx-1">/</span><span>{{ maxTokens }}</span>
                        </div>
                    </div>
                </template>
                <div v-else class="grow"></div> 

                <div class="h-3 w-px bg-gray-300 dark:bg-gray-700 mx-1 shrink-0"></div>

                <!-- ── [AMUSING] AI VIBE & RPG LOADOUT COCKPIT TRIGGER ── -->
                <button 
                    @click="isLoadoutModalOpen = true"
                    class="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-purple-50 hover:bg-purple-100 dark:bg-purple-950/40 dark:hover:bg-purple-900/50 border border-purple-200 dark:border-purple-800 text-purple-700 dark:text-purple-300 text-[10px] font-black uppercase tracking-wider shadow-2xs hover:scale-105 transition-all cursor-pointer select-none shrink-0"
                    title="Click for AI Vibe Check & Character Loadout"
                >
                    <span class="text-xs">{{ aiVibeEmoji }}</span>
                    <span class="truncate max-w-[120px] sm:max-w-[170px]">{{ aiCharacterClass }}</span>
                    <span class="px-1 py-0.2 rounded bg-purple-200/80 dark:bg-purple-800 text-[9px] font-mono">{{ activeBuffsCount }} buffs</span>
                </button>
            </div>
        </div>

        <div class="p-3 sm:p-4 max-w-4xl mx-auto space-y-3">
            <!-- Placeholder Detection Pill -->
            <div v-if="detectedPlaceholders.length > 0" class="flex items-center justify-between px-3.5 py-2 bg-amber-50/90 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/70 rounded-xl text-xs text-amber-900 dark:text-amber-200 shadow-xs animate-in fade-in slide-in-from-bottom-1">
                <div class="flex items-center gap-2 min-w-0">
                    <IconSparkles class="w-4 h-4 text-amber-500 shrink-0 animate-pulse" />
                    <span class="font-bold truncate">
                        {{ detectedPlaceholders.length }} placeholder{{ detectedPlaceholders.length > 1 ? 's' : '' }} detected:
                        <span class="font-mono text-[11px] opacity-80">
                            {{ detectedPlaceholders.map(p => p.name).join(', ') }}
                        </span>
                    </span>
                </div>
                <button 
                    @click="openFillPlaceholders(false)" 
                    type="button" 
                    class="px-2.5 py-1 bg-amber-500 hover:bg-amber-600 text-white font-bold text-[10px] uppercase tracking-wider rounded-lg shadow-sm transition-all active:scale-95 shrink-0 ml-2 cursor-pointer flex items-center gap-1"
                >
                    <span>Fill Values</span>
                    <IconChevronRight class="w-3 h-3" />
                </button>
            </div>

            <!-- SPECIAL SELECTION ZONE -->
            <div v-if="stagedImages.length > 0 || attachedFiles.length > 0 || attachedSkills.length > 0 || loadedContextItems.length > 0 || activeRagStoresInfo.length > 0" class="flex flex-wrap gap-2 max-h-40 overflow-y-auto custom-scrollbar p-3 mb-2 bg-gray-100 dark:bg-gray-900/60 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-700 transition-all">

                <!-- Active RAG Database Indicators (Drop Target) -->
                <div v-for="ragStore in activeRagStoresInfo" :key="`rag-chip-${ragStore.id}`"
                     @dragover.prevent
                     @dragenter="handleDragEnterRagChip(ragStore.id)"
                     @dragleave="handleDragLeaveRagChip(ragStore.id)"
                     @drop="handleDropOnRagChip($event, ragStore.id, ragStore.name)"
                     @click="router.push({ path: '/datastores', query: { storeId: ragStore.id } })"
                     class="flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-bold border-2 border-green-500/80 bg-green-50 text-green-800 dark:bg-green-950/40 dark:border-green-800 dark:text-green-300 shadow-sm hover:shadow-md hover:border-green-600 hover:scale-[1.02] cursor-pointer transition-all group/rag"
                     :class="{
                        'ring-4 ring-green-400 scale-105 bg-green-100 dark:bg-green-900/80 border-green-600 animate-pulse': hoveredRagStoreId === ragStore.id
                     }"
                     :title="`Drop artefact here to vectorize into '${ragStore.name}', or click to inspect in Data Studio`">
                    <IconDatabase class="w-4 h-4 text-green-600 dark:text-green-400 shrink-0 group-hover/rag:scale-110 transition-transform" />
                    <span class="truncate max-w-[180px] underline-offset-2 group-hover/rag:underline">
                        {{ ragStore.name }}
                    </span>
                    <span class="text-[9px] font-mono opacity-60 uppercase">({{ ragStore.mode }})</span>
                    <button @click.stop="toggleRagStore(ragStore.id)" class="cursor-pointer text-green-600 hover:text-red-500 dark:text-green-400 dark:hover:text-red-400 transition-colors ml-1 p-0.5 rounded-full hover:bg-green-100 dark:hover:bg-green-900/60" title="Detach database from chat">
                        <IconXMark class="w-3.5 h-3.5" />
                    </button>
                </div>

                <div v-for="(img, index) in stagedImages" :key="`staged-img-${index}`" 
                     @click="openStagedImageViewer(index)"
                     class="relative w-16 h-16 group rounded-lg overflow-hidden border-2 transition-all shadow-sm cursor-pointer border-blue-500 hover:scale-105"
                     :class="{'grayscale opacity-60': !currentModelVisionSupport}">
                    <img :src="img.previewUrl" class="w-full h-full object-cover" />
                    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1">
                        <button @click.stop="removeStagedImage(index)" class="text-white hover:text-red-400 p-0.5" title="Remove"><IconXMark class="w-5 h-5" /></button>
                    </div>
                </div>

                <!-- Unified Artefact Chips (Grouped by Title with Version Selector, Draggable to RAG) -->
                <div v-for="group in groupedAttachedFiles" :key="group.title"
                     draggable="true"
                     @dragstart="$event.dataTransfer.setData('text/lollms-artefact-title', group.title)"
                     class="flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-bold border-2 transition-all duration-200 shadow-sm group/file cursor-grab active:cursor-grabbing hover:scale-[1.02]"
                     :class="[
                        group.isAnyLoaded
                            ? (group.artefact_type === 'note' ? 'border-amber-500 bg-amber-50 text-amber-700 dark:border-amber-900/30' : 
                               group.artefact_type === 'skill' ? 'border-emerald-500 bg-emerald-50 text-emerald-700 dark:border-emerald-900/30' :
                               'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-900/30')
                            : 'border-gray-300 bg-gray-50 dark:bg-gray-800 text-gray-400 opacity-50'
                     ]"
                     :title="`Drag to green RAG database chip to vectorize, or click title to open workspace`">
                    
                    <!-- Icon based on registered custom types -->
                    <IconPencil v-if="group.artefact_type === 'note'" class="w-4 h-4 text-amber-600" />
                    <IconSparkles v-else-if="group.artefact_type === 'skill'" class="w-4 h-4 text-emerald-600" />
                    <IconFileText v-else class="w-4 h-4 text-blue-600" />

                    <!-- Title -->
                    <span @click.stop="viewAttachedFile(group.latest)" class="truncate max-w-[150px] cursor-pointer hover:underline decoration-2" :title="`Open Workspace: ${group.title}`">
                        {{ group.title }}
                    </span>

                    <!-- Version Selector (if multiple versions) -->
                    <div v-if="group.versions.length > 1" class="relative flex items-center">
                        <select 
                            v-model="group.selectedVersion"
                            @click.stop
                            @change="onVersionSelect(group.title, $event.target.value)"
                            class="bg-transparent border-none text-[9px] font-mono font-bold text-inherit focus:ring-0 p-0 pr-3 cursor-pointer opacity-80 hover:opacity-100 appearance-none"
                        >
                            <option v-for="v in group.versions" :key="v.version" :value="v.version" class="text-gray-800 dark:text-gray-200">
                                v{{ v.version }}
                            </option>
                        </select>
                        <span class="text-[8px] pointer-events-none opacity-60 ml-0.5 -mr-0.5">▼</span>
                    </div>
                    <span v-else class="text-[9px] font-mono opacity-60">v{{ group.latest.version }}</span>

                    <div class="h-3 w-px bg-gray-300 dark:bg-gray-600 mx-1"></div>

                    <!-- Execute Button (Visual Cue in attached chips list) -->
                    <button v-if="isGroupExecutable(group)" @click.stop="handleExecuteGroup(group)" class="cursor-pointer hover:scale-110 transition-transform text-blue-500 hover:text-green-500 mr-1" :title="getGroupExecuteTitle(group)">
                        <IconPlayCircle class="w-4 h-4" />
                    </button>

                    <!-- Load/Unload Toggle (applies to selected version) -->
                    <button v-if="!isSavedLibraryItem" @click.stop="toggleArtefactLoad(group.selectedFile || group.latest)" :title="(group.selectedFile || group.latest).is_loaded ? 'Exclude from context' : 'Include in context'" class="cursor-pointer hover:scale-110 transition-transform">
                        <IconCheckCircle v-if="(group.selectedFile || group.latest).is_loaded" class="w-4 h-4 text-green-500"/>
                        <IconCircle v-else class="w-4 h-4" />
                    </button>

                    <!-- Remove Button -->
                    <button @click.stop="removeArtefact(group.latest)" class="cursor-pointer text-gray-400 hover:text-red-500 transition-colors ml-1" title="Permanently delete">
                        <IconXMark class="w-3.5 h-3.5" />
                    </button>
                </div>

                <!-- Fork / New Chat with Attached Artefacts Action Button -->
                <button 
                    v-if="groupedAttachedFiles.length > 0 && !isSavedLibraryItem"
                    @click.stop="handleCreateDiscussionWithAttachedArtefacts"
                    class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-bold border-2 border-purple-400 dark:border-purple-800/80 bg-purple-50 text-purple-800 dark:bg-purple-950/40 dark:text-purple-300 shadow-xs hover:shadow-md hover:scale-105 transition-all cursor-pointer group/fork"
                    title="Start a fresh conversation pre-loaded with all these active documents"
                >
                    <IconGitBranch class="w-3.5 h-3.5 text-purple-600 dark:text-purple-400 group-hover/fork:rotate-45 transition-transform" />
                    <span>New Chat with {{ groupedAttachedFiles.length }} File{{ groupedAttachedFiles.length > 1 ? 's' : '' }}</span>
                </button>

                <!-- Attached Skills (Staged) -->
                <div v-for="skill in attachedSkills" :key="skill.id" 
                     class="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border border-teal-200 bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:border-teal-800 dark:text-teal-300 transition-all duration-200 shadow-sm">
                    <button @click="viewAttachedSkill(skill)" class="flex items-center gap-2 hover:opacity-80">
                        <IconSparkles class="w-3.5 h-3.5" />
                        <span class="truncate max-w-[150px] font-bold">{{ skill.name }}</span>
                    </button>
                    <button @click="discussionsStore.detachSkill(skill.id)" class="text-teal-400 hover:text-red-500 transition-colors ml-1" title="Remove Skill"><IconXMark class="w-3.5 h-3.5" /></button>
                </div>

            </div>

            <!-- Active Generation / Background Task Status Pill -->
            <div v-if="generationInProgress || currentActiveTask || isUploading" 
                 class="flex items-center justify-between px-3.5 py-1.5 bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200/80 dark:border-blue-800/60 rounded-xl text-xs text-blue-800 dark:text-blue-300 shadow-xs animate-in fade-in slide-in-from-bottom-1">
                <div class="flex items-center gap-2.5 min-w-0">
                    <IconAnimateSpin class="w-4 h-4 animate-spin text-blue-600 dark:text-blue-400 shrink-0" />
                    <span v-if="isUploading" class="truncate font-semibold">{{ uploadingMessage }}</span>
                    <span v-else-if="currentActiveTask" class="truncate font-semibold">{{ currentActiveTask.name }} ({{ currentActiveTask.progress }}%)...</span>
                    <span v-else class="truncate font-semibold">{{ generationState.details || 'AI is generating response...' }}</span>
                </div>
                <button v-if="generationInProgress" @click="handleStopGeneration" class="text-[10px] font-black uppercase tracking-wider text-red-500 hover:text-red-600 hover:underline shrink-0 ml-3 py-0.5 px-1.5 rounded bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-900">
                    Stop
                </button>
            </div>

            <!-- Input Controls -->
            <div class="flex items-end gap-2 bg-gray-50 dark:bg-gray-900/50 p-2 rounded-2xl border border-gray-200 dark:border-gray-700 focus-within:border-blue-500/50 focus-within:ring-4 focus-within:ring-blue-500/10 transition-all duration-200 shadow-sm relative">

                <div class="pb-1 pl-1 flex items-center gap-1.5 shrink-0">
                    <!-- ── REWORKED TABBED WORKSPACE & KNOWLEDGE HUB MENU ── -->
                    <div class="relative" ref="workspaceMenuRef">
                        <button 
                            type="button" 
                            @click="isWorkspaceMenuOpen = !isWorkspaceMenuOpen" 
                            class="btn-icon bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 w-9 h-9 flex items-center justify-center rounded-xl transition-all shadow-sm border dark:border-gray-700 relative active:scale-95 cursor-pointer"
                            :class="{
                                'text-blue-600 dark:text-blue-400 border-blue-400 dark:border-blue-600 bg-blue-50/60 dark:bg-blue-900/30': isWorkspaceMenuOpen,
                                'text-gray-500': !isWorkspaceMenuOpen
                            }"
                            title="Workspace Hub & Knowledge Injection"
                        >
                            <IconPlus class="w-4 h-4" />
                            <span v-if="ragStoreSelection.length > 0 || mcpToolSelection.length > 0 || loadedContextItems.length > 0" class="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-blue-500 rounded-full border-2 border-white dark:border-gray-800"></span>
                        </button>

                        <!-- Tabbed Popover Menu -->
                        <Transition
                            enter-active-class="transition ease-out duration-150"
                            enter-from-class="opacity-0 translate-y-2 scale-95"
                            enter-to-class="opacity-100 translate-y-0 scale-100"
                            leave-active-class="transition ease-in duration-100"
                            leave-from-class="opacity-100 translate-y-0 scale-100"
                            leave-to-class="opacity-0 translate-y-2 scale-95"
                        >
                            <div 
                                v-if="isWorkspaceMenuOpen" 
                                class="absolute bottom-full left-0 mb-3 w-88 sm:w-[420px] bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-2xl overflow-hidden z-50 text-gray-800 dark:text-gray-100 flex flex-col max-h-[82vh]"
                            >
                                <!-- Tab Switcher Header -->
                                <div class="px-2 pt-2 pb-1 border-b dark:border-gray-800 bg-gray-50/80 dark:bg-gray-950/60 flex items-center gap-1 overflow-x-auto custom-scrollbar shrink-0 select-none">
                                    <button 
                                        type="button" 
                                        @click="openWorkspaceMenu('attach')"
                                        class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1 shrink-0 cursor-pointer"
                                        :class="activeWorkspaceTab === 'attach' ? 'bg-white dark:bg-gray-800 text-blue-600 shadow-xs' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                                    >
                                        <span>📎 Ingest</span>
                                    </button>
                                    <button 
                                        type="button" 
                                        @click="openWorkspaceMenu('notes')"
                                        class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1 shrink-0 cursor-pointer"
                                        :class="activeWorkspaceTab === 'notes' ? 'bg-white dark:bg-gray-800 text-amber-600 shadow-xs' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                                    >
                                        <span>📝 Notes</span>
                                        <span class="text-[9px] px-1 py-0.2 rounded-full bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 font-mono">{{ notes.length }}</span>
                                    </button>
                                    <button 
                                        type="button" 
                                        @click="openWorkspaceMenu('skills')"
                                        class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1 shrink-0 cursor-pointer"
                                        :class="activeWorkspaceTab === 'skills' ? 'bg-white dark:bg-gray-800 text-teal-600 shadow-xs' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                                    >
                                        <span>✨ Skills</span>
                                        <span class="text-[9px] px-1 py-0.2 rounded-full bg-teal-100 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 font-mono">{{ skills.length }}</span>
                                    </button>
                                    <button 
                                        type="button" 
                                        @click="openWorkspaceMenu('prompts')"
                                        class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1 shrink-0 cursor-pointer"
                                        :class="activeWorkspaceTab === 'prompts' ? 'bg-white dark:bg-gray-800 text-purple-600 shadow-xs' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                                    >
                                        <span>🎟️ Prompts</span>
                                    </button>
                                    <button 
                                        type="button" 
                                        @click="openWorkspaceMenu('context')"
                                        class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1 shrink-0 cursor-pointer"
                                        :class="activeWorkspaceTab === 'context' ? 'bg-white dark:bg-gray-800 text-green-600 shadow-xs' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                                    >
                                        <span>⚙️ Context</span>
                                    </button>
                                </div>

                                <!-- Tab 1: Attach & Ingest -->
                                <div v-if="activeWorkspaceTab === 'attach'" class="p-3 space-y-3 overflow-y-auto custom-scrollbar">
                                    <div class="text-[10px] font-black uppercase tracking-wider text-gray-400 px-1">Document & Media Ingestion</div>
                                    <div class="grid grid-cols-2 gap-2">
                                        <button @click="triggerFileUpload('as_is')" class="p-2.5 rounded-xl border border-gray-100 dark:border-gray-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/20 text-left transition-colors flex items-center gap-2.5 group cursor-pointer">
                                            <IconFolder class="w-4 h-4 text-emerald-500 shrink-0" />
                                            <div class="min-w-0"><p class="text-xs font-bold truncate text-gray-800 dark:text-gray-200">Native File</p><p class="text-[9px] text-gray-400">Preserve as-is</p></div>
                                        </button>
                                        <button @click="triggerFileUpload('text_images')" class="p-2.5 rounded-xl border border-gray-100 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-blue-950/20 text-left transition-colors flex items-center gap-2.5 group cursor-pointer">
                                            <IconFileText class="w-4 h-4 text-blue-500 shrink-0" />
                                            <div class="min-w-0"><p class="text-xs font-bold truncate text-gray-800 dark:text-gray-200">Text + Pages</p><p class="text-[9px] text-gray-400">PDF / DOCX layout</p></div>
                                        </button>
                                        <button @click="triggerFileUpload('data')" class="p-2.5 rounded-xl border border-gray-100 dark:border-gray-800 hover:bg-green-50 dark:hover:bg-green-950/20 text-left transition-colors flex items-center gap-2.5 group cursor-pointer">
                                            <IconDatabase class="w-4 h-4 text-green-500 shrink-0" />
                                            <div class="min-w-0"><p class="text-xs font-bold truncate text-gray-800 dark:text-gray-200">Data Tables</p><p class="text-[9px] text-gray-400">CSV / DB tables</p></div>
                                        </button>
                                        <button @click="triggerImageUpload" class="p-2.5 rounded-xl border border-gray-100 dark:border-gray-800 hover:bg-purple-50 dark:hover:bg-purple-950/20 text-left transition-colors flex items-center gap-2.5 group cursor-pointer">
                                            <IconPhoto class="w-4 h-4 text-purple-500 shrink-0" />
                                            <div class="min-w-0"><p class="text-xs font-bold truncate text-gray-800 dark:text-gray-200">Images</p><p class="text-[9px] text-gray-400">Attach for vision</p></div>
                                        </button>
                                        <button @click="handleCreateManualArtefact" class="p-2.5 rounded-xl border border-gray-100 dark:border-gray-800 hover:bg-orange-50 dark:hover:bg-orange-950/20 text-left transition-colors flex items-center gap-2.5 group cursor-pointer">
                                            <IconPencil class="w-4 h-4 text-orange-500 shrink-0" />
                                            <div class="min-w-0"><p class="text-xs font-bold truncate text-gray-800 dark:text-gray-200">Create Blank</p><p class="text-[9px] text-gray-400">Write in workspace</p></div>
                                        </button>
                                        <button @click="handleImportFromInternet" class="p-2.5 rounded-xl border border-gray-100 dark:border-gray-800 hover:bg-cyan-50 dark:hover:bg-cyan-950/20 text-left transition-colors flex items-center gap-2.5 group cursor-pointer">
                                            <IconWeb class="w-4 h-4 text-cyan-500 shrink-0" />
                                            <div class="min-w-0"><p class="text-xs font-bold truncate text-gray-800 dark:text-gray-200">Import from Internet</p><p class="text-[9px] text-gray-400">Web, Wiki, Arxiv, YouTube, etc.</p></div>
                                        </button>
                                    </div>
                                </div>

                                <!-- Tab 2: Notes Hub -->
                                <div v-else-if="activeWorkspaceTab === 'notes'" class="p-3 space-y-3 flex flex-col grow min-h-0">
                                    <div class="flex items-center justify-between gap-2 shrink-0">
                                        <input 
                                            v-model="noteSearchTerm" 
                                            type="text" 
                                            placeholder="Filter notes..." 
                                            class="input-field !py-1 text-xs grow"
                                        />
                                        <router-link to="/notes-studio" @click="isWorkspaceMenuOpen = false" class="btn btn-secondary btn-xs shrink-0 flex items-center gap-1" title="Open Notes Studio">
                                            <IconPencil class="w-3 h-3" />
                                            <span>Studio</span>
                                        </router-link>
                                    </div>

                                    <div class="overflow-y-auto custom-scrollbar space-y-1 grow max-h-72">
                                        <div v-if="filteredNotes.length === 0" class="text-center py-8 text-xs text-gray-400 italic">
                                            {{ noteSearchTerm ? 'No matching notes found.' : 'No notes saved yet. Create your first note in Notes Studio!' }}
                                        </div>
                                        <div 
                                            v-for="note in filteredNotes" 
                                            :key="note.id"
                                            @click="handleToggleNoteInDiscussion(note)"
                                            class="p-2.5 rounded-xl border transition-all flex items-center justify-between gap-3 cursor-pointer group"
                                            :class="isNoteActiveInContext(note) ? 'bg-amber-50/80 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800 shadow-xs' : 'border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/60'"
                                        >
                                            <div class="flex items-center gap-2.5 min-w-0">
                                                <div class="w-7 h-7 rounded-lg bg-amber-100 dark:bg-amber-900/40 text-amber-600 flex items-center justify-center shrink-0">
                                                    <IconPencil class="w-3.5 h-3.5" />
                                                </div>
                                                <div class="min-w-0">
                                                    <p class="text-xs font-bold truncate text-gray-800 dark:text-gray-100">{{ note.title || 'Untitled Note' }}</p>
                                                    <p class="text-[9px] text-gray-400 truncate">{{ (note.content || '').substring(0, 50) }}...</p>
                                                </div>
                                            </div>
                                            <div class="shrink-0 flex items-center gap-1">
                                                <span v-if="isNoteActiveInContext(note)" class="px-2 py-0.5 rounded-md text-[9px] font-black uppercase bg-amber-500 text-white shadow-2xs">Loaded</span>
                                                <span v-else class="px-2 py-0.5 rounded-md text-[9px] font-bold uppercase bg-gray-100 dark:bg-gray-700 text-gray-500 group-hover:text-amber-600">+ Add</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Tab 3: Skills Hub -->
                                <div v-else-if="activeWorkspaceTab === 'skills'" class="p-3 space-y-3 flex flex-col grow min-h-0">
                                    <div class="flex items-center justify-between gap-2 shrink-0">
                                        <input 
                                            v-model="skillSearchTerm" 
                                            type="text" 
                                            placeholder="Filter skills..." 
                                            class="input-field !py-1 text-xs grow"
                                        />
                                        <router-link to="/skills-studio" @click="isWorkspaceMenuOpen = false" class="btn btn-secondary btn-xs shrink-0 flex items-center gap-1" title="Open Skills Studio">
                                            <IconSparkles class="w-3 h-3" />
                                            <span>Studio</span>
                                        </router-link>
                                    </div>

                                    <div class="overflow-y-auto custom-scrollbar space-y-1 grow max-h-72">
                                        <div v-if="filteredSkills.length === 0" class="text-center py-8 text-xs text-gray-400 italic">
                                            {{ skillSearchTerm ? 'No matching skills found.' : 'No skills in library. Create one in Skills Studio or install from Zoo!' }}
                                        </div>
                                        <div 
                                            v-for="skill in filteredSkills" 
                                            :key="skill.id"
                                            @click="handleToggleSkillInDiscussion(skill)"
                                            class="p-2.5 rounded-xl border transition-all flex items-center justify-between gap-3 cursor-pointer group"
                                            :class="isSkillActiveInContext(skill) ? 'bg-teal-50/80 dark:bg-teal-950/40 border-teal-300 dark:border-teal-800 shadow-xs' : 'border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/60'"
                                        >
                                            <div class="flex items-center gap-2.5 min-w-0">
                                                <div class="w-7 h-7 rounded-lg bg-teal-100 dark:bg-teal-900/40 text-teal-600 flex items-center justify-center shrink-0">
                                                    <IconSparkles class="w-3.5 h-3.5" />
                                                </div>
                                                <div class="min-w-0">
                                                    <div class="flex items-center gap-1.5">
                                                        <p class="text-xs font-bold truncate text-gray-800 dark:text-gray-100">{{ skill.name }}</p>
                                                        <span class="px-1 py-0.2 rounded text-[8px] font-bold uppercase font-mono" :class="skill.is_system ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300' : 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300'">
                                                            {{ skill.is_system ? 'System' : 'Personal' }}
                                                        </span>
                                                    </div>
                                                    <p class="text-[9px] text-gray-400 truncate">{{ skill.description || skill.category || 'AI capability capsule' }}</p>
                                                </div>
                                            </div>
                                            <div class="shrink-0 flex items-center gap-1">
                                                <span v-if="isSkillActiveInContext(skill)" class="px-2 py-0.5 rounded-md text-[9px] font-black uppercase bg-teal-500 text-white shadow-2xs">Equipped</span>
                                                <span v-else class="px-2 py-0.5 rounded-md text-[9px] font-bold uppercase bg-gray-100 dark:bg-gray-700 text-gray-500 group-hover:text-teal-600">+ Equip</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Tab 4: Prompts -->
                                <div v-else-if="activeWorkspaceTab === 'prompts'" class="p-3 space-y-3 overflow-y-auto custom-scrollbar max-h-72">
                                    <div class="text-[10px] font-black uppercase tracking-wider text-gray-400 px-1">Prompt Templates</div>
                                    <div class="space-y-1">
                                        <div v-for="p in lollmsPrompts" :key="p.id" @click="handlePromptSelection(p.content); isWorkspaceMenuOpen = false;" class="p-2 rounded-xl hover:bg-purple-50 dark:hover:bg-purple-950/30 cursor-pointer border border-transparent hover:border-purple-200 text-xs">
                                            <p class="font-bold text-gray-800 dark:text-gray-200">{{ p.name }}</p>
                                            <p class="text-[9px] text-gray-400 truncate">{{ p.description }}</p>
                                        </div>
                                    </div>
                                </div>

                                <!-- Tab 5: Context & RAG -->
                                <div v-else-if="activeWorkspaceTab === 'context'" class="p-3 space-y-3 overflow-y-auto custom-scrollbar max-h-72">
                                    <div class="text-[10px] font-black uppercase tracking-wider text-gray-400 px-1">Active RAG Knowledge Stores</div>
                                    <div class="space-y-1">
                                        <button @click.stop="handleOpenCreateDatastoreModal" class="w-full text-left p-2 rounded-xl text-green-600 font-bold text-xs hover:bg-green-50 dark:hover:bg-green-950/20 border border-dashed border-green-300">
                                            + Create New DataStore
                                        </button>
                                        <button v-for="store in availableRagStores" :key="store.id" @click.stop="toggleRagStore(store.id)" class="w-full text-left p-2 rounded-xl flex items-center justify-between text-xs border" :class="ragStoreSelection.includes(store.id) ? 'bg-green-50 dark:bg-green-950/30 border-green-300 font-bold text-green-700' : 'border-gray-100 dark:border-gray-800'">
                                            <span class="truncate pr-2">{{ store.name }}</span>
                                            <IconCheckCircle v-if="ragStoreSelection.includes(store.id)" class="w-4 h-4 text-green-500 shrink-0" />
                                        </button>
                                    </div>

                                    <div class="text-[10px] font-black uppercase tracking-wider text-gray-400 px-1 pt-2 border-t dark:border-gray-800">MCP Cybernetic Tools</div>
                                    <div class="space-y-1">
                                        <div v-for="group in availableMcpToolsForSelector" :key="group.label" class="space-y-1">
                                            <span class="text-[9px] font-bold text-gray-400 uppercase px-1">{{ group.label }}</span>
                                            <button v-for="tool in group.items" :key="tool.id" @click.stop="toggleMcpTool(tool.id)" class="w-full text-left p-2 rounded-xl flex items-center justify-between text-xs border" :class="mcpToolSelection.includes(tool.id) ? 'bg-purple-50 dark:bg-purple-950/30 border-purple-300 font-bold text-purple-700' : 'border-gray-100 dark:border-gray-800'">
                                                <span class="truncate pr-2">{{ tool.name }}</span>
                                                <IconCheckCircle v-if="mcpToolSelection.includes(tool.id)" class="w-4 h-4 text-purple-500 shrink-0" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </Transition>
                    </div>

                    <!-- Generation Controls (Temperature, Rounds, Reasoning Effort) Popover -->
                    <div class="relative" ref="tuningMenuRef">
                        <button 
                            type="button" 
                            @click="isTuningOpen = !isTuningOpen"
                            class="btn-icon bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 w-9 h-9 flex items-center justify-center rounded-xl transition-all shadow-sm border dark:border-gray-700 relative active:scale-95 cursor-pointer"
                            :class="{
                                'text-purple-600 dark:text-purple-400 border-purple-400 dark:border-purple-600 bg-purple-50/60 dark:bg-purple-900/30': isTuningActive,
                                'text-gray-500': !isTuningActive
                            }"
                            title="Generation Parameters (Temperature, Rounds, Reasoning Effort)"
                        >
                            <IconAdjustmentsHorizontal class="w-4 h-4" />
                            <span v-if="isTuningActive" class="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-purple-500 rounded-full border-2 border-white dark:border-gray-800 animate-pulse"></span>
                        </button>

                        <!-- Floating Tuning Popover Panel -->
                        <Transition
                            enter-active-class="transition ease-out duration-150"
                            enter-from-class="opacity-0 translate-y-2 scale-95"
                            enter-to-class="opacity-100 translate-y-0 scale-100"
                            leave-active-class="transition ease-in duration-100"
                            leave-from-class="opacity-100 translate-y-0 scale-100"
                            leave-to-class="opacity-0 translate-y-2 scale-95"
                        >
                            <div 
                                v-if="isTuningOpen"
                                class="absolute bottom-full left-0 mb-3 w-80 sm:w-88 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-2xl p-4 space-y-4 z-50 text-gray-800 dark:text-gray-100"
                            >
                                <!-- Popover Header -->
                                <div class="flex items-center justify-between border-b dark:border-gray-800 pb-2.5">
                                    <div class="flex items-center gap-2">
                                        <IconAdjustmentsHorizontal class="w-4 h-4 text-purple-500" />
                                        <span class="text-xs font-black uppercase tracking-wider text-gray-800 dark:text-gray-100">Generation Controls</span>
                                    </div>
                                    <button 
                                        type="button" 
                                        @click="resetTuningDefaults" 
                                        class="text-[10px] font-bold text-gray-400 hover:text-red-500 hover:underline transition-colors cursor-pointer"
                                        title="Reset parameters to model and server defaults"
                                    >
                                        Reset Defaults
                                    </button>
                                </div>

                                <!-- 1. Reasoning Effort (Thinking) -->
                                <div class="space-y-2">
                                    <div class="flex items-center justify-between">
                                        <div class="flex items-center gap-1.5">
                                            <IconThinking class="w-4 h-4 text-indigo-500" />
                                            <span class="text-xs font-bold">Reasoning Effort</span>
                                        </div>
                                        <button 
                                            type="button" 
                                            @click="isReasoningEffortActive = !isReasoningEffortActive" 
                                            :class="[isReasoningEffortActive ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200']"
                                            :title="isReasoningEffortActive ? 'Deactivate thinking' : 'Activate thinking (defaults to low)'"
                                        >
                                            <span :class="[isReasoningEffortActive ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200']"></span>
                                        </button>
                                    </div>

                                    <!-- Effort Selector (Pills) -->
                                    <div v-if="isReasoningEffortActive" class="grid grid-cols-4 gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-xl text-xs animate-in fade-in">
                                        <button 
                                            v-for="effort in ['low', 'medium', 'high', 'max']" 
                                            :key="effort"
                                            type="button"
                                            @click="setReasoningEffort(effort)"
                                            class="py-1 px-1.5 rounded-lg font-bold text-[10px] uppercase transition-all capitalize cursor-pointer text-center"
                                            :class="reasoningEffort === effort ? 'bg-white dark:bg-gray-700 text-indigo-600 dark:text-indigo-400 shadow-xs' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'"
                                        >
                                            {{ effort }}
                                        </button>
                                    </div>
                                    <p class="text-[10px] text-gray-400">
                                        {{ isReasoningEffortActive ? `Model will reason with ${reasoningEffort.toUpperCase()} effort.` : 'Thinking deactivated (model responds directly).' }}
                                    </p>
                                </div>

                                <!-- 2. Temperature -->
                                <div class="space-y-2 border-t dark:border-gray-800 pt-3">
                                    <div class="flex items-center justify-between">
                                        <div class="flex items-center gap-1.5">
                                            <span class="text-xs font-bold">Temperature</span>
                                            <span class="text-[10px] font-mono text-gray-400">
                                                {{ isCustomTemp ? customTemp.toFixed(2) : '(Default)' }}
                                            </span>
                                        </div>
                                        <button 
                                            type="button" 
                                            @click="isCustomTemp = !isCustomTemp" 
                                            :class="[isCustomTemp ? 'bg-purple-600' : 'bg-gray-200 dark:bg-gray-700', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200']"
                                            :title="isCustomTemp ? 'Deactivate custom temperature (use model default)' : 'Activate custom temperature'"
                                        >
                                            <span :class="[isCustomTemp ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200']"></span>
                                        </button>
                                    </div>

                                    <div v-if="isCustomTemp" class="space-y-2 animate-in fade-in">
                                        <div class="flex items-center gap-3">
                                            <input 
                                                type="range" 
                                                v-model.number="customTemp" 
                                                min="0.0" 
                                                max="2.0" 
                                                step="0.05" 
                                                class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-purple-600"
                                            />
                                            <input 
                                                type="number" 
                                                v-model.number="customTemp" 
                                                min="0.0" 
                                                max="2.0" 
                                                step="0.05" 
                                                class="input-field !py-0.5 !px-1.5 text-xs w-16 text-center font-mono font-bold"
                                            />
                                        </div>
                                        <div class="flex items-center justify-between text-[10px] text-gray-400">
                                            <button type="button" @click="customTemp = 0.2" class="hover:text-purple-500 cursor-pointer">Precise (0.2)</button>
                                            <button type="button" @click="customTemp = 0.7" class="hover:text-purple-500 cursor-pointer">Balanced (0.7)</button>
                                            <button type="button" @click="customTemp = 1.2" class="hover:text-purple-500 cursor-pointer">Creative (1.2)</button>
                                        </div>
                                    </div>
                                    <p v-else class="text-[10px] text-gray-400">
                                        Deactivated. Model will use its native default temperature.
                                    </p>
                                </div>

                                <!-- 3. Number of Rounds -->
                                <div class="space-y-2 border-t dark:border-gray-800 pt-3">
                                    <div class="flex items-center justify-between">
                                        <div class="flex items-center gap-1.5">
                                            <IconClock class="w-4 h-4 text-blue-500" />
                                            <span class="text-xs font-bold">Max Reasoning Rounds</span>
                                            <span class="text-[10px] font-mono text-gray-400">
                                                {{ isCustomRounds ? customRounds : '(Default)' }}
                                            </span>
                                        </div>
                                        <button 
                                            type="button" 
                                            @click="isCustomRounds = !isCustomRounds" 
                                            :class="[isCustomRounds ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200']"
                                            :title="isCustomRounds ? 'Deactivate custom rounds limit (use discussion default)' : 'Activate custom rounds limit'"
                                        >
                                            <span :class="[isCustomRounds ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200']"></span>
                                        </button>
                                    </div>

                                    <div v-if="isCustomRounds" class="space-y-2 animate-in fade-in">
                                        <div class="flex items-center gap-3">
                                            <input 
                                                type="range" 
                                                v-model.number="customRounds" 
                                                min="1" 
                                                max="50" 
                                                step="1" 
                                                class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                            />
                                            <input 
                                                type="number" 
                                                v-model.number="customRounds" 
                                                min="1" 
                                                max="50" 
                                                step="1" 
                                                class="input-field !py-0.5 !px-1.5 text-xs w-16 text-center font-mono font-bold"
                                            />
                                        </div>
                                        <div class="flex items-center justify-between text-[10px] text-gray-400">
                                            <button type="button" @click="customRounds = 5" class="hover:text-blue-500 cursor-pointer">Quick (5)</button>
                                            <button type="button" @click="customRounds = 10" class="hover:text-blue-500 cursor-pointer">Standard (10)</button>
                                            <button type="button" @click="customRounds = 20" class="hover:text-blue-500 cursor-pointer">Default (20)</button>
                                            <button type="button" @click="customRounds = 35" class="hover:text-blue-500 cursor-pointer">Deep (35)</button>
                                        </div>
                                    </div>
                                    <p v-else class="text-[10px] text-gray-400">
                                        Deactivated. Discussion default (20 rounds) will apply.
                                    </p>
                                </div>
                            </div>
                        </Transition>
                    </div>

                    <input type="file" ref="fileInput" @change="handleFileUpload" multiple class="hidden">
                    <input type="file" ref="imageInput" @change="handleImageUpload" multiple accept="image/*" class="hidden">
                </div>

                <div class="grow min-w-0 relative flex items-center">
                    <!-- Standard Auto-Growing Textarea (Always accessible for drafting) -->
                    <textarea 
                        ref="textareaRef"
                        v-model="messageText" 
                        @keydown="handleKeyDown" 
                        @input="adjustTextareaHeight"
                        @paste="handlePaste" 
                        rows="1" 
                        class="w-full bg-transparent border-0 focus:ring-0 resize-none py-2.5 px-3 max-h-80 overflow-y-auto text-sm leading-relaxed transition-all duration-100 min-h-[42px]" 
                        :placeholder="isRecording ? 'Recording... Click to stop.' : (generationInProgress ? 'Draft next message... (Ready when generation finishes)' : 'Type a message... (Shift+Enter for new line)')" 
                    ></textarea>
                </div>

                <div class="flex items-center gap-1 pb-1 pr-1">
                    <button v-if="isSttActive" 
                            @click="toggleRecording" 
                            class="w-9 h-9 flex items-center justify-center rounded-xl transition-all shadow-sm border dark:border-gray-700 active:scale-95" 
                            :class="{
                                'text-red-500 animate-pulse bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800': isRecording, 
                                'text-gray-500 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700': !isRecording
                            }"
                            title="Voice Input">
                        <IconMicrophone class="w-5 h-5" />
                    </button>
                    
                    <button v-if="!generationInProgress" @click="handleSendMessage" class="w-9 h-9 flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm transition-all active:scale-95">
                         <IconSend class="w-5 h-5" />
                    </button>
                    <button v-else @click="handleStopGeneration" class="w-9 h-9 flex items-center justify-center bg-red-500 hover:bg-red-600 text-white rounded-xl shadow-sm transition-all active:scale-95" title="Stop Generation">
                        <IconStopCircle class="w-5 h-5" />
                    </button>
                </div>
            </div>
            
            <div v-if="totalPercentage >= 100" class="flex flex-col items-center gap-1 animate-in fade-in slide-in-from-bottom-2 py-1">
                <p class="text-[10px] text-center text-red-600 dark:text-red-400 font-black uppercase tracking-widest bg-red-500/20 px-6 py-1.5 rounded-full border border-red-500 shadow-lg shadow-red-500/20 animate-pulse">
                    ⚠️ Context Limit Reached
                </p>
                <p class="text-[9px] text-gray-500 font-medium italic">Older messages or large documents will be truncated during generation.</p>
            </div>
        </div>
    </div>

    <!-- ── [AMUSING] AI CHARACTER SHEET & ACTIVE LOADOUT MODAL ── -->
    <Teleport to="body">
        <div 
            v-if="isLoadoutModalOpen" 
            @click.self="isLoadoutModalOpen = false" 
            class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
        >
            <div class="bg-white dark:bg-gray-900 w-full max-w-xl rounded-3xl shadow-2xl border border-purple-200/60 dark:border-purple-800/50 overflow-hidden flex flex-col max-h-[88vh] animate-in zoom-in-95 duration-200">

                <!-- Character Header -->
                <div class="p-6 bg-gradient-to-br from-purple-600 via-indigo-600 to-blue-600 text-white relative overflow-hidden shrink-0">
                    <div class="absolute -right-8 -bottom-8 text-8xl opacity-15 pointer-events-none select-none">
                        {{ aiVibeEmoji }}
                    </div>

                    <div class="flex items-center justify-between relative z-10 mb-3">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-black uppercase tracking-[0.2em] bg-white/20 px-2.5 py-0.5 rounded-full backdrop-blur-sm">
                                AI Character Sheet
                            </span>
                        </div>
                        <button @click="isLoadoutModalOpen = false" class="p-1.5 hover:bg-white/20 rounded-full transition-colors cursor-pointer text-white">
                            <IconXMark class="w-5 h-5" />
                        </button>
                    </div>

                    <div class="flex items-center gap-4 relative z-10">
                        <div class="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-md border border-white/30 flex items-center justify-center text-4xl shadow-inner shrink-0">
                            {{ aiVibeEmoji }}
                        </div>
                        <div class="min-w-0">
                            <h3 class="text-xl sm:text-2xl font-black tracking-tight leading-tight">{{ aiCharacterClass }}</h3>
                            <p class="text-xs text-purple-100 italic mt-0.5 line-clamp-2">"{{ aiVibeQuote }}"</p>
                        </div>
                    </div>
                </div>

                <!-- Attributes & Meters Grid -->
                <div class="p-6 overflow-y-auto custom-scrollbar space-y-6 grow">
                    <div class="space-y-2">
                        <span class="text-[10px] font-black uppercase tracking-widest text-gray-400">Cognitive Attributes</span>
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <!-- Reasoning Gauge -->
                            <div class="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-2xl border dark:border-gray-800 space-y-1">
                                <span class="text-[9px] font-bold text-gray-400 uppercase">🧠 Brain Power</span>
                                <p class="text-xs font-black text-indigo-600 dark:text-indigo-400 uppercase font-mono">
                                    {{ isReasoningEffortActive ? reasoningEffort : 'Instant Instinct' }}
                                </p>
                                <p class="text-[9px] text-gray-400 leading-tight">
                                    {{ isReasoningEffortActive ? 'Chain-of-thought enabled.' : 'Fast direct response.' }}
                                </p>
                            </div>

                            <!-- Heat Gauge -->
                            <div class="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-2xl border dark:border-gray-800 space-y-1">
                                <span class="text-[9px] font-bold text-gray-400 uppercase">🌡️ Spiciness</span>
                                <p class="text-xs font-black text-amber-600 dark:text-amber-400 uppercase font-mono">
                                    {{ isCustomTemp ? customTemp.toFixed(2) : 'Default' }}
                                </p>
                                <p class="text-[9px] text-gray-400 leading-tight">
                                    {{ isCustomTemp ? (customTemp > 1 ? 'High creativity.' : 'Precise logic.') : 'Model calibrated.' }}
                                </p>
                            </div>

                            <!-- Stamina Gauge -->
                            <div class="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-2xl border dark:border-gray-800 space-y-1">
                                <span class="text-[9px] font-bold text-gray-400 uppercase">⏱️ Stamina</span>
                                <p class="text-xs font-black text-blue-600 dark:text-blue-400 uppercase font-mono">
                                    {{ isCustomRounds ? `${customRounds} Rounds` : '20 Rounds' }}
                                </p>
                                <p class="text-[9px] text-gray-400 leading-tight">Agentic loop budget.</p>
                            </div>
                        </div>
                    </div>

                    <!-- Active Buffs & Equipped Inventory -->
                    <div class="space-y-2">
                        <div class="flex items-center justify-between">
                            <span class="text-[10px] font-black uppercase tracking-widest text-gray-400">Equipped Buffs & Knowledge ({{ activeBuffs.length }})</span>
                            <span class="text-[9px] text-gray-400 font-mono">Live conversation context</span>
                        </div>

                        <div v-if="activeBuffs.length === 0" class="p-6 text-center text-xs text-gray-400 italic bg-gray-50 dark:bg-gray-800/40 rounded-2xl border border-dashed dark:border-gray-800">
                            No active buffs or knowledge equipped. The AI is running in clean vanilla mode!
                        </div>

                        <div v-else class="space-y-2">
                            <div 
                                v-for="buff in activeBuffs" 
                                :key="buff.id"
                                class="p-3.5 rounded-2xl border border-gray-100 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-800/40 flex items-center justify-between gap-3 group"
                            >
                                <div class="flex items-start gap-3 min-w-0">
                                    <div class="w-8 h-8 rounded-xl bg-white dark:bg-gray-700 shadow-xs flex items-center justify-center text-lg shrink-0 border border-gray-200 dark:border-gray-600">
                                        {{ buff.icon }}
                                    </div>
                                    <div class="min-w-0">
                                        <div class="flex items-center gap-2">
                                            <h4 class="text-xs font-bold text-gray-800 dark:text-gray-100 truncate">{{ buff.name }}</h4>
                                            <span class="px-1.5 py-0.2 rounded text-[8px] font-black uppercase tracking-widest bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300">{{ buff.badge }}</span>
                                        </div>
                                        <p class="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{{ buff.description }}</p>
                                    </div>
                                </div>

                                <button 
                                    type="button"
                                    @click="buff.action();" 
                                    class="px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase transition-all shrink-0 cursor-pointer bg-gray-200/80 dark:bg-gray-700 hover:bg-red-100 dark:hover:bg-red-900/40 hover:text-red-600 text-gray-600 dark:text-gray-300"
                                >
                                    {{ buff.actionText || 'Eject' }}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Footer with quick actions -->
                <div class="p-4 border-t dark:border-gray-800 bg-gray-50/70 dark:bg-gray-950/70 flex items-center justify-between gap-3 shrink-0">
                    <div class="flex items-center gap-2">
                        <button @click="isLoadoutModalOpen = false; openWorkspaceMenu('notes');" class="btn btn-secondary btn-xs flex items-center gap-1">
                            <span>📝 Equip Note</span>
                        </button>
                        <button @click="isLoadoutModalOpen = false; openWorkspaceMenu('skills');" class="btn btn-secondary btn-xs flex items-center gap-1">
                            <span>✨ Equip Skill</span>
                        </button>
                    </div>

                    <button @click="isLoadoutModalOpen = false" class="btn btn-primary btn-sm px-6">
                        Awesome!
                    </button>
                </div>

            </div>
        </div>
    </Teleport>
</template>

<style scoped>
@reference "tailwindcss";
.tool-badge { @apply inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black border shadow-sm transition-all; }
.menu-divider { @apply my-1 border-t border-gray-100 dark:border-gray-700; }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
.no-scrollbar::-webkit-scrollbar { display: none; }
textarea { scrollbar-width: thin; scrollbar-color: rgba(156, 163, 175, 0.5) transparent; }
</style>