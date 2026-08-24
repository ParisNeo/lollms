<script setup>
import { computed } from 'vue';
import IconStar from '../../../assets/icons/IconStar.vue';
import IconStarFilled from '../../../assets/icons/IconStarFilled.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconShare from '../../../assets/icons/IconShare.vue';
import IconCopy from '../../../assets/icons/IconCopy.vue';
import IconPlayCircle from '../../../assets/icons/IconPlayCircle.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';

const props = defineProps({
    personality: { type: Object, required: true },
    isUserPersonality: { type: Boolean, default: false },
    isActive: { type: Boolean, default: false },
    isSaving: { type: Boolean, default: false },
    isStarred: { type: Boolean, default: false },
    isShared: { type: Boolean, default: false },
    sharedBy: { type: String, default: '' },
    categoryStyle: { type: Object, default: () => ({ color: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300', icon: '🎯' }) }
});

const emit = defineEmits(['select', 'toggle-star', 'edit', 'delete', 'share', 'clone']);

const contextOptionIcons = {
    'image_generation': '🎨',
    'image_editing': '✏️',
    'slide_maker': '📊',
    'note_generation': '📝',
    'memory': '🧠',
    'inline_widgets': '🧩'
};

const contextOptionLabels = {
    'image_generation': 'Image Gen',
    'image_editing': 'Image Edit',
    'slide_maker': 'Slides',
    'note_generation': 'Notes',
    'memory': 'Memory',
    'inline_widgets': 'Widgets'
};

const hasContextOptions = computed(() => {
    return props.personality.required_context_options && props.personality.required_context_options.length > 0;
});

const hasTools = computed(() => {
    return props.personality.tools && props.personality.tools.length > 0;
});

const descriptionPreview = computed(() => {
    const desc = props.personality.description || '';
    if (desc.length > 120) {
        return desc.substring(0, 120) + '...';
    }
    return desc;
});

function handleSelect() {
    if (props.isSaving) return;
    emit('select', props.personality);
}

function handleStar(e) {
    e.stopPropagation();
    emit('toggle-star', props.personality);
}

function handleEdit(e) {
    e.stopPropagation();
    emit('edit', props.personality);
}

function handleDelete(e) {
    e.stopPropagation();
    emit('delete', props.personality);
}

function handleShare(e) {
    e.stopPropagation();
    emit('share', props.personality);
}

function handleClone(e) {
    e.stopPropagation();
    emit('clone', props.personality);
}
</script>

<template>
    <div 
        @click="handleSelect"
        class="group relative bg-white/95 dark:bg-gray-800/90 rounded-2xl border transition-all duration-300 cursor-pointer overflow-hidden hover:shadow-xl hover:-translate-y-1 backdrop-blur-sm flex flex-col justify-between"
        :class="[
            isActive 
                ? 'border-blue-500 shadow-lg shadow-blue-500/10 ring-2 ring-blue-500/30 dark:ring-blue-500/20' 
                : 'border-gray-200/80 dark:border-gray-700/70 hover:border-blue-500/40 dark:hover:border-blue-500/40',
            isSaving ? 'opacity-70 pointer-events-none' : ''
        ]"
    >
        <!-- Active Glow Strip -->
        <div 
            v-if="isActive"
            class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-indigo-500 shadow-sm"
        ></div>
        
        <!-- Saving Overlay -->
        <div v-if="isSaving" class="absolute inset-0 bg-white/70 dark:bg-black/50 backdrop-blur-xs flex items-center justify-center z-10">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>

        <div class="p-4 flex flex-col grow">
            <!-- Header: Avatar + Meta + Star -->
            <div class="flex items-start gap-3.5 mb-3">
                <!-- Avatar -->
                <div class="relative shrink-0">
                    <div 
                        class="w-13 h-13 rounded-xl overflow-hidden bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-700 dark:to-gray-600 flex items-center justify-center shadow-inner border border-gray-200/50 dark:border-gray-600/50 group-hover:scale-105 transition-transform duration-300"
                        :class="{ 'ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-gray-800': isActive }"
                    >
                        <img 
                            v-if="personality.icon_base64" 
                            :src="personality.icon_base64" 
                            class="w-full h-full object-cover"
                            :alt="personality.name"
                        />
                        <span v-else class="text-2xl">{{ categoryStyle.icon || '🎯' }}</span>
                    </div>

                    <!-- Active Badge -->
                    <div 
                        v-if="isActive"
                        class="absolute -bottom-1 -right-1 w-4.5 h-4.5 bg-emerald-500 rounded-full flex items-center justify-center shadow-md border-2 border-white dark:border-gray-800"
                    >
                        <IconCheckCircle class="w-3 h-3 text-white" />
                    </div>
                </div>

                <!-- Name & Category -->
                <div class="flex-1 min-w-0 pt-0.5">
                    <div class="flex items-center gap-2 mb-1">
                        <h4 class="font-bold text-gray-900 dark:text-white text-sm truncate leading-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                            {{ personality.name }}
                        </h4>
                        <span 
                            v-if="isShared"
                            class="shrink-0 px-1.5 py-0.2 rounded text-[10px] font-semibold bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300 border border-purple-200/60 dark:border-purple-800/40"
                            :title="`Shared by ${sharedBy}`"
                        >
                            📤 Shared
                        </span>
                    </div>

                    <div class="flex items-center gap-1.5 flex-wrap">
                        <span 
                            v-if="personality.category"
                            class="px-2 py-0.5 rounded-md text-[10px] font-semibold tracking-wide"
                            :class="categoryStyle.color"
                        >
                            {{ categoryStyle.icon }} {{ personality.category }}
                        </span>
                        <span 
                            v-else
                            class="px-2 py-0.5 rounded-md text-[10px] font-semibold tracking-wide bg-gray-100 text-gray-500 dark:bg-gray-700/50 dark:text-gray-400"
                        >
                            Uncategorized
                        </span>
                    </div>
                </div>

                <!-- Star Favorite Button -->
                <button 
                    @click="handleStar"
                    class="shrink-0 p-1 rounded-lg transition-all hover:scale-110 active:scale-95"
                    :class="isStarred ? 'bg-amber-400/15 text-amber-500' : 'text-gray-300 dark:text-gray-600 hover:text-amber-400'"
                    title="Toggle favorite"
                >
                    <IconStarFilled v-if="isStarred" class="w-4 h-4" />
                    <IconStar v-else class="w-4 h-4" />
                </button>
            </div>

            <!-- Description -->
            <p 
                v-if="personality.description"
                class="text-xs text-gray-600 dark:text-gray-300/80 leading-relaxed mb-3 line-clamp-2"
                :title="personality.description"
            >
                {{ descriptionPreview }}
            </p>
            <p v-else class="text-xs text-gray-400 dark:text-gray-500 italic mb-3">
                No personality description provided
            </p>

            <!-- Context Capabilities & Tools -->
            <div v-if="hasContextOptions || hasTools" class="flex flex-wrap gap-1.5 mt-auto pt-2">
                <span 
                    v-for="opt in personality.required_context_options" 
                    :key="opt"
                    class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/40 flex items-center gap-1"
                    :title="contextOptionLabels[opt] || opt"
                >
                    {{ contextOptionIcons[opt] || '🔧' }} {{ contextOptionLabels[opt] || opt }}
                </span>
                <span 
                    v-if="hasTools"
                    class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200/60 dark:border-emerald-800/40 flex items-center gap-1"
                    :title="personality.tools.join(', ')"
                >
                    🔧 {{ personality.tools.length }} tool{{ personality.tools.length > 1 ? 's' : '' }}
                </span>
            </div>
        </div>

        <!-- Footer: Main Trigger & Micro Actions -->
        <div class="p-3 border-t border-gray-150 dark:border-gray-750 bg-gray-50/80 dark:bg-gray-850/60 flex items-center justify-between gap-2 mt-auto">
            <div class="flex items-center gap-1">
                <!-- Activation State -->
                <button 
                    v-if="!isActive"
                    @click.stop="handleSelect"
                    class="btn btn-secondary btn-sm text-xs font-semibold shadow-sm"
                >
                    <IconPlayCircle class="w-3.5 h-3.5 mr-1" />
                    Activate
                </button>
                <span 
                    v-else
                    class="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-300/60 dark:border-emerald-700/50"
                >
                    <IconCheckCircle class="w-3.5 h-3.5 text-emerald-500" />
                    Active
                </span>
            </div>

            <!-- Micro-action buttons -->
            <div class="flex items-center gap-0.5">
                <!-- Clone Trigger -->
                <button 
                    v-if="!isUserPersonality && (personality.is_public || personality.owner_username === 'System')"
                    @click="handleClone"
                    class="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                    title="Clone to my personalities"
                >
                    <IconCopy class="w-3.5 h-3.5" />
                </button>
                
                <!-- Edit Trigger -->
                <button 
                    v-if="isUserPersonality"
                    @click="handleEdit"
                    class="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                    title="Edit personality"
                >
                    <IconPencil class="w-3.5 h-3.5" />
                </button>
                
                <!-- Share Trigger -->
                <button 
                    v-if="isUserPersonality && !isShared"
                    @click="handleShare"
                    class="p-1.5 rounded-lg text-gray-400 hover:text-emerald-600 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                    title="Share with friend"
                >
                    <IconShare class="w-3.5 h-3.5" />
                </button>
                
                <!-- Delete Trigger -->
                <button 
                    v-if="isUserPersonality"
                    @click="handleDelete"
                    class="p-1.5 rounded-lg text-gray-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                    title="Delete personality"
                >
                    <IconTrash class="w-3.5 h-3.5" />
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>