<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from './GenericModal.vue';
import WysiwygEditor from '../ui/WysiwygEditor.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const modalProps = computed(() => uiStore.modalData('newsArticleEditor'));
const article = computed(() => modalProps.value?.article);

const form = ref({ title: '', content: '', fun_fact: '' });
const isLoading = ref(false);

watch(article, (newArticle) => {
    if (newArticle) {
        form.value = {
            title: newArticle.title,
            content: newArticle.content,
            fun_fact: newArticle.fun_fact,
        };
    }
}, { immediate: true });

async function handleSubmit() {
    if (!article.value) return;
    isLoading.value = true;
    try {
        await adminStore.updateNewsArticle(article.value.id, form.value);
        uiStore.closeModal('newsArticleEditor');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="newsArticleEditor" :title="`Edit Article: ${article?.title.substring(0, 30)}...`" maxWidthClass="max-w-4xl">
        <template #body>
            <form v-if="article" @submit.prevent="handleSubmit" class="space-y-4">
                <div>
                    <label for="article-title" class="label">Title</label>
                    <input id="article-title" v-model="form.title" type="text" class="input-field mt-1">
                </div>
                <div>
                    <label for="article-content" class="label">Content (Markdown)</label>
                    <WysiwygEditor v-model="form.content" class="mt-1"/>
                </div>
                <div>
                    <label for="article-funfact" class="label">Fun Fact</label>
                    <textarea id="article-funfact" v-model="form.fun_fact" rows="2" class="input-field mt-1"></textarea>
                </div>
            </form>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('newsArticleEditor')" class="btn btn-secondary">Cancel</button>
            <button @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">{{ isLoading ? 'Saving...' : 'Save Changes' }}</button>
        </template>
    </GenericModal>
</template>