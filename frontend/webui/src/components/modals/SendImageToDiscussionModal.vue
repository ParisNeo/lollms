<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useImageStore } from '../../stores/images';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconArrowsUpDown from '../../assets/icons/IconArrowsUpDown.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMessage from '../../assets/icons/IconMessage.vue';

const MODAL_NAME = 'sendImageToDiscussion';

const discussionsStore = useDiscussionsStore();
const imageStore = useImageStore();
const uiStore = useUiStore();

const modalData = computed(() => uiStore.modalProps?.[MODAL_NAME] || {});
const imageIds = computed(() => modalData.value.imageIds || []);

// ── Discussion list state ──────────────────────────────────────────────────
const isLoading = ref(false);
const searchTerm = ref('');
const sortMode = ref('activity'); // 'activity' | 'alpha' | 'created'
const currentPage = ref(1);
const pageSize = 10;
const isSending = ref(false);
const sendingToId = ref(null);

async function ensureDiscussionsLoaded() {
    isLoading.value = true;
    try {
        // Reuse whatever the store already has; only hit the network if the
        // list is empty so opening the modal is instant in the common case.
        if (!discussionsStore.sortedDiscussions || discussionsStore.sortedDiscussions.length === 0) {
            await discussionsStore.fetchDiscussions();
        }
    } finally {
        isLoading.value = false;
    }
}

onMounted(ensureDiscussionsLoaded);

// Flatten shared and owned discussions into a single searchable list. Shared
// entries carry `share_id` and lack ownership-only fields, but expose the same
// `id`/`title` pair we need for the move operation.
const allDiscussions = computed(() => {
    const owned = (discussionsStore.sortedDiscussions || []).map(d => ({
        id: d.id,
        title: d.title || 'Untitled Discussion',
        updated_at: d.updated_at,
        created_at: d.created_at,
        is_shared: false,
    }));
    const shared = (discussionsStore.sharedWithMe || []).map(d => ({
        id: d.id,
        title: d.title || 'Untitled Discussion',
        updated_at: d.updated_at,
        created_at: d.created_at,
        is_shared: true,
    }));
    return [...owned, ...shared];
});

const filteredDiscussions = computed(() => {
    let list = allDiscussions.value;
    const q = searchTerm.value.trim().toLowerCase();
    if (q) {
        list = list.filter(d => d.title.toLowerCase().includes(q));
    }
    const sorted = [...list];
    if (sortMode.value === 'alpha') {
        sorted.sort((a, b) => a.title.localeCompare(b.title));
    } else if (sortMode.value === 'created') {
        sorted.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    } else {
        // activity (default)
        sorted.sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0));
    }
    return sorted;
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredDiscussions.value.length / pageSize)));

const paginatedDiscussions = computed(() => {
    const start = (currentPage.value - 1) * pageSize;
    return filteredDiscussions.value.slice(start, start + pageSize);
});

const visiblePageNumbers = computed(() => {
    const total = totalPages.value;
    const current = currentPage.value;
    const pages = [];
    if (total <= 7) {
        for (let i = 1; i <= total; i++) pages.push(i);
    } else {
        pages.push(1);
        const start = Math.max(2, current - 1);
        const end = Math.min(total - 1, current + 1);
        for (let i = start; i <= end; i++) {
            if (!pages.includes(i)) pages.push(i);
        }
        if (!pages.includes(total)) pages.push(total);
    }
    return pages;
});

// Reset to page 1 whenever the query or sort changes so the user never lands
// on an out-of-range page after filtering.
watch([searchTerm, sortMode], () => {
    currentPage.value = 1;
});

function goToPage(p) {
    if (p < 1 || p > totalPages.value || p === currentPage.value) return;
    currentPage.value = p;
    nextTick(() => {
        // Scroll the list back to top after a page change.
        document.getElementById('discussion-list-scroll')?.scrollTo({ top: 0 });
    });
}

function formatDate(iso) {
    if (!iso) return '';
    try {
        return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(iso));
    } catch {
        return '';
    }
}

async function sendTo(discussion) {
    if (!discussion || isSending.value) return;
    if (!imageIds.value.length) {
        uiStore.addNotification('No images selected.', 'warning');
        return;
    }
    sendingToId.value = discussion.id;
    isSending.value = true;
    try {
        await imageStore.moveImagesToDiscussionBatch(imageIds.value, discussion.id);
        uiStore.addNotification(
            imageIds.value.length === 1
                ? `Image sent to "${discussion.title}".`
                : `${imageIds.value.length} images sent to "${discussion.title}".`,
            'success'
        );
        closeModal();
    } catch (e) {
        const detail = e?.response?.data?.detail || 'Failed to send image to discussion.';
        uiStore.addNotification(detail, 'error');
    } finally {
        isSending.value = false;
        sendingToId.value = null;
    }
}

function closeModal() {
    uiStore.closeModal(MODAL_NAME);
}
</script>

<template>
    <GenericModal :modal-name="MODAL_NAME" title="Send to Discussion" max-width-class="max-w-2xl">
        <template #body>
            <div class="space-y-4">
                <!-- Summary strip -->
                <div class="flex items-center gap-2 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 px-3 py-2">
                    <IconSend class="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
                    <p class="text-xs text-blue-800 dark:text-blue-200 font-medium">
                        Sending <strong>{{ imageIds.length }}</strong> image{{ imageIds.length > 1 ? 's' : '' }} — pick a discussion below.
                    </p>
                </div>

                <!-- Search + Sort -->
                <div class="flex flex-col sm:flex-row gap-2">
                    <div class="relative grow">
                        <input
                            v-model="searchTerm"
                            type="text"
                            placeholder="Search discussions..."
                            class="input-field w-full !py-2 !pl-8 !text-sm"
                        />
                        <IconMagnifyingGlass class="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                        <button
                            v-if="searchTerm"
                            type="button"
                            @click="searchTerm = ''"
                            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-red-500"
                            title="Clear search"
                        >
                            <IconXMark class="w-3.5 h-3.5" />
                        </button>
                    </div>

                    <div class="relative shrink-0">
                        <select
                            v-model="sortMode"
                            class="input-field !py-2 !pl-8 !pr-6 !text-sm appearance-none cursor-pointer"
                            title="Sort discussions"
                        >
                            <option value="activity">Recent Activity</option>
                            <option value="created">Newest First</option>
                            <option value="alpha">Alphabetical</option>
                        </select>
                        <IconArrowsUpDown class="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                    </div>
                </div>

                <!-- Loading state -->
                <div v-if="isLoading" class="py-10 flex flex-col items-center justify-center text-gray-400">
                    <IconAnimateSpin class="w-6 h-6 animate-spin text-blue-500 mb-2" />
                    <p class="text-xs font-bold uppercase tracking-widest">Loading discussions...</p>
                </div>

                <!-- Empty state -->
                <div
                    v-else-if="paginatedDiscussions.length === 0"
                    class="py-10 flex flex-col items-center justify-center text-center text-gray-400"
                >
                    <IconMessage class="w-10 h-10 mb-2 opacity-30" />
                    <p class="text-sm font-bold">{{ searchTerm ? 'No discussions match your search.' : 'No discussions available.' }}</p>
                    <p class="text-xs mt-1">{{ searchTerm ? 'Try different keywords.' : 'Start a chat first, then send images here.' }}</p>
                </div>

                <!-- Discussion list -->
                <div v-else id="discussion-list-scroll" class="space-y-1.5">
                    <button
                        v-for="d in paginatedDiscussions"
                        :key="d.id"
                        type="button"
                        @click="sendTo(d)"
                        :disabled="isSending"
                        class="w-full text-left flex items-center gap-3 p-2.5 rounded-xl border transition-all group"
                        :class="[
                            sendingToId === d.id
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                                : 'border-gray-200 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50/60 dark:hover:bg-blue-900/20',
                            isSending && sendingToId !== d.id ? 'opacity-50 cursor-not-allowed' : ''
                        ]"
                    >
                        <div class="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
                            <IconMessage class="w-4 h-4" />
                        </div>
                        <div class="min-w-0 grow">
                            <div class="flex items-center gap-2">
                                <span class="text-sm font-bold text-gray-800 dark:text-gray-200 truncate">{{ d.title }}</span>
                                <span v-if="d.is_shared" class="px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-wider bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 shrink-0">Shared</span>
                            </div>
                            <span class="text-[10px] font-mono text-gray-400">{{ formatDate(d.updated_at || d.created_at) }}</span>
                        </div>
                        <IconAnimateSpin v-if="sendingToId === d.id" class="w-4 h-4 animate-spin text-blue-600 shrink-0" />
                        <IconSend v-else class="w-4 h-4 text-gray-300 group-hover:text-blue-500 transition-colors shrink-0" />
                    </button>
                </div>

                <!-- Pagination -->
                <div v-if="totalPages > 1" class="flex items-center justify-between gap-2 pt-2 border-t dark:border-gray-700">
                    <span class="text-[10px] font-mono text-gray-500">
                        Page {{ currentPage }} of {{ totalPages }} · {{ filteredDiscussions.length }} total
                    </span>
                    <div class="flex items-center gap-1">
                        <button
                            type="button"
                            @click="goToPage(currentPage - 1)"
                            :disabled="currentPage <= 1"
                            class="px-2.5 py-1 rounded-lg border dark:border-gray-700 text-[11px] font-bold disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        >
                            Prev
                        </button>
                        <button
                            v-for="p in visiblePageNumbers"
                            :key="p"
                            type="button"
                            @click="goToPage(p)"
                            class="w-7 h-7 rounded-lg text-[11px] font-mono font-bold flex items-center justify-center transition-all"
                            :class="currentPage === p ? 'bg-blue-600 text-white shadow-sm' : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'"
                        >
                            {{ p }}
                        </button>
                        <button
                            type="button"
                            @click="goToPage(currentPage + 1)"
                            :disabled="currentPage >= totalPages"
                            class="px-2.5 py-1 rounded-lg border dark:border-gray-700 text-[11px] font-bold disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        >
                            Next
                        </button>
                    </div>
                </div>
            </div>
        </template>

        <template #footer>
            <button class="btn btn-secondary" type="button" @click="closeModal" :disabled="isSending">Cancel</button>
        </template>
    </GenericModal>
</template>