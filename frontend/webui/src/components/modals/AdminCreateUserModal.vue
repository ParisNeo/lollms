<script setup>
import { ref, computed, watch } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';
import IconUser from '../../assets/icons/IconUser.vue';
import IconMail from '../../assets/icons/IconMail.vue';
import IconLock from '../../assets/icons/IconLock.vue';
import IconShieldCheck from '../../assets/icons/IconShieldCheck.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import SimpleSelectMenu from '../ui/SimpleSelectMenu.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const formData = ref({
    username: '',
    password: '',
    email: '',
    is_admin: false,
    is_moderator: false,
    user_ui_level: 0,
    
    // LLM Settings
    lollms_model_name: null,
    llm_ctx_size: null,
    llm_temperature: null,
    llm_top_k: null,
    llm_top_p: null,
    llm_repeat_penalty: null,
    llm_repeat_last_n: null,
    put_thoughts_in_context: false,
    
    // Other Bindings
    tti_binding_model_name: null,
    tts_binding_model_name: null,
    stt_binding_model_name: null,
    safe_store_vectorizer: null,
    
    // RAG Settings
    rag_top_k: null,
    max_rag_len: null,
    rag_n_hops: null,
    rag_min_sim_percent: null,
    rag_use_graph: null,
    rag_graph_response_type: null,
    
    // UI Settings
    first_page: 'feed',
    message_font_size: 14,
    
    // Feature Flags
    auto_title: false,
    chat_active: true,
    fun_mode: false,
    show_token_counter: true,
    receive_notification_emails: true,
    is_searchable: true,
    
    // Image Settings
    image_generation_enabled: false,
    image_annotation_enabled: false,
    image_editing_enabled: false,
    activate_generated_images: false,
    max_image_width: -1,
    max_image_height: -1,
    compress_images: false,
    image_compression_quality: 85,
    
    // Memory & Herd Mode
    memory_enabled: false,
    auto_memory_enabled: false,
    herd_mode_enabled: false,
    
    // Reasoning
    reasoning_activation: false,
    reasoning_effort: null,
    reasoning_summary: false,
    
    // Web Search
    web_search_enabled: false,
    web_search_deep_analysis: false
});

const isLoading = ref(false);
const showAdvancedSettings = ref(false);

const uiLevelOptions = [
    { value: 0, label: 'Beginner' },
    { value: 1, label: 'Advanced' },
    { value: 2, label: 'Expert' }
];

const firstPageOptions = [
    { value: 'feed', label: 'Feed' },
    { value: 'chat', label: 'Chat' },
    { value: 'notes', label: 'Notes' }
];

const reasoningEffortOptions = [
    { value: null, label: 'Default' },
    { value: 'low', label: 'Low' },
    { value: 'medium', label: 'Medium' },
    { value: 'high', label: 'High' }
];

const ragResponseTypes = [
    { value: 'chunks_summary', label: 'Chunks Summary' },
    { value: 'direct', label: 'Direct' },
    { value: 'mixed', label: 'Mixed' }
];

const availableModels = computed(() => {
    return adminStore.adminAvailableLollmsModels.map(m => ({
        value: m.model_name,
        label: m.display_name || m.model_name
    }));
});

watch(() => uiStore.isModalOpen('adminCreateUser'), (isOpen) => {
    if (isOpen) {
        // Reset form
        formData.value = {
            username: '',
            password: '',
            email: '',
            is_admin: false,
            is_moderator: false,
            user_ui_level: 0,
            lollms_model_name: null,
            llm_ctx_size: null,
            llm_temperature: null,
            llm_top_k: null,
            llm_top_p: null,
            llm_repeat_penalty: null,
            llm_repeat_last_n: null,
            put_thoughts_in_context: false,
            tti_binding_model_name: null,
            tts_binding_model_name: null,
            stt_binding_model_name: null,
            safe_store_vectorizer: null,
            rag_top_k: null,
            max_rag_len: null,
            rag_n_hops: null,
            rag_min_sim_percent: null,
            rag_use_graph: null,
            rag_graph_response_type: null,
            first_page: 'feed',
            message_font_size: 14,
            auto_title: false,
            chat_active: true,
            fun_mode: false,
            show_token_counter: true,
            receive_notification_emails: true,
            is_searchable: true,
            image_generation_enabled: false,
            image_annotation_enabled: false,
            image_editing_enabled: false,
            activate_generated_images: false,
            max_image_width: -1,
            max_image_height: -1,
            compress_images: false,
            image_compression_quality: 85,
            memory_enabled: false,
            auto_memory_enabled: false,
            herd_mode_enabled: false,
            reasoning_activation: false,
            reasoning_effort: null,
            reasoning_summary: false,
            web_search_enabled: false,
            web_search_deep_analysis: false
        };
        showAdvancedSettings.value = false;
        
        // Load available models if not already loaded
        if (availableModels.value.length === 0) {
            adminStore.fetchAdminAvailableLollmsModels();
        }
    }
});

async function handleSubmit() {
    if (!formData.value.username.trim() || !formData.value.password.trim()) {
        uiStore.addNotification('Username and password are required.', 'warning');
        return;
    }
    
    isLoading.value = true;
    try {
        await adminStore.createUser(formData.value);
        uiStore.closeModal('adminCreateUser');
        uiStore.addNotification('User created successfully.', 'success');
    } catch (error) {
        console.error('Create user failed:', error);
        const message = error.response?.data?.detail || 'Failed to create user.';
        uiStore.addNotification(message, 'error');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modalName="adminCreateUser"
        title="Create New User"
        maxWidthClass="max-w-4xl"
    >
        <template #body>
            <div class="space-y-6">
                <!-- Basic Information -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label for="username" class="label">Username *</label>
                        <div class="relative mt-1">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <IconUser class="h-4 w-4 text-gray-400" />
                            </div>
                            <input
                                id="username"
                                v-model="formData.username"
                                type="text"
                                class="input-field pl-10"
                                placeholder="Enter username"
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <label for="password" class="label">Password *</label>
                        <div class="relative mt-1">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <IconLock class="h-4 w-4 text-gray-400" />
                            </div>
                            <input
                                id="password"
                                v-model="formData.password"
                                type="password"
                                class="input-field pl-10"
                                placeholder="Enter password"
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <label for="email" class="label">Email</label>
                        <div class="relative mt-1">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <IconMail class="h-4 w-4 text-gray-400" />
                            </div>
                            <input
                                id="email"
                                v-model="formData.email"
                                type="email"
                                class="input-field pl-10"
                                placeholder="user@example.com"
                            />
                        </div>
                    </div>

                    <div>
                        <label for="ui-level" class="label">UI Level</label>
                        <SimpleSelectMenu
                            v-model="formData.user_ui_level"
                            :options="uiLevelOptions"
                            class="mt-1"
                        />
                    </div>
                </div>

                <!-- Roles -->
                <div class="flex items-center gap-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                    <div class="flex items-center gap-2">
                        <input
                            id="is-admin"
                            v-model="formData.is_admin"
                            type="checkbox"
                            class="checkbox"
                        />
                        <label for="is-admin" class="label mb-0 cursor-pointer flex items-center gap-2">
                            <IconShieldCheck class="w-4 h-4 text-blue-600 dark:text-blue-400" />
                            Admin
                        </label>
                    </div>
                    <div class="flex items-center gap-2">
                        <input
                            id="is-moderator"
                            v-model="formData.is_moderator"
                            type="checkbox"
                            class="checkbox"
                        />
                        <label for="is-moderator" class="label mb-0 cursor-pointer flex items-center gap-2">
                            <IconShieldCheck class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                            Moderator
                        </label>
                    </div>
                </div>

                <!-- Advanced Settings Toggle -->
                <div class="border-t pt-4">
                    <button
                        @click="showAdvancedSettings = !showAdvancedSettings"
                        type="button"
                        class="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
                    >
                        {{ showAdvancedSettings ? '▼' : '▶' }} Advanced Settings
                    </button>
                </div>

                <!-- Advanced Settings -->
                <div v-if="showAdvancedSettings" class="space-y-6 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg border">
                    <!-- LLM Settings -->
                    <div>
                        <h4 class="font-semibold text-sm mb-3">LLM Settings</h4>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="label">Model</label>
                                <SimpleSelectMenu
                                    v-model="formData.lollms_model_name"
                                    :options="[{ value: null, label: 'Use Default' }, ...availableModels]"
                                />
                            </div>
                            <div>
                                <label class="label">Context Size</label>
                                <input v-model.number="formData.llm_ctx_size" type="number" class="input-field" placeholder="Default" />
                            </div>
                            <div>
                                <label class="label">Temperature</label>
                                <input v-model.number="formData.llm_temperature" type="number" step="0.1" class="input-field" placeholder="Default" />
                            </div>
                            <div>
                                <label class="label">Top K</label>
                                <input v-model.number="formData.llm_top_k" type="number" class="input-field" placeholder="Default" />
                            </div>
                        </div>
                    </div>

                    <!-- RAG Settings -->
                    <div>
                        <h4 class="font-semibold text-sm mb-3">RAG Settings</h4>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="label">Top K</label>
                                <input v-model.number="formData.rag_top_k" type="number" class="input-field" placeholder="Default" />
                            </div>
                            <div>
                                <label class="label">Max Length</label>
                                <input v-model.number="formData.max_rag_len" type="number" class="input-field" placeholder="Default" />
                            </div>
                            <div>
                                <label class="label">Use Graph</label>
                                <SimpleSelectMenu
                                    v-model="formData.rag_use_graph"
                                    :options="[
                                        { value: null, label: 'Default' },
                                        { value: true, label: 'Yes' },
                                        { value: false, label: 'No' }
                                    ]"
                                />
                            </div>
                            <div>
                                <label class="label">Response Type</label>
                                <SimpleSelectMenu
                                    v-model="formData.rag_graph_response_type"
                                    :options="[{ value: null, label: 'Default' }, ...ragResponseTypes]"
                                />
                            </div>
                        </div>
                    </div>

                    <!-- Feature Flags -->
                    <div>
                        <h4 class="font-semibold text-sm mb-3">Features</h4>
                        <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input v-model="formData.auto_title" type="checkbox" class="checkbox" />
                                <span class="text-sm">Auto Title</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input v-model="formData.fun_mode" type="checkbox" class="checkbox" />
                                <span class="text-sm">Fun Mode</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input v-model="formData.memory_enabled" type="checkbox" class="checkbox" />
                                <span class="text-sm">Memory</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input v-model="formData.image_generation_enabled" type="checkbox" class="checkbox" />
                                <span class="text-sm">Image Gen</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input v-model="formData.web_search_enabled" type="checkbox" class="checkbox" />
                                <span class="text-sm">Web Search</span>
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer">
                                <input v-model="formData.reasoning_activation" type="checkbox" class="checkbox" />
                                <span class="text-sm">Reasoning</span>
                            </label>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('adminCreateUser')" type="button" class="btn btn-secondary">
                    Cancel
                </button>
                <button @click="handleSubmit" type="button" class="btn btn-primary" :disabled="isLoading">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                    Create User
                </button>
            </div>
        </template>
    </GenericModal>
</template>