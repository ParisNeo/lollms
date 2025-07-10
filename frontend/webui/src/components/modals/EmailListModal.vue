<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalProps);
const emails = computed(() => props.value?.emails || []);

const emailsAsString = computed(() => emails.value.join(', '));
const mailtoLink = computed(() => `mailto:?bcc=${emails.value.join(',')}`);

const listCopied = ref(false);

function copyEmailList() {
    navigator.clipboard.writeText(emailsAsString.value).then(() => {
        listCopied.value = true;
        setTimeout(() => {
            listCopied.value = false;
        }, 2000);
    });
}
</script>

<template>
    <GenericModal
        modal-name="emailList"
        title="User Email List"
        @close="uiStore.closeModal('emailList')"
        maxWidthClass="max-w-xl"
    >
        <template #body>
            <div class="p-6 space-y-4">
                <p class="text-sm text-gray-600 dark:text-gray-300">
                    The SMTP server is not configured, so emails cannot be sent automatically.
                    You can copy the list of user emails below and paste it into the "BCC" field of your preferred email client.
                </p>
                <div v-if="emails.length > 0">
                    <label for="email-list-area" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Emails of Opted-in Users</label>
                    <textarea
                        id="email-list-area"
                        :value="emailsAsString"
                        rows="8"
                        readonly
                        class="input-field mt-1 font-mono text-xs"
                    ></textarea>
                </div>
                <div v-else class="text-center text-gray-500 py-4">
                    No users have opted-in to receive emails.
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-between items-center w-full">
                 <a 
                    v-if="emails.length > 0"
                    :href="mailtoLink" 
                    target="_blank"
                    class="btn btn-secondary"
                >
                    Open in Email App
                </a>
                <div class="flex-grow"></div>
                <div class="flex space-x-3">
                    <button 
                        v-if="emails.length > 0"
                        type="button" 
                        @click="copyEmailList" 
                        class="btn"
                        :class="listCopied ? 'btn-success' : 'btn-secondary'"
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