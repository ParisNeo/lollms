<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import GenericModal from './GenericModal.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const uiStore = useUiStore();

const modalProps = computed(() => uiStore.modalData('funFact'));
const fact = computed(() => modalProps.value?.fact);
const preselectedCategoryId = computed(() => modalProps.value?.preselectedCategoryId);
const onSave = computed(() => modalProps.value?.onSave);

const form = ref({
    content: '',
    category_id: null
});

const isLoading = ref(false);
const categories = ref([]);

async function fetchCategories() {
    try {
        const res = await apiClient.get('/api/admin/fun-facts/categories');
        categories.value = res.data;
    } catch (e) {
        console.error("Failed to fetch categories:", e);
    }
}

watch(modalProps, async (props) => {
    if (props) {
        await fetchCategories();
        if (fact.value) {
            form.value = {
                content: fact.value.content,
                category_id: fact.value.category.id
            };
        } else {
            form.value = {
                content: '',
                category_id: preselectedCategoryId.value || (categories.value[0]?.id || null)
            };
        }
    }
}, { immediate: true });

async function handleSubmit() {
    if (!form.value.content.trim() || !form.value.category_id) return;
    isLoading.value = true;
    try {
        if (fact.value) {
            await apiClient.put(`/api/admin/fun-facts/${fact.value.id}`, form.value);
            uiStore.addNotification('Fun fact updated.', 'success');
        } else {
            await apiClient.post('/api/admin/fun-facts', form.value);
            uiStore.addNotification('Fun fact created.', 'success');
        }
        
        if (onSave.value) onSave.value();
        uiStore.closeModal('funFact');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="funFact" :title="fact ? 'Edit Fun Fact' : 'New Fun Fact'">
        <template #body>
            <form @submit.prevent="handleSubmit" class="p-6 space-y-6">
                <div>
                    <label for="fact-category" class="block text-sm font-medium">Category</label>
                    <select id="fact-category" v-model="form.category_id" class="input-field mt-1" required>
                        <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                    </select>
                </div>
                <div>
                    <label for="fact-content" class="block text-sm font-medium">Content (Markdown Supported)</label>
                    <textarea id="fact-content" v-model="form.content" rows="6" class="input-field mt-1" placeholder="Enter the fun fact here..." required></textarea>
                </div>

                <!-- Markdown Syntax Help -->
                <div class="bg-blue-50 dark:bg-gray-900/50 rounded-xl p-4 border border-blue-100 dark:border-gray-700">
                    <div class="flex items-center gap-2 mb-3 text-blue-700 dark:text-blue-400">
                        <IconInfo class="w-4 h-4" />
                        <span class="text-xs font-black uppercase tracking-widest">Formatting Guide</span>
                    </div>
                    <ul class="text-[11px] space-y-2 text-gray-600 dark:text-gray-400 font-mono">
                        <li><span class="font-sans font-bold text-gray-800 dark:text-gray-200">Link:</span> <code>[Site Name](https://...)</code></li>
                        <li><span class="font-sans font-bold text-gray-800 dark:text-gray-200">Image:</span> <code>![Alt Text](https://path/to/image.png)</code></li>
                        <li><span class="font-sans font-bold text-gray-800 dark:text-gray-200">Video:</span> <code>Just paste a YouTube URL on its own line</code></li>
                    </ul>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('funFact')" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">
                    {{ isLoading ? 'Saving...' : 'Save Fact' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>
