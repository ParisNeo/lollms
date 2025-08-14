<!-- [CREATE] frontend/webui/src/components/modals/DiscussionTreeNode.vue -->
<script setup>
import { computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconToken from '../../assets/icons/IconToken.vue';

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  level: {
    type: Number,
    default: 0,
  },
  activeBranchId: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(['select-branch']);

const authStore = useAuthStore();
const dataStore = useDataStore();

const isUser = computed(() => props.node.sender_type === 'user');
const isAi = computed(() => props.node.sender_type === 'assistant');

const senderName = computed(() => {
    if (isUser.value) return authStore.user?.username || 'You';
    if (isAi.value) return props.node.sender || 'Assistant';
    return props.node.sender || 'System';
});

const senderIcon = computed(() => {
    if (isUser.value) return authStore.user?.icon;
    if (isAi.value) {
        const personality = dataStore.allPersonalities.find(p => p.name === props.node.sender);
        return personality?.icon_base64;
    }
    return null; // No icon for system messages in this context
});

const nodeClass = computed(() => {
    return {
        'bg-gray-100 dark:bg-gray-700/50': props.level % 2 === 0,
        'bg-gray-50 dark:bg-gray-900/50': props.level % 2 !== 0,
        'border-blue-500 ring-2 ring-blue-500': isActiveBranch.value,
        'cursor-pointer hover:bg-opacity-80': props.node.is_leaf,
        'bg-green-100 dark:bg-green-900/30': props.node.is_leaf && isAi.value, /* Green for AI leaf */
        'bg-purple-100 dark:bg-purple-900/30': props.node.is_leaf && isUser.value, /* Purple for User leaf */
    };
});

const isActiveBranch = computed(() => {
  // Recursively check if this node or any of its children are part of the active branch
  if (props.node.id === props.activeBranchId) return true;
  if (props.node.children) {
    return props.node.children.some(child => {
        // Find if any of the child's descendants are the activeBranchId
        const findInDescendants = (n) => {
            if (n.id === props.activeBranchId) return true;
            if (n.children) {
                return n.children.some(grandchild => findInDescendants(grandchild));
            }
            return false;
        };
        return findInDescendants(child);
    });
  }
  return false;
});

function handleNodeClick() {
  if (props.node.is_leaf) {
    emit('select-branch', props.node.id);
  }
}

const formatContentSnippet = (content) => {
  if (!content) return '';
  const plainText = content.replace(/<[^>]*>?/gm, '').trim(); // Remove HTML/Markdown tags
  return plainText.substring(0, 100) + (plainText.length > 100 ? '...' : '');
};

const formatDateTime = (isoString) => {
  if (!isoString) return 'N/A';
  return new Date(isoString).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
};
</script>

<template>
  <div class="tree-node" :style="{ 'margin-left': (level * 20) + 'px' }">
    <div
      class="node-content rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm transition-all duration-150 relative"
      :class="nodeClass"
      @click="handleNodeClick"
    >
      <div class="flex items-center gap-2 mb-2 text-sm font-semibold">
        <img v-if="senderIcon" :src="senderIcon" class="w-6 h-6 rounded-full object-cover" :alt="senderName" />
        <IconUserCircle v-else-if="isUser" class="w-6 h-6 text-blue-500" />
        <IconSparkles v-else-if="isAi" class="w-6 h-6 text-purple-500" />
        <span class="truncate">{{ senderName }}</span>
        <span v-if="isAi && (node.binding_name || node.model_name)" class="text-xs text-gray-500 font-mono">
            ({{ node.model_name || node.binding_name }})
        </span>
      </div>
      <p class="text-xs text-gray-700 dark:text-gray-300 line-clamp-2">{{ formatContentSnippet(node.content) }}</p>
      <div class="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mt-2">
        <span class="flex items-center gap-1">
            <IconToken class="w-3 h-3" />
            {{ node.token_count || 0 }} tokens
        </span>
        <span>{{ formatDateTime(node.created_at) }}</span>
      </div>
      <div v-if="node.is_leaf" class="absolute -top-2 -right-2 bg-blue-500 text-white text-xs px-2 py-0.5 rounded-full shadow">Leaf</div>
    </div>

    <div v-if="node.children && node.children.length > 0" class="node-children">
      <DiscussionTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :level="level + 1"
        :active-branch-id="activeBranchId"
        @select-branch="handleSelectBranch"
      />
    </div>
  </div>
</template>

<style scoped>
.tree-node {
  position: relative;
  margin-bottom: 8px; /* Space between nodes */
}

.node-content {
  padding: 10px;
  background-color: white;
  color: #333;
  transition: all 0.2s ease-in-out;
}

.node-content.bg-gray-100 { /* Example for Tailwind, adjust as needed */
  background-color: theme('colors.gray.100');
}
.dark .node-content.bg-gray-700\/50 {
  background-color: theme('colors.gray.700', '50%');
}

.node-content.bg-gray-50 {
  background-color: theme('colors.gray.50');
}
.dark .node-content.bg-gray-900\/50 {
  background-color: theme('colors.gray.900', '50%');
}

/* Specific colors for leaf nodes */
.node-content.bg-green-100 {
  background-color: theme('colors.green.100');
}
.dark .node-content.bg-green-900\/30 {
  background-color: theme('colors.green.900', '30%');
}

.node-content.bg-purple-100 {
  background-color: theme('colors.purple.100');
}
.dark .node-content.bg-purple-900\/30 {
  background-color: theme('colors.purple.900', '30%');
}

.node-children {
  position: relative;
  padding-left: 20px; /* Space for connecting lines */
  margin-top: 8px;
}

/* Connectors (optional, but visually helpful) */
.tree-node:not(:last-child) > .node-children::before {
  content: '';
  position: absolute;
  top: -8px; /* Adjust to connect to parent */
  bottom: 8px; /* Adjust to connect to child */
  left: 0;
  width: 1px;
  background-color: theme('colors.gray.300');
  z-index: -1;
}

.dark .tree-node:not(:last-child) > .node-children::before {
  background-color: theme('colors.gray.600');
}

.node-children > .tree-node::before {
  content: '';
  position: absolute;
  top: 15px; /* Half height of the node content */
  left: -20px;
  width: 20px; /* Horizontal line length */
  height: 1px;
  background-color: theme('colors.gray.300');
}

.dark .node-children > .tree-node::before {
  background-color: theme('colors.gray.600');
}

</style>