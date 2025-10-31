<template>
    <div 
        ref="panelRef"
        class="absolute top-4 left-4 w-96 bg-white dark:bg-gray-800 rounded-lg shadow-lg border dark:border-gray-700 z-10"
        :style="{ transform: `translate(${position.x}px, ${position.y}px)` }"
    >
        <div 
            class="flex items-center justify-between p-2 cursor-move border-b dark:border-gray-700"
            @mousedown="startDrag"
        >
            <h3 class="font-semibold text-lg">Prompts</h3>
            <button @click="isCollapsed = !isCollapsed" class="btn-icon">
                <IconChevronUp v-if="!isCollapsed" class="w-5 h-5" />
                <IconChevronDown v-else class="w-5 h-5" />
            </button>
        </div>

        <div v-show="!isCollapsed" class="p-4 space-y-4">
            <div>
                <div class="flex justify-between items-center mb-1">
                    <label for="floating-prompt" class="block text-sm font-medium">Prompt</label>
                    <button @click="$emit('enhance', 'prompt')" class="btn-icon" title="Enhance prompt with AI">
                        <IconSparkles class="w-4 h-4" />
                    </button>
                </div>
                <textarea 
                    id="floating-prompt"
                    :value="prompt"
                    @input="$emit('update:prompt', $event.target.value)"
                    rows="4" 
                    class="input-field w-full" 
                    placeholder="Describe the image..."
                ></textarea>
            </div>
            <div>
                <div class="flex justify-between items-center mb-1">
                    <label for="floating-neg-prompt" class="block text-sm font-medium">Negative Prompt</label>
                    <button @click="$emit('enhance', 'negative_prompt')" class="btn-icon" title="Enhance negative prompt with AI">
                        <IconSparkles class="w-4 h-4" />
                    </button>
                </div>
                <textarea 
                    id="floating-neg-prompt"
                    :value="negativePrompt"
                    @input="$emit('update:negativePrompt', $event.target.value)"
                    rows="3" 
                    class="input-field w-full" 
                    placeholder="ugly, blurry..."
                ></textarea>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue';
import IconChevronUp from '../../assets/icons/IconChevronUp.vue';
import IconChevronDown from '../../assets/icons/IconChevronDown.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

defineProps({
    prompt: String,
    negativePrompt: String,
});
defineEmits(['update:prompt', 'update:negativePrompt', 'enhance']);

const isCollapsed = ref(false);
const panelRef = ref(null);
const position = ref({ x: 0, y: 0 });
const dragStart = ref({ x: 0, y: 0 });
const isDragging = ref(false);

function startDrag(event) {
    isDragging.value = true;
    dragStart.value.x = event.clientX - position.value.x;
    dragStart.value.y = event.clientY - position.value.y;
    window.addEventListener('mousemove', onDrag);
    window.addEventListener('mouseup', stopDrag);
}

function onDrag(event) {
    if (!isDragging.value) return;
    position.value.x = event.clientX - dragStart.value.x;
    position.value.y = event.clientY - dragStart.value.y;
}

function stopDrag() {
    isDragging.value = false;
    window.removeEventListener('mousemove', onDrag);
    window.removeEventListener('mouseup', stopDrag);
}

onUnmounted(() => {
    window.removeEventListener('mousemove', onDrag);
    window.removeEventListener('mouseup', stopDrag);
});
</script>