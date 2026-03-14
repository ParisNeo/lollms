<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useNotesStore } from '../../stores/notes';
import GenericModal from './GenericModal.vue';
import IconMail from '../../assets/icons/IconMail.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const notesStore = useNotesStore();

const modalData = computed(() => uiStore.modalData('emailNotes'));
const noteIds = computed(() => modalData.value?.noteIds || []);
const recipientEmail = ref('');
const isSending = ref(false);

async function copyAsRichText(html) {
    try {
        // We create a blob with the HTML type to let the OS know it's formatted text
        const blob = new Blob([html], { type: 'text/html' });
        const data = [new ClipboardItem({ 'text/html': blob })];
        await navigator.clipboard.write(data);
        uiStore.addNotification("Formatted notes copied! You can now paste them directly into your email body.", "success", 5000);
    } catch (err) {
        console.error('Failed to copy rich text:', err);
        // Fallback to raw HTML copy if Rich Copy fails
        uiStore.copyToClipboard(html, "Rich copy failed. Raw HTML copied instead.");
    }
}

async function handleSend(mode = 'standard') {
    if (!recipientEmail.value) return;
    isSending.value = true;
    try {
        const result = await notesStore.emailNotes(noteIds.value, recipientEmail.value);
        
        if (result && (result.manual_mode || mode === 'gmail' || mode === 'copy')) {
            // 1. If user just wants to copy to clipboard
            if (mode === 'copy') {
                await copyAsRichText(result.html);
                uiStore.closeModal('emailNotes');
                return;
            }

            // 2. Prepare URL components
            const subject = encodeURIComponent(result.subject);
            const recipient = encodeURIComponent(result.recipient);
            
            // Note: We leave the body empty in the URL because we'll use the clipboard 
            // to provide high-quality Rich Text instead of messy raw text.

            if (mode === 'gmail') {
                // Open Gmail tab
                const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${recipient}&su=${subject}`;
                window.open(gmailUrl, '_blank');
                
                // Copy Rich Text to clipboard automatically
                await copyAsRichText(result.html);
                uiStore.addNotification("Gmail opened! Just press Paste (Ctrl+V) in the message body.", "info", 6000);
            } else {
                // Standard Mailto (Local App like Outlook/Mail.app)
                window.location.href = `mailto:${result.recipient}?subject=${subject}`;
                
                // Copy Rich Text to clipboard automatically
                await copyAsRichText(result.html);
                uiStore.addNotification("Opening your mail app. Press Paste (Ctrl+V) to insert the formatted notes.", "info", 6000);
            }
        }
        
        uiStore.closeModal('emailNotes');
    } finally {
        isSending.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="emailNotes" title="Email Notes" maxWidthClass="max-w-md">
        <template #body>
            <div class="space-y-4">
                <p class="text-sm text-gray-500">Sending {{ noteIds.length }} note(s) as a formatted email.</p>
                <div>
                    <label class="label">Recipient Email</label>
                    <div class="relative mt-1">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <IconMail class="h-4 w-4 text-gray-400" />
                        </div>
                        <input
                            v-model="recipientEmail"
                            type="email"
                            class="input-field pl-10"
                            placeholder="colleague@example.com"
                            required
                            @keyup.enter="handleSend"
                        />
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex flex-col sm:flex-row gap-2 w-full justify-end">
                <button @click="uiStore.closeModal('emailNotes')" class="btn btn-secondary order-4 sm:order-1">Cancel</button>

                <button @click="handleSend('copy')" class="btn btn-secondary flex items-center gap-2 order-3 sm:order-2" :disabled="!recipientEmail || isSending">
                    <IconCopy class="w-4 h-4" />
                    Copy Formatted
                </button>

                <button @click="handleSend('gmail')" class="btn btn-secondary flex items-center gap-2 order-2 sm:order-3" :disabled="!recipientEmail || isSending">
                    <img src="https://ssl.gstatic.com/ui/v1/icons/mail/images/favicon5.ico" class="w-4 h-4" alt="Gmail" />
                    Compose in Gmail
                </button>

                <button @click="handleSend('standard')" class="btn btn-primary order-1 sm:order-4" :disabled="!recipientEmail || isSending">
                    <IconAnimateSpin v-if="isSending" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isSending ? 'Preparing...' : 'Send via System' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>