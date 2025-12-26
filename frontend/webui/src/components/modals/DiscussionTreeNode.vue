<!-- [UPDATE] frontend/webui/src/components/modals/DiscussionTreeNode.vue -->
<script setup>
import { computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconToken from '../../assets/icons/IconToken.vue';

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  // Used to manage indentation or visual depth if needed
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
    return null;
});

const nodeClass = computed(() => {
    return {
        'bg-white dark:bg-gray-800': true,
        'border-blue-500 ring-2 ring-blue-500': isActiveBranch.value,
        'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600': !isActiveBranch.value,
        'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-750': props.node.is_leaf,
        'leaf-node': props.node.is_leaf,
    };
});

const statusColorClass = computed(() => {
    if (props.node.is_leaf) {
        return isAi.value ? 'bg-green-500' : 'bg-purple-500';
    }
    return 'bg-gray-400';
});

const isActiveBranch = computed(() => {
  if (props.node.id === props.activeBranchId) return true;
  if (props.node.children) {
    return props.node.children.some(child => {
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
  const plainText = content.replace(/<[^>]*>?/gm, '').trim(); 
  return plainText.substring(0, 120) + (plainText.length > 120 ? '...' : '');
};

const formatDateTime = (isoString) => {
  if (!isoString) return '';
  return new Date(isoString).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};
</script>

<template>
  <div class="tree-node-container relative">
    <div class="node-wrapper flex items-start relative z-10">
        <!-- Node Box -->
        <div
          class="node-card relative flex flex-col p-3 rounded-lg border shadow-sm transition-all duration-200 w-full min-w-[250px] max-w-[400px]"
          :class="nodeClass"
          @click="handleNodeClick"
        >
          <!-- Header -->
          <div class="flex items-center gap-2 mb-2 pb-2 border-b border-gray-100 dark:border-gray-700/50">
            <div class="relative">
                <img v-if="senderIcon" :src="senderIcon" class="w-6 h-6 rounded-full object-cover border border-gray-200 dark:border-gray-700" :alt="senderName" />
                <div v-else class="w-6 h-6 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                    <IconUserCircle v-if="isUser" class="w-4 h-4 text-blue-500" />
                    <IconSparkles v-else class="w-4 h-4 text-purple-500" />
                </div>
                <!-- Status Dot -->
                <div class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-white dark:border-gray-800" :class="statusColorClass"></div>
            </div>
            
            <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold text-gray-900 dark:text-gray-100 truncate">{{ senderName }}</span>
                    <span class="text-[10px] text-gray-400 tabular-nums">{{ formatDateTime(node.created_at) }}</span>
                </div>
                <div v-if="isAi && (node.binding_name || node.model_name)" class="text-[9px] text-gray-500 dark:text-gray-400 font-mono truncate opacity-80">
                    {{ node.binding_name }}{{ node.model_name ? '/' + node.model_name : '' }}
                </div>
            </div>
          </div>

          <!-- Content -->
          <div class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed font-sans line-clamp-3">
              {{ formatContentSnippet(node.content) || '(No content)' }}
          </div>
          
          <!-- Footer Stats -->
          <div class="mt-2 pt-2 flex items-center gap-3 text-[10px] text-gray-400 border-t border-gray-50 dark:border-gray-700/30">
             <span class="flex items-center gap-1"><IconToken class="w-3 h-3" /> {{ node.token_count || 0 }}</span>
             <span v-if="node.is_leaf" class="ml-auto text-blue-500 font-bold uppercase tracking-wider">Leaf</span>
          </div>

          <!-- Selection Indicator -->
          <div v-if="isActiveBranch && !node.is_leaf" class="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 rounded-l-lg opacity-50"></div>
        </div>
    </div>

    <!-- Children Container with Connector Lines -->
    <div v-if="node.children && node.children.length > 0" class="children-container pl-8 relative mt-4">
      
      <!-- Vertical Line -->
      <div class="absolute left-4 top-[-20px] bottom-4 w-px bg-gray-300 dark:bg-gray-600 z-0"></div>
      
      <div v-for="(child, index) in node.children" :key="child.id" class="child-wrapper relative pl-4 pb-4 last:pb-0">
          <!-- Horizontal Line -->
          <div class="absolute left-[-16px] top-6 w-5 h-px bg-gray-300 dark:bg-gray-600 z-0"></div>
          
          <!-- Mask for vertical line on last child -->
          <div v-if="index === node.children.length - 1" class="absolute left-[-17px] top-6 bottom-0 w-4 bg-white dark:bg-[#1f2937] z-0"></div>

          <DiscussionTreeNode
            :node="child"
            :level="level + 1"
            :active-branch-id="activeBranchId"
            @select-branch="emit('select-branch', $event)"
          />
      </div>
    </div>
  </div>
</template>

<style scoped>
.child-wrapper:last-child > .absolute.bg-white {
    /* Match modal background color to mask line */
    background-color: white; 
}
.dark .child-wrapper:last-child > .absolute.bg-white {
    background-color: #1f2937; /* Tailwind gray-800 for dark mode modal body */
}
</style>
