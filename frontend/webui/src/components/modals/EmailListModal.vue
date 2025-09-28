# [UPDATE] frontend/webui/src/components/modals/EmailListModal.vue
<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('emailList'));

const allEligibleUsers = ref([]);
const selectedUserIds = ref([]);
const selectAll = ref(true);
const separator = ref(',');

onMounted(() => {
    allEligibleUsers.value = props.value?.users || [];
    selectedUserIds.value = allEligibleUsers.value.map(u => u.id);
});

watch(selectAll, (newValue) => {
    if (newValue) {
        selectedUserIds.value = allEligibleUsers.value.map(u => u.id);
    } else {
        selectedUserIds.value = [];
    }
});

watch(selectedUserIds, (newSelection) => {
    if (newSelection.length === allEligibleUsers.value.length && newSelection.length > 0) {
        selectAll.value = true;
    } else if (newSelection.length === 0) {
        selectAll.value = false;
    }
}, { deep: true });

const selectedEmails = computed(() => {
    return allEligibleUsers.value
        .filter(user => selectedUserIds.value.includes(user.id))
        .map(user => user.email)
        .filter(Boolean); // Filter out any null/undefined emails
});

const emailsAsString = computed(() => selectedEmails.value.join(separator.value + ' '));
const mailtoLink = computed(() => `mailto:?bcc=${selectedEmails.value.join(',')}`);

const listCopied = ref(false);

function copyEmailList() {
    if (selectedEmails.value.length === 0) return;
    uiStore.copyToClipboard(emailsAsString.value).then((success) => {
        if (success) {
            listCopied.value = true;
            setTimeout(() => {
                listCopied.value = false;
            }, 2000);
        }
    });
}
</script>

<template>
    <GenericModal
        modal-name="emailList"
        title="Copy Email List"
        @close="uiStore.closeModal('emailList')"
        maxWidthClass="max-w-2xl"
    >
        <template #body>
            <div class="p-6 space-y-4">
                <div class="space-y-2">
                     <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300">Recipients ({{ selectedUserIds.length }} / {{ allEligibleUsers.length }})</h4>
                    <div class="relative border border-gray-200 dark:border-gray-600 rounded-md">
                        <div class="flex items-center p-2 border-b border-gray-200 dark:border-gray-600">
                            <input id="select-all-manual" type="checkbox" v-model="selectAll" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                            <label for="select-all-manual" class="ml-3 block text-sm font-medium text-gray-700 dark:text-gray-200">Select All</label>
                        </div>
                        <div class="max-h-60 overflow-y-auto">
                            <div v-if="allEligibleUsers.length > 0" class="divide-y divide-gray-200 dark:divide-gray-600">
                                <div v-for="user in allEligibleUsers" :key="user.id" class="p-2 flex items-center">
                                    <input :id="`manual-user-${user.id}`" type="checkbox" :value="user.id" v-model="selectedUserIds" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                                    <label :for="`manual-user-${user.id}`" class="ml-3 text-sm text-gray-600 dark:text-gray-300">
                                        <span class="font-medium">{{ user.username }}</span> ({{ user.email }})
                                    </label>
                                </div>
                            </div>
                            <div v-else class="p-4 text-center text-sm text-gray-500">
                                No users to list.
                            </div>
                        </div>
                    </div>
                </div>

                <div>
                    <div class="flex items-center justify-between mb-1">
                        <label for="email-list-area" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Selected Emails</label>
                        <div class="flex items-center gap-2">
                            <label for="separator" class="text-sm">Separator:</label>
                            <select id="separator" v-model="separator" class="input-field !py-1 !px-2 text-sm">
                                <option value=",">Comma</option>
                                <option value=";">Semicolon</option>
                            </select>
                        </div>
                    </div>
                    <textarea
                        id="email-list-area"
                        :value="emailsAsString"
                        rows="5"
                        readonly
                        class="input-field mt-1 font-mono text-xs"
                        placeholder="Select users to see their emails here..."
                    ></textarea>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-between items-center w-full">
                 <a 
                    :href="mailtoLink" 
                    target="_blank"
                    class="btn btn-secondary"
                    :class="{'opacity-50 cursor-not-allowed': selectedEmails.length === 0}"
                    @click.prevent="selectedEmails.length > 0 && (window.location.href = mailtoLink)"
                >
                    Open in Email App
                </a>
                <div class="flex-grow"></div>
                <div class="flex space-x-3">
                    <button 
                        type="button" 
                        @click="copyEmailList" 
                        class="btn"
                        :class="listCopied ? 'btn-success' : 'btn-secondary'"
                        :disabled="selectedEmails.length === 0"
                    >
                        {{ listCopied ? 'Copied!' : 'Copy List' }}
                    </button>
                    <button type="button" class="btn btn-primary" @click="uiStore.closeModal('emailList')">
                        Done
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>