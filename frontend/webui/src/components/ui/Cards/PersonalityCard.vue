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
    categoryStyle: { type: Object, default: () => ({ color: 'bg-gray-100 text-gray-700', icon: '🎯' }) }
});

const emit = defineEmits(['select', 'toggle-star', 'edit', 'delete', 'share', 'clone']);

// Context option icons mapping
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
        class="group relative bg-white dark:bg-gray-800 rounded-xl border-2 transition-all duration-200 cursor-pointer overflow-hidden hover:shadow-lg"
        :class="[
            isActive 
                ? 'border-blue-500 shadow-lg shadow-blue-500/10 ring-2 ring-blue-500/20' 
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600',
            isSaving ? 'opacity-70 pointer-events-none' : ''
        ]"
    >
        <!-- Active Indicator Strip -->
        <div 
            v-if="isActive"
            class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-indigo-500"
        ></div>
        
        <!-- Saving Overlay -->
        <div v-if="isSaving" class="absolute inset-0 bg-white/60 dark:bg-black/40 flex items-center justify-center z-10">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>

        <div class="p-5">
            <!-- Header: Icon + Name + Star -->
            <div class="flex items-start gap-3 mb-3">
                <!-- Avatar -->
                <div class="relative flex-shrink-0">
                    <div 
                        class="w-14 h-14 rounded-xl overflow-hidden bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-700 dark:to-gray-600 flex items-center justify-center shadow-inner"
                        :class="{ 'ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-gray-800': isActive }"
                    >
                        <img 
                            v-if="personality.icon_base64" 
                            :src="personality.icon_base64" 
                            class="w-full h-full object-cover"
                            :alt="personality.name"
                        />
                        <span v-else class="text-2xl">{{ categoryStyle.icon }}</span>
                    </div>
                    <!-- Active Badge -->
                    <div 
                        v-if="isActive"
                        class="absolute -bottom-1 -right-1 w-5 h-5 bg-green-500 rounded-full flex items-center justify-center shadow-md"
                    >
                        <IconCheckCircle class="w-3 h-3 text-white" />
                    </div>
                </div>

                <!-- Name & Category -->
                <div class="flex-1 min-w-0 pt-0.5">
                    <div class="flex items-center gap-2 mb-1">
                        <h4 class="font-bold text-gray-900 dark:text-white text-sm truncate leading-tight">
                            {{ personality.name }}
                        </h4>
                        <span 
                            v-if="isShared"
                            class="flex-shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300"
                            title="Shared by {{ sharedBy }}"
                        >
                            📤
                        </span>
                    </div>
                    <div class="flex items-center gap-1.5 flex-wrap">
                        <span 
                            v-if="personality.category"
                            class="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide"
                            :class="categoryStyle.color"
                        >
                            {{ categoryStyle.icon }} {{ personality.category }}
                        </span>
                        <span 
                            v-else
                            class="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                        >
                            Uncategorized
                        </span>
                    </div>
                </div>

                <!-- Star Button -->
                <button 
                    @click="handleStar"
                    class="flex-shrink-0 p-1.5 rounded-lg transition-all hover:scale-110"
                    :class="isStarred ? 'text-yellow-500' : 'text-gray-300 dark:text-gray-600 hover:text-yellow-400'"
                    title="Toggle favorite"
                >
                    <IconStarFilled v-if="isStarred" class="w-5 h-5" />
                    <IconStar v-else class="w-5 h-5" />
                </button>
            </div>

            <!-- Description -->
            <p 
                v-if="personality.description"
                class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed mb-3 line-clamp-2"
                :title="personality.description"
            >
                {{ descriptionPreview }}
            </p>
            <p v-else class="text-xs text-gray-400 dark:text-gray-500 italic mb-3">
                No description provided
            </p>

            <!-- Context Options & Tools -->
            <div v-if="hasContextOptions || hasTools" class="flex flex-wrap gap-1.5 mb-3">
                <span 
                    v-for="opt in personality.required_context_options" 
                    :key="opt"
                    class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-50 text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-800"
                    :title="contextOptionLabels[opt] || opt"
                >
                    {{ contextOptionIcons[opt] || '🔧' }} {{ contextOptionLabels[opt] || opt }}
                </span>
                <span 
                    v-if="hasTools"
                    class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-800"
                    :title="personality.tools.join(', ')"
                >
                    🔧 {{ personality.tools.length }} tool{{ personality.tools.length > 1 ? 's' : '' }}
                </span>
            </div>

            <!-- Footer: Actions -->
            <div class="flex items-center justify-between pt-3 border-t border-gray-100 dark:border-gray-700/50">
                <div class="flex items-center gap-1">
                    <!-- Select Button (when not active) -->
                    <button 
                        v-if="!isActive"
                        @click.stop="handleSelect"
                        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/30 transition-colors"
                    >
                        <IconPlayCircle class="w-3.5 h-3.5" />
                        Activate
                    </button>
                    <span 
                        v-else
                        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400"
                    >
                        <IconCheckCircle class="w-3.5 h-3.5" />
                        Active
                    </span>
                </div>

                <!-- Action Buttons -->
                <div class="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <!-- Clone (for public/system) -->
                    <button 
                        v-if="!isUserPersonality && (personality.is_public || personality.owner_username === 'System')"
                        @click="handleClone"
                        class="p-1.5 rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                        title="Clone to my personalities"
                    >
                        <IconCopy class="w-4 h-4" />
                    </button>
                    
                    <!-- Edit -->
                    <button 
                        v-if="isUserPersonality"
                        @click="handleEdit"
                        class="p-1.5 rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                        title="Edit personality"
                    >
                        <IconPencil class="w-4 h-4" />
                    </button>
                    
                    <!-- Share -->
                    <button 
                        v-if="isUserPersonality && !isShared"
                        @click="handleShare"
                        class="p-1.5 rounded-lg text-gray-400 hover:text-green-500 hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors"
                        title="Share with friend"
                    >
                        <IconShare class="w-4 h-4" />
                    </button>
                    
                    <!-- Delete -->
                    <button 
                        v-if="isUserPersonality"
                        @click="handleDelete"
                        class="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                        title="Delete personality"
                    >
                        <IconTrash class="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
</style>