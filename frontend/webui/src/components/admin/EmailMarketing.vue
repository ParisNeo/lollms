<script setup>
import { ref, onMounted, computed } from 'vue';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';

const uiStore = useUiStore();
const proposals = ref([]);
const topics = ref([]);
const newTopic = ref('');
const activeTab = ref('proposals'); // proposals, topics
const isLoading = ref(false);

const pendingProposals = computed(() => proposals.value.filter(p => p.status === 'pending_review'));
const historyProposals = computed(() => proposals.value.filter(p => p.status !== 'pending_review'));

onMounted(() => {
    fetchProposals();
    fetchTopics();
});

async function fetchProposals() {
    isLoading.value = true;
    try {
        const res = await apiClient.get('/api/admin/email-marketing/proposals');
        proposals.value = res.data;
    } finally { isLoading.value = false; }
}

async function fetchTopics() {
    const res = await apiClient.get('/api/admin/email-marketing/topics');
    topics.value = res.data;
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
    if (status === 'approved' && !confirm("This will send the email to all users immediately. Continue?")) return;
    
    try {
        await apiClient.put(`/api/admin/email-marketing/proposals/${id}`, { status });
        uiStore.addNotification(status === 'approved' ? 'Email queued for sending!' : 'Proposal updated', 'success');
        fetchProposals();
    } catch (e) {
        uiStore.addNotification('Action failed', 'error');
    }
}

async function deleteProposal(id) {
    if (!confirm("Delete this draft?")) return;
    await apiClient.delete(`/api/admin/email-marketing/proposals/${id}`);
    fetchProposals();
}

// Simple edit mode state
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
}

</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
        <h2 class="text-xl font-bold mb-4">Email Marketing Bot</h2>
        
        <div class="flex space-x-4 mb-6 border-b dark:border-gray-700">
            <button @click="activeTab = 'proposals'" :class="['pb-2 px-1', activeTab === 'proposals' ? 'border-b-2 border-blue-500 font-bold' : 'text-gray-500']">Review Drafts</button>
            <button @click="activeTab = 'topics'" :class="['pb-2 px-1', activeTab === 'topics' ? 'border-b-2 border-blue-500 font-bold' : 'text-gray-500']">Topics</button>
            <button @click="activeTab = 'history'" :class="['pb-2 px-1', activeTab === 'history' ? 'border-b-2 border-blue-500 font-bold' : 'text-gray-500']">History</button>
        </div>

        <!-- REVIEW TAB -->
        <div v-if="activeTab === 'proposals'" class="space-y-6">
            <div v-if="pendingProposals.length === 0" class="text-center text-gray-500 py-10">
                No pending drafts. Lollms is thinking...
            </div>
            
            <div v-for="p in pendingProposals" :key="p.id" class="border dark:border-gray-700 rounded-lg p-4">
                <div v-if="editingId === p.id">
                    <input v-model="editForm.title" class="input-field mb-2" />
                    <textarea v-model="editForm.content" class="input-field h-40 mb-2"></textarea>
                    <div class="flex gap-2">
                        <button @click="saveEdit(p.id)" class="btn btn-primary btn-sm">Save</button>
                        <button @click="editingId = null" class="btn btn-secondary btn-sm">Cancel</button>
                    </div>
                </div>
                <div v-else>
                    <div class="flex justify-between items-start mb-2">
                        <h3 class="font-bold text-lg">{{ p.title }}</h3>
                        <span class="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">Topic: {{ p.source_topic }}</span>
                    </div>
                    <p class="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap mb-4 bg-gray-50 dark:bg-gray-900 p-3 rounded">{{ p.content }}</p>
                    
                    <div class="flex gap-3 mt-4">
                        <button @click="updateStatus(p.id, 'approved')" class="btn btn-primary">Approve & Send</button>
                        <button @click="startEdit(p)" class="btn btn-secondary">Edit</button>
                        <button @click="updateStatus(p.id, 'rejected')" class="text-red-500 hover:underline">Reject</button>
                        <button @click="deleteProposal(p.id)" class="text-gray-500 hover:underline ml-auto">Delete</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- TOPICS TAB -->
        <div v-if="activeTab === 'topics'" class="space-y-4">
            <div class="flex gap-2">
                <input v-model="newTopic" placeholder="Suggest a topic (e.g., 'Python Tips')" class="input-field" @keyup.enter="addTopic" />
                <button @click="addTopic" class="btn btn-primary">Add</button>
            </div>
            <ul class="divide-y divide-gray-200 dark:divide-gray-700">
                <li v-for="t in topics" :key="t.id" class="py-3 flex justify-between items-center">
                    <span>{{ t.topic }}</span>
                    <button @click="removeTopic(t.id)" class="text-red-500 hover:text-red-700">&times;</button>
                </li>
            </ul>
        </div>
        
        <!-- HISTORY TAB -->
        <div v-if="activeTab === 'history'" class="space-y-4">
            <div v-for="p in historyProposals" :key="p.id" class="border-b dark:border-gray-700 pb-2">
                <div class="flex justify-between">
                    <span class="font-medium">{{ p.title }}</span>
                    <span :class="{'text-green-500': p.status==='sent', 'text-red-500': p.status==='rejected'}">{{ p.status }}</span>
                </div>
                <div class="text-xs text-gray-400">{{ new Date(p.created_at).toLocaleDateString() }}</div>
            </div>
        </div>

    </div>
</template>
