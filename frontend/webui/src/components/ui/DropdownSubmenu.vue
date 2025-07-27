<template>
  <div class="relative" ref="triggerRef" @mouseenter="openSubmenu" @mouseleave="closeSubmenu">
    <div class="flex items-center justify-between px-3 py-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded cursor-pointer text-sm text-gray-700 dark:text-gray-200 w-full">
      <EditorIcon v-if="props.icon" :name="props.icon" :collection="props.collection" class="h-6 w-6 mr-2" />
      <span class="flex-grow">{{ props.title }}</span>
      <EditorIcon name="chevron-right" collection="ui" class="h-4 w-4 ml-2 opacity-70" />
    </div>

    <Teleport to="body">
      <div
        v-if="isOpen"
        ref="menuRef"
        :style="menuStyle"
        @mouseenter="openSubmenu" 
        @mouseleave="closeSubmenu"
        class="fixed z-50 p-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-lg min-w-max max-h-[80vh] overflow-y-auto"
      >
        <slot></slot>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted, onUnmounted } from 'vue';
import EditorIcon from './EditorIcon.vue';

const props = defineProps({
    title: String,
    icon: String,
    collection: { type: String, default: 'ui' }
});

const isOpen = ref(false);
const timer = ref(null);
const triggerRef = ref(null);
const menuRef = ref(null);
const menuStyle = reactive({
    top: '0px',
    left: '0px',
    visibility: 'hidden',
});

const updatePosition = () => {
    if (!triggerRef.value) return;
    const rect = triggerRef.value.getBoundingClientRect();
    menuStyle.top = `${rect.top + window.scrollY}px`;
    menuStyle.left = `${rect.right + window.scrollX + 4}px`;
    menuStyle.visibility = 'visible';
};

const openSubmenu = () => {
    if (timer.value) clearTimeout(timer.value);
    isOpen.value = true;
    menuStyle.visibility = 'hidden';
    nextTick(updatePosition);
};

const closeSubmenu = () => {
    timer.value = setTimeout(() => {
        isOpen.value = false;
    }, 200);
};

onMounted(() => window.addEventListener('resize', closeSubmenu));
onUnmounted(() => window.removeEventListener('resize', closeSubmenu));
</script>