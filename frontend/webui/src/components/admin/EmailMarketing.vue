<script setup>
import { ref, onMounted, computed } from 'vue';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const proposals = ref([]);
const topics = ref([]);
const newTopic = ref('');
const activeTab = ref('drafts'); // drafts, sent, topics
const isLoading = ref(false);

// Wizard State
const isWizardOpen = ref(false);
const wizardStep = ref(1);
const isGenerating = ref(false);
const wizardData = ref({
    topic: '',
    tone: 'professional',
    instructions: '',
    subject: '',
    content: ''
});

// Defensive computed properties
const safeProposals = computed(() => Array.isArray(proposals.value) ? proposals.value : []);

const drafts = computed(() => safeProposals.value.filter(p => p.status === 'draft' || p.status === 'pending_review' || p.status === 'rejected'));
const sentHistory = computed(() => safeProposals.value.filter(p => p.status === 'sent' || p.status === 'approved'));

onMounted(() => {
    fetchProposals();
    fetchTopics();
});

async function fetchProposals() {
    isLoading.value = true;
    try {
        const res = await apiClient.get('/api/admin/email-marketing/proposals');
        proposals.value = Array.isArray(res.data) ? res.data : [];
    } catch (e) {
        console.error("Failed to fetch proposals:", e);
        proposals.value = [];
    } finally { isLoading.value = false; }
}

async function fetchTopics() {
    try {
        const res = await apiClient.get('/api/admin/email-marketing/topics');
        topics.value = Array.isArray(res.data) ? res.data : [];
    } catch (e) {
        topics.value = [];
    }
}

// --- Wizard Functions ---
function openWizard() {
    wizardData.value = { topic: '', tone: 'professional', instructions: '', subject: '', content: '' };
    wizardStep.value = 1;
    isWizardOpen.value = true;
}

async function generateWizardDraft() {
    if (!wizardData.value.topic) return;
    isGenerating.value = true;
    try {
        // Updated endpoint path to match backend
        const res = await apiClient.post('/api/admin/email-marketing/generate-proposal', {
            topic: wizardData.value.topic,
            tone: wizardData.value.tone,
            additional_instructions: wizardData.value.instructions
        });
        wizardData.value.subject = res.data.subject;
        wizardData.value.content = res.data.body;
        wizardStep.value = 2;
    } catch (e) {
        uiStore.addNotification('AI Generation failed', 'error');
    } finally {
        isGenerating.value = false;
    }
}

async function saveWizardProposal() {
    try {
        await apiClient.post('/api/admin/email-marketing/proposals', {
            title: wizardData.value.subject,
            content: wizardData.value.content,
            source_topic: wizardData.value.topic
        });
        uiStore.addNotification('Campaign draft created!', 'success');
        isWizardOpen.value = false;
        fetchProposals();
    } catch (e) {
        uiStore.addNotification('Failed to save draft', 'error');
    }
}

async function addTopic() {
    if (!newTopic.value.trim()) return;
    await apiClient.post('/api/admin/email-marketing/topics', { topic: newTopic.value });
    newTopic.value = '';
    fetchTopics();
}

async function removeTopic(id) {
    await apiClient.delete(`/api/admin/email-marketing/topics/${id}`);
    fetchTopics();
}

async function updateStatus(id, status) {
    if (status === 'approved' && !confirm("This will send the email to all eligible users. Continue?")) return;
    try {
        await apiClient.put(`/api/admin/email-marketing/proposals/${id}`, { status });
        uiStore.addNotification(status === 'approved' ? 'Campaign started!' : 'Draft updated', 'success');
        fetchProposals();
    } catch (e) {
        uiStore.addNotification('Action failed', 'error');
    }
}

async function resendToNew(id) {
    if (!confirm("This will email users who joined after the initial campaign. Continue?")) return;
    try {
        await apiClient.post(`/api/admin/email-marketing/proposals/${id}/resend`);
        uiStore.addNotification('Resend task started', 'success');
        fetchProposals();
    } catch (e) {
        uiStore.addNotification('Action failed', 'error');
    }
}

async function deleteProposal(id) {
    if (!confirm("Delete this campaign/draft permanently?")) return;
    await apiClient.delete(`/api/admin/email-marketing/proposals/${id}`);
    fetchProposals();
}

const editingId = ref(null);
const editForm = ref({ title: '', content: '' });

function startEdit(p) {
    editingId.value = p.id;
    editForm.value = { title: p.title, content: p.content };
}

async function saveEdit(id) {
    await apiClient.put(`/api/admin/email-marketing/proposals/${id}`, editForm.value);
    editingId.value = null;
    fetchProposals();
    uiStore.addNotification('Draft saved', 'success');
}

function getStatusClass(status) {
    switch(status) {
        case 'sent': return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300';
        case 'pending_review': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300';
        case 'rejected': return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300';
        default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow rounded-lg h-full flex flex-col relative overflow-hidden">
        
        <!-- HEADER -->
        <div class="p-6 border-b dark:border-gray-700 flex justify-between items-center bg-white dark:bg-gray-800 z-10">
            <div>
                <h2 class="text-xl font-bold">Email Campaigns</h2>
                <p class="text-sm text-gray-500">Engage your users with AI-generated newsletters.</p>
            </div>
            <button @click="openWizard" class="btn btn-primary flex items-center gap-2 shadow-lg hover:scale-105 transition-transform">
                <IconSparkles class="w-4 h-4"/> AI Campaign Wizard
            </button>
        </div>
        
        <!-- TABS -->
        <div class="flex space-x-6 px-6 border-b dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30">
            <button @click="activeTab = 'drafts'" :class="['py-3 px-1 text-sm font-medium border-b-2 transition-all', activeTab === 'drafts' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700']">Drafts & Proposals</button>
            <button @click="activeTab = 'sent'" :class="['py-3 px-1 text-sm font-medium border-b-2 transition-all', activeTab === 'sent' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700']">Sent History</button>
            <button @click="activeTab = 'topics'" :class="['py-3 px-1 text-sm font-medium border-b-2 transition-all', activeTab === 'topics' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700']">AI Research Topics</button>
        </div>

        <div class="flex-grow overflow-y-auto p-6">
            
            <!-- DRAFTS -->
            <div v-if="activeTab === 'drafts'" class="space-y-6">
                <div v-if="isLoading" class="text-center py-20"><IconAnimateSpin class="w-10 h-10 animate-spin mx-auto text-blue-500"/></div>
                <div v-else-if="drafts.length === 0" class="text-center text-gray-500 py-20 border-2 border-dashed rounded-xl">
                    No active drafts. Start with the Wizard above!
                </div>
                
                <div v-for="p in drafts" :key="p.id" class="border dark:border-gray-700 rounded-xl overflow-hidden shadow-sm bg-white dark:bg-gray-900/50">
                    <div v-if="editingId === p.id" class="p-4 space-y-4">
                        <input v-model="editForm.title" class="input-field w-full font-bold" />
                        <textarea v-model="editForm.content" class="input-field w-full h-64 font-mono text-sm"></textarea>
                        <div class="flex gap-2 justify-end">
                            <button @click="editingId = null" class="btn btn-secondary">Cancel</button>
                            <button @click="saveEdit(p.id)" class="btn btn-primary">Save Draft</button>
                        </div>
                    </div>
                    <div v-else class="p-5">
                        <div class="flex justify-between items-start mb-4">
                            <div class="flex-grow">
                                <div class="flex items-center gap-2 mb-2">
                                    <span :class="['px-2 py-0.5 text-[9px] font-black uppercase rounded tracking-wider', getStatusClass(p.status)]">
                                        {{ p.status.replace('_', ' ') }}
                                    </span>
                                    <h3 class="font-bold text-lg text-gray-900 dark:text-white">{{ p.title }}</h3>
                                </div>
                                <div v-if="p.source_topic" class="flex items-center gap-2 text-xs text-gray-500 bg-gray-100 dark:bg-gray-800 w-fit px-2 py-1 rounded">
                                    <IconRefresh class="w-3 h-3" />
                                    <span>Source: {{ p.source_topic }}</span>
                                </div>
                            </div>
                            <div class="flex gap-1">
                                <button @click="startEdit(p)" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg text-gray-500 transition-colors" title="Edit Content"><IconPencil class="w-4 h-4"/></button>
                                <button @click="deleteProposal(p.id)" class="p-2 hover:bg-red-50 text-red-500 rounded-lg transition-colors" title="Delete"><IconTrash class="w-4 h-4"/></button>
                            </div>
                        </div>
                        <div class="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap mb-6 line-clamp-3 bg-gray-50 dark:bg-gray-800/80 p-4 rounded-xl border dark:border-gray-700 italic">
                            {{ p.content }}
                        </div>
                        <div class="flex gap-3">
                            <button @click="updateStatus(p.id, 'approved')" class="btn btn-primary btn-sm flex items-center gap-2 font-bold px-4">
                                <IconSend class="w-4 h-4"/> Start Campaign
                            </button>
                            <button v-if="p.status === 'draft'" @click="updateStatus(p.id, 'pending_review')" class="btn btn-secondary btn-sm">Queue for Review</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- SENT HISTORY -->
            <div v-if="activeTab === 'sent'" class="space-y-4">
                <div v-if="sentHistory.length === 0" class="text-center text-gray-500 py-10">No campaigns sent yet.</div>
                <div class="overflow-hidden border dark:border-gray-700 rounded-xl">
                    <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                        <thead class="bg-gray-50 dark:bg-gray-900/50">
                            <tr class="text-left text-[10px] font-black uppercase tracking-widest text-gray-500">
                                <th class="py-3 px-4">Subject</th>
                                <th class="py-3 px-4">Sent At</th>
                                <th class="py-3 px-4">Coverage</th>
                                <th class="py-3 px-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900/20">
                            <tr v-for="p in sentHistory" :key="p.id" class="hover:bg-gray-50 dark:hover:bg-gray-700/30 group transition-colors">
                                <td class="py-4 px-4">
                                    <div class="font-bold text-gray-900 dark:text-white">{{ p.title }}</div>
                                </td>
                                <td class="py-4 px-4 text-sm text-gray-500">
                                    {{ p.sent_at ? new Date(p.sent_at).toLocaleDateString() : 'Active...' }}
                                </td>
                                <td class="py-4 px-4">
                                    <span class="px-2 py-1 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 rounded-lg text-[10px] font-black border dark:border-blue-800">
                                        {{ p.recipients_count || 0 }} RECIPIENTS
                                    </span>
                                </td>
                                <td class="py-4 px-4 text-right space-x-2">
                                    <button @click="resendToNew(p.id)" class="btn btn-secondary btn-xs" title="Send only to new users">
                                        Resend to New
                                    </button>
                                    <button @click="deleteProposal(p.id)" class="text-red-500 opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded transition-all"><IconTrash class="w-4 h-4"/></button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- TOPICS -->
            <div v-if="activeTab === 'topics'" class="max-w-2xl mx-auto space-y-6">
                <div class="flex gap-2">
                    <input v-model="newTopic" placeholder="Suggest a research topic for the AI..." class="input-field flex-grow" @keyup.enter="addTopic" />
                    <button @click="addTopic" class="btn btn-primary px-6">Add Topic</button>
                </div>
                <div class="border dark:border-gray-700 rounded-2xl overflow-hidden bg-white dark:bg-gray-900/40">
                    <ul class="divide-y divide-gray-200 dark:divide-gray-700">
                        <li v-for="t in topics" :key="t.id" class="p-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                            <div class="flex items-center gap-3">
                                <div class="p-2 bg-green-50 dark:bg-green-900/30 rounded-full"><IconPlus class="w-4 h-4 text-green-500" /></div>
                                <div>
                                    <span class="font-bold text-gray-900 dark:text-white">{{ t.topic }}</span>
                                    <p class="text-[10px] text-gray-500 uppercase tracking-tighter">Added via {{ t.source }}</p>
                                </div>
                            </div>
                            <button @click="removeTopic(t.id)" class="text-red-500 hover:bg-red-50 p-2 rounded-full transition-all"><IconTrash class="w-4 h-4"/></button>
                        </li>
                    </ul>
                </div>
            </div>
        </div>

        <!-- AI WIZARD MODAL -->
        <div v-if="isWizardOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-950/60 backdrop-blur-sm">
            <div class="bg-white dark:bg-gray-800 w-full max-w-2xl rounded-3xl shadow-2xl overflow-hidden animate-fade-in-up">
                
                <div class="p-6 border-b dark:border-gray-700 flex justify-between items-center bg-blue-600 text-white">
                    <div class="flex items-center gap-3">
                        <IconSparkles class="w-6 h-6 animate-pulse" />
                        <h3 class="text-xl font-black uppercase tracking-tighter">AI Campaign Wizard</h3>
                    </div>
                    <button @click="isWizardOpen = false" class="p-1 hover:bg-white/20 rounded-full"><IconXMark class="w-6 h-6" /></button>
                </div>

                <div class="p-8">
                    <div v-if="wizardStep === 1" class="space-y-6">
                        <div class="space-y-2">
                            <label class="text-xs font-black uppercase text-gray-500 tracking-widest">What is this email about?</label>
                            <textarea v-model="wizardData.topic" rows="3" class="input-field w-full" placeholder="e.g. New features in v2.1, maintenance notice for Sunday, or tips for better prompts..."></textarea>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div class="space-y-2">
                                <label class="text-xs font-black uppercase text-gray-500 tracking-widest">Tone</label>
                                <select v-model="wizardData.tone" class="input-field w-full">
                                    <option value="professional">Professional & Direct</option>
                                    <option value="friendly">Friendly & Casual</option>
                                    <option value="exciting">Exciting & Hype</option>
                                    <option value="urgent">Urgent & Serious</option>
                                </select>
                            </div>
                            <div class="space-y-2">
                                <label class="text-xs font-black uppercase text-gray-500 tracking-widest">Custom Instructions</label>
                                <input v-model="wizardData.instructions" type="text" class="input-field w-full" placeholder="e.g. Include a link to our discord">
                            </div>
                        </div>
                        <div class="pt-4 flex justify-end">
                            <button @click="generateWizardDraft" :disabled="!wizardData.topic || isGenerating" class="btn btn-primary px-8 py-3 rounded-2xl flex items-center gap-3">
                                <IconAnimateSpin v-if="isGenerating" class="w-5 h-5 animate-spin" />
                                <span v-else>Generate Draft</span>
                                <IconArrowRight v-if="!isGenerating" class="w-4 h-4" />
                            </button>
                        </div>
                    </div>

                    <div v-if="wizardStep === 2" class="space-y-6">
                        <div class="space-y-2">
                            <label class="text-xs font-black uppercase text-gray-500 tracking-widest">Subject Line</label>
                            <input v-model="wizardData.subject" class="input-field w-full font-bold" />
                        </div>
                        <div class="space-y-2">
                            <label class="text-xs font-black uppercase text-gray-500 tracking-widest">Email Content</label>
                            <textarea v-model="wizardData.content" rows="10" class="input-field w-full font-mono text-sm"></textarea>
                        </div>
                        <div class="flex justify-between items-center pt-4">
                            <button @click="wizardStep = 1" class="btn btn-secondary">Back</button>
                            <div class="flex gap-2">
                                <button @click="generateWizardDraft" class="btn btn-secondary flex items-center gap-2">
                                    <IconRefresh class="w-4 h-4" /> Re-Generate
                                </button>
                                <button @click="saveWizardProposal" class="btn btn-primary px-8 flex items-center gap-2">
                                    <IconCheckCircle class="w-4 h-4" /> Save as Draft
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </div>
</template>

<style scoped>
.animate-fade-in-up { animation: fadeInUp 0.4s ease-out; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
</style>
