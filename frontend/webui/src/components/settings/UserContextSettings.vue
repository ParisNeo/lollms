<script setup>
import { computed, ref, watch, nextTick, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { storeToRefs } from 'pinia';
import LanguageSelector from '../ui/LanguageSelector.vue';

const authStore = useAuthStore();
const { user } = storeToRefs(authStore);

// Local state for form fields
const preferredName = ref('');
const generalInfo = ref('');
const personalInfo = ref('');
const codingStyle = ref('');
const langPrefs = ref('');
const tellOS = ref(false);
const shareDynamicInfo = ref(true);
const sharePersonalInfo = ref(false);
const funMode = ref(false);
const aiResponseLanguage = ref('auto');
const forceAiResponseLanguage = ref(false);
const imageGenerationEnabled = ref(false);
const imageGenerationSystemPrompt = ref('');
const imageAnnotationEnabled = ref(false);
const imageEditingEnabled = ref(false); 
const slideMakerEnabled = ref(false); // NEW
const activateGeneratedImages = ref(false);
const noteGenerationEnabled = ref(false);
const memoryEnabled = ref(false);
const autoMemoryEnabled = ref(false);
const maxImageWidth = ref(-1);
const maxImageHeight = ref(-1);
const compressImages = ref(false);
const imageCompressionQuality = ref(85);

const hasChanges = ref(false);
const isSaving = ref(false);

const isTtiConfigured = computed(() => !!user.value?.tti_binding_model_name);

// Function to update local state from the store
function populateForm() {
  if (user.value) {
    preferredName.value = user.value.preferred_name || '';
    generalInfo.value = user.value.data_zone || '';
    personalInfo.value = user.value.user_personal_info || '';
    codingStyle.value = user.value.coding_style_constraints || '';
    langPrefs.value = user.value.programming_language_preferences || '';
    tellOS.value = user.value.tell_llm_os || false;
    shareDynamicInfo.value = user.value.share_dynamic_info_with_llm ?? true;
    sharePersonalInfo.value = user.value.share_personal_info_with_llm || false;
    funMode.value = user.value.fun_mode || false;
    aiResponseLanguage.value = user.value.ai_response_language || 'auto';
    forceAiResponseLanguage.value = user.value.force_ai_response_language || false;
    imageGenerationEnabled.value = user.value.image_generation_enabled || false;
    imageGenerationSystemPrompt.value = user.value.image_generation_system_prompt || '';
    imageAnnotationEnabled.value = user.value.image_annotation_enabled || false;
    imageEditingEnabled.value = user.value.image_editing_enabled || false;
    slideMakerEnabled.value = user.value.slide_maker_enabled || false; // NEW
    activateGeneratedImages.value = user.value.activate_generated_images || false;
    noteGenerationEnabled.value = user.value.note_generation_enabled || false;
    memoryEnabled.value = user.value.memory_enabled || false;
    autoMemoryEnabled.value = user.value.auto_memory_enabled || false;
    maxImageWidth.value = user.value.max_image_width ?? -1;
    maxImageHeight.value = user.value.max_image_height ?? -1;
    compressImages.value = user.value.compress_images || false;
    imageCompressionQuality.value = user.value.image_compression_quality ?? 85;
    
    // Reset change tracker
    nextTick(() => {
        hasChanges.value = false;
    });
  }
}

// Watch for changes in the user object (e.g., after login or refresh)
watch(user, populateForm, { immediate: true, deep: true });

// Watch for changes in local form fields to enable the save button
watch([
    preferredName, generalInfo, personalInfo, codingStyle, langPrefs, tellOS, shareDynamicInfo, sharePersonalInfo,
    funMode, aiResponseLanguage, forceAiResponseLanguage, 
    imageGenerationEnabled, imageGenerationSystemPrompt, imageAnnotationEnabled, imageEditingEnabled, slideMakerEnabled, activateGeneratedImages, noteGenerationEnabled,
    memoryEnabled, autoMemoryEnabled, maxImageWidth, maxImageHeight, compressImages, imageCompressionQuality
], () => {
  hasChanges.value = true;
});

const staticInfo = [
  { label: 'Date', placeholder: '{{date}}' },
  { label: 'Time', placeholder: '{{time}}' },
  { label: 'Date & Time', placeholder: '{{datetime}}' },
  { label: 'Username', placeholder: '{{user_name}}' },
];

async function handleSaveChanges() {
    if (!hasChanges.value) return;
    isSaving.value = true;
    try {
        await authStore.updateUserPreferences({
            preferred_name: preferredName.value,
            data_zone: generalInfo.value,
            user_personal_info: personalInfo.value,
            coding_style_constraints: codingStyle.value,
            programming_language_preferences: langPrefs.value,
            tell_llm_os: tellOS.value,
            share_dynamic_info_with_llm: shareDynamicInfo.value,
            share_personal_info_with_llm: sharePersonalInfo.value,
            fun_mode: funMode.value,
            ai_response_language: aiResponseLanguage.value,
            force_ai_response_language: forceAiResponseLanguage.value,
            image_generation_enabled: imageGenerationEnabled.value,
            image_generation_system_prompt: imageGenerationSystemPrompt.value,
            image_annotation_enabled: imageAnnotationEnabled.value,
            image_editing_enabled: imageEditingEnabled.value,
            slide_maker_enabled: slideMakerEnabled.value, // NEW
            activate_generated_images: activateGeneratedImages.value,
            note_generation_enabled: noteGenerationEnabled.value,
            memory_enabled: memoryEnabled.value,
            auto_memory_enabled: autoMemoryEnabled.value,
            max_image_width: maxImageWidth.value,
            max_image_height: maxImageHeight.value,
            compress_images: compressImages.value,
            image_compression_quality: imageCompressionQuality.value
        });
        hasChanges.value = false;
    } finally {
        isSaving.value = false;
    }
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
    <div class="px-4 py-5 sm:p-6 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Global User Context</h3>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Manage information and preferences shared with the AI across all discussions.
        </p>
    </div>
    
    <div class="p-4 sm:p-6 space-y-6">
        <!-- Preferred Name -->
        <div>
            <label for="preferred-name" class="block text-sm font-semibold mb-1 text-gray-700 dark:text-gray-200">Preferred Name</label>
            <input 
                type="text" 
                id="preferred-name" 
                v-model="preferredName" 
                class="input-field w-full" 
                :placeholder="user?.username || 'How should the AI address you?'"
            >
            <p class="text-xs text-gray-500 mt-1">If left blank, the AI will use your username: <strong>{{ user?.username }}</strong></p>
        </div>
        
        <!-- Memory Settings -->
        <div class="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50 rounded-lg space-y-3">
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Long-Term Memory</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Allow the AI to access and manage your memory bank.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="memoryEnabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            
            <div v-if="memoryEnabled" class="flex items-center justify-between pl-4 border-l-2 border-blue-300 dark:border-blue-600">
                <div>
                    <h4 class="text-xs font-semibold text-gray-700 dark:text-gray-300">Auto Memory Decision</h4>
                    <p class="text-[10px] text-gray-500 dark:text-gray-400">Let the AI automatically decide when to save new memories during conversation.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="autoMemoryEnabled" class="sr-only peer">
                    <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
        </div>

        <!-- Static Info Section -->
        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Dynamic Information</h3>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="shareDynamicInfo" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            <p v-if="shareDynamicInfo" class="text-xs text-gray-500 dark:text-gray-400 mb-3">The AI will automatically know the following information. You can use these placeholders in your prompts.</p>
            <p v-else class="text-xs text-gray-500 dark:text-gray-400 mb-3">Dynamic information is currently disabled and will not be sent to the AI.</p>
            <div v-if="shareDynamicInfo" class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <div v-for="info in staticInfo" :key="info.label" class="flex justify-between items-center">
                    <span class="text-gray-800 dark:text-gray-200">{{ info.label }}:</span>
                    <code class="px-2 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">{{ info.placeholder }}</code>
                </div>
            </div>
        </div>

        <!-- Personal Info Section -->
        <div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 rounded-lg">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Personal Information / Credentials</h3>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="sharePersonalInfo" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            <p class="text-xs text-gray-600 dark:text-gray-300 mb-2">
                You can add sensitive information here (e.g., API keys, passwords, personal details) that the AI might need for specific tasks.
            </p>
            <div class="p-2 mb-3 bg-white dark:bg-gray-900 border border-red-200 dark:border-red-800 rounded text-xs text-red-600 dark:text-red-400 font-medium">
                Warning: Do NOT enter passwords or sensitive credentials unless you are running a local, secure model that you trust. Information entered here will be sent to the AI model in the context.
            </div>
            <textarea v-model="personalInfo" class="styled-textarea" placeholder="e.g., My email password is..., API Key for Service X is..."></textarea>
        </div>
        
        <!-- Toggle Sections -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Fun Mode 🎉</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Ask the AI to be more humorous and witty.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="funMode" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Image Annotation</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI to annotate images with bounding boxes.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="imageAnnotationEnabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Note Generation</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI to generate and format notes during conversation.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="noteGenerationEnabled" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>

            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Operating System</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Inform the AI about your current operating system.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="tellOS" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Image Editing</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI to edit existing images using tags like &lt;edit_image&gt;.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="imageEditingEnabled" class="sr-only peer" :disabled="!isTtiConfigured">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600 peer-disabled:opacity-50"></div>
                </label>
            </div>
            
            <!-- NEW: Slide Maker Toggle -->
            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg flex items-center justify-between">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Slide Maker</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Enable AI to generate slide presentations with images.</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="slideMakerEnabled" class="sr-only peer" :disabled="!isTtiConfigured">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600 peer-disabled:opacity-50"></div>
                </label>
            </div>
        </div>
        
        <!-- Image Generation Settings -->
        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg">
            <div class="flex items-center justify-between mb-3">
                <div class="flex-grow">
                    <h3 class="text-sm font-semibold" :class="isTtiConfigured ? 'text-gray-700 dark:text-gray-200' : 'text-gray-400 dark:text-gray-500'">Image Generation</h3>
                    <p class="text-xs" :class="isTtiConfigured ? 'text-gray-500 dark:text-gray-400' : 'text-gray-400 dark:text-gray-500'">
                        {{ isTtiConfigured ? 'Enable AI to generate images using code blocks.' : 'Select a TTI model in settings to enable.' }}
                    </p>
                </div>
                <label class="relative inline-flex items-center" :class="isTtiConfigured ? 'cursor-pointer' : 'cursor-not-allowed'">
                    <input type="checkbox" v-model="imageGenerationEnabled" class="sr-only peer" :disabled="!isTtiConfigured">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600 peer-disabled:opacity-50"></div>
                </label>
            </div>

            <div v-if="imageGenerationEnabled && isTtiConfigured" class="space-y-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                <!-- System Prompt -->
                <div>
                    <label for="image-gen-prompt" class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">Image Generation System Prompt</label>
                    <textarea id="image-gen-prompt" v-model="imageGenerationSystemPrompt" class="styled-textarea" placeholder="e.g., All images should be in a photorealistic style, 4k, detailed."></textarea>
                    <p class="text-xs text-gray-500 mt-1">This prompt will be added to every image generation request made from within a chat message.</p>
                </div>

                <!-- Auto Activate Setting -->
                <div class="flex items-center justify-between">
                    <div class="flex-grow pr-4">
                        <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Auto-Activate Generated Images</h4>
                        <p class="text-xs text-gray-500 dark:text-gray-400">If enabled, images generated by the AI will be automatically added to the conversation context for future turns.</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" v-model="activateGeneratedImages" class="sr-only peer">
                        <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                    </label>
                </div>
            </div>
        </div>

        <!-- Image Resizing Settings -->
        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg">
            <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">Image Upload Resizing</h3>
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Automatically resize images sent to the AI if they exceed these dimensions. Set to -1 to disable resizing.
            </p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                    <label for="max-image-width" class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Max Width (px)</label>
                    <input type="number" id="max-image-width" v-model.number="maxImageWidth" class="input-field w-full" placeholder="-1">
                </div>
                <div>
                    <label for="max-image-height" class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Max Height (px)</label>
                    <input type="number" id="max-image-height" v-model.number="maxImageHeight" class="input-field w-full" placeholder="-1">
                </div>
            </div>

             <!-- NEW: Compression Settings -->
             <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex-grow pr-4">
                        <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Compress Images</h4>
                        <p class="text-xs text-gray-500 dark:text-gray-400">Convert uploads to JPEG to reduce size (helps avoid API limits). Defaults to PNG if disabled.</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" v-model="compressImages" class="sr-only peer">
                        <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                    </label>
                </div>
                
                <div v-if="compressImages">
                    <label for="compression-quality" class="block text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">Quality ({{ imageCompressionQuality }})</label>
                    <input type="range" id="compression-quality" v-model.number="imageCompressionQuality" min="10" max="100" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700">
                </div>
            </div>
        </div>

        <!-- AI Language Setting -->
        <div class="p-4 bg-gray-50 dark:bg-gray-700/50 border dark:border-gray-600 rounded-lg">
            <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">AI Response Language</h3>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="forceAiResponseLanguage" class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
            </div>
            <LanguageSelector v-model="aiResponseLanguage" id="aiResponseLanguage" :include-auto="true" :disabled="!forceAiResponseLanguage" />
            <p v-if="forceAiResponseLanguage" class="mt-2 text-xs text-gray-500 dark:text-gray-400">Force the AI to respond in a specific language. 'Auto' will match the user's prompt language.</p>
            <p v-else class="mt-2 text-xs text-gray-500 dark:text-gray-400">Language enforcement is disabled. The AI will respond based on its training and personality.</p>
        </div>

        <!-- Text Areas for Preferences -->
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">Coding Style Constraints</label>
                <textarea v-model="codingStyle" class="styled-textarea" placeholder="e.g., Always follow PEP8 for Python code. Use pathlib instead of os.path."></textarea>
            </div>
            <div>
                <label class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">Programming Language & Library Preferences</label>
                <textarea v-model="langPrefs" class="styled-textarea" placeholder="e.g., I prefer solutions in Python 3.10+. For web development, use Vue.js with Tailwind CSS."></textarea>
            </div>
            <div>
                <label class="block text-sm font-semibold mb-2 text-gray-700 dark:text-gray-200">General Info / Notes</label>
                <textarea v-model="generalInfo" class="styled-textarea" placeholder="Add any other information about yourself or general instructions for the AI."></textarea>
            </div>
        </div>
    </div>
    
    <div class="px-4 py-3 bg-gray-50 dark:bg-gray-700/50 text-right sm:px-6 rounded-b-lg border-t border-gray-200 dark:border-gray-700">
        <button @click="handleSaveChanges" class="btn btn-primary" :disabled="!hasChanges || isSaving">
            {{ isSaving ? 'Saving...' : 'Save Context Settings' }}
        </button>
    </div>
  </div>
</template>

<style scoped>
.styled-textarea {
    @apply w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-900 focus:ring-blue-500 focus:border-blue-500 transition text-sm min-h-[100px] resize-y;
}
</style>
