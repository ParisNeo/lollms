<!-- [UPDATE] frontend/webui/src/components/modals/DiscussionTreeModal.vue -->
<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';
import DiscussionTreeNode from './DiscussionTreeNode.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore(); // Keep this for potential future use or consistency

const props = computed(() => uiStore.modalData('discussionTree'));
const discussionId = computed(() => props.value?.discussionId);

const isLoading = ref(false);
const treeData = ref([]); // Stores the hierarchical tree structure

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const activeBranchId = computed(() => activeDiscussion.value?.active_branch_id);

watch(discussionId, async (newId) => {
    if (newId) {
        await loadTreeData(newId);
    }
}, { immediate: true });

async function loadTreeData(id) {
    isLoading.value = true;
    try {
        const flatMessages = await discussionsStore.fetchDiscussionTree(id);
        
        // Log the received messages for debugging
        console.log("Messages received for tree:", flatMessages); 

        // Add a defensive check to ensure flatMessages is an array
        if (!Array.isArray(flatMessages)) {
            console.error("Error: Expected an array of messages but received:", flatMessages);
            // Fallback to an empty array to prevent TypeError
            treeData.value = []; 
            return;
        }

        treeData.value = buildTree(flatMessages);
    } finally {
        isLoading.value = false;
    }
}

function buildTree(messages) {
    // This function is now guaranteed to receive an array due to the check in loadTreeData
    const messageMap = new Map();
    const roots = [];

    // First pass: create a map of messages by ID and initialize children array
    messages.forEach(msg => {
        messageMap.set(msg.id, {
            ...msg,
            children: [],
            is_leaf: true, // Assume leaf until a child is added
        });
    });

    // Second pass: build the hierarchy
    messageMap.forEach(node => {
        if (node.parent_message_id && messageMap.has(node.parent_message_id)) {
            const parent = messageMap.get(node.parent_message_id);
            parent.children.push(node);
            parent.is_leaf = false; // Parent is no longer a leaf
            node.is_root = false;
        } else {
            // If no parent or parent not found, it's a root (or orphan top, which we treat as root for display)
            roots.push(node);
            node.is_root = true;
        }
    });

    // Sort children by creation date for consistent display
    messageMap.forEach(node => {
        node.children.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    });

    // Sort root nodes by creation date
    roots.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

    return roots;
}

function handleSelectBranch(messageId) {
    discussionsStore.switchBranch(messageId);
    uiStore.closeModal('discussionTree');
}

</script>

<template>
    <GenericModal
        modal-name="discussionTree"
        :title="activeDiscussion ? `Discussion Tree: ${activeDiscussion.title}` : 'Discussion Tree'"
        max-width-class="max-w-4xl"
    >
        <template #body>
            <div v-if="isLoading" class="flex justify-center items-center p-8">
                <IconAnimateSpin class="w-8 h-8 text-gray-500" />
                <span class="ml-3 text-gray-500">Loading discussion tree...</span>
            </div>
            <div v-else-if="!discussionId" class="text-center p-8 text-gray-500">
                No discussion selected.
            </div>
            <div v-else-if="treeData.length === 0" class="text-center p-8 text-gray-500">
                No messages found for this discussion.
            </div>
            <div v-else class="overflow-y-auto max-h-[70vh] py-2 px-4">
                <DiscussionTreeNode
                    v-for="node in treeData"
                    :key="node.id"
                    :node="node"
                    :level="0"
                    :active-branch-id="activeBranchId"
                    @select-branch="handleSelectBranch"
                />
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('discussionTree')" class="btn btn-secondary">Close</button>
        </template>
    </GenericModal>
</template>

<style scoped>
/* Add any specific styles for the modal or tree container here */
</style>