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
        
        if (result) {
            // 1. If user just wants to copy to clipboard
            if (mode === 'copy') {
                await copyAsRichText(result.html);
                // DO NOT close the modal here, allowing further actions
                return;
            }

            // 2. Prepare URL components
            const subject = encodeURIComponent(result.subject);
            const recipient = encodeURIComponent(result.recipient);
            
            if (mode === 'gmail') {
                // Open Gmail tab
                const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${recipient}&su=${subject}`;
                window.open(gmailUrl, '_blank');
                
                // Copy Rich Text to clipboard automatically so they just have to paste
                await copyAsRichText(result.html);
                uiStore.addNotification("Gmail opened! Press Paste (Ctrl+V) in the body.", "info", 6000);
            } else {
                // Standard Mailto (Local App like Outlook/Mail.app)
                window.location.href = `mailto:${result.recipient}?subject=${subject}`;
                
                // Copy Rich Text to clipboard automatically
                await copyAsRichText(result.html);
                uiStore.addNotification("Local mail app opened. Press Paste (Ctrl+V) to insert notes.", "info", 6000);
            }
        }
        
        uiStore.closeModal('emailNotes');
    } finally {
        isSending.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="emailNotes" title="Export to Email" maxWidthClass="max-w-lg">
        <template #body>
            <div class="space-y-5">
                <!-- Security Note -->
                <div class="p-4 bg-amber-50 dark:bg-amber-900/20 border-l-4 border-amber-500 rounded-r-xl">
                    <div class="flex items-center gap-2 text-amber-800 dark:text-amber-200 mb-1">
                        <IconShieldCheck class="w-5 h-5" />
                        <span class="text-sm font-bold uppercase tracking-tight">Security & Privacy Policy</span>
                    </div>
                    <p class="text-xs text-amber-700/80 dark:text-amber-300/80 leading-relaxed">
                        To protect your account and prevent unauthorized mail delivery, LoLLMs does not send emails directly from the server.
                        Instead, we prepare the content so you can safely send it using your own local tools or Gmail.
                    </p>
                </div>

                <div class="space-y-1">
                    <label class="text-[10px] font-black uppercase text-gray-400 tracking-widest px-1">Recipient Address</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                            <IconMail class="h-4 w-4 text-gray-400" />
                        </div>
                        <input
                            v-model="recipientEmail"
                            type="email"
                            class="input-field pl-11 !rounded-xl"
                            placeholder="recipient@example.com"
                            required
                            @keyup.enter="handleSend('standard')"
                        />
                    </div>
                </div>

                <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700">
                    <p class="text-[11px] text-gray-500 dark:text-gray-400">
                        <b>Selected:</b> {{ noteIds.length }} note(s) will be merged into a single document.
                    </p>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between w-full gap-3 pt-2">
                <button @click="uiStore.closeModal('emailNotes')" class="px-4 py-2 text-sm font-bold text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
                    Cancel
                </button>

                <div class="flex flex-col sm:flex-row gap-2">
                    <button @click="handleSend('copy')" class="btn btn-secondary flex items-center justify-center gap-2 !rounded-xl border-gray-200 shadow-sm" :disabled="!recipientEmail || isSending">
                        <IconCopy class="w-4 h-4 text-gray-500" />
                        <span>Copy Formatted</span>
                    </button>

                    <button @click="handleSend('gmail')" class="btn btn-secondary flex items-center justify-center gap-2 !rounded-xl border-gray-200 shadow-sm" :disabled="!recipientEmail || isSending">
                        <img src="https://ssl.gstatic.com/ui/v1/icons/mail/images/favicon5.ico" class="w-4 h-4" alt="Gmail" />
                        <span>Gmail</span>
                    </button>

                    <button @click="handleSend('standard')" class="btn btn-primary flex items-center justify-center gap-2 !rounded-xl shadow-lg" :disabled="!recipientEmail || isSending">
                        <IconAnimateSpin v-if="isSending" class="w-4 h-4 animate-spin" />
                        <IconShare v-else class="w-4 h-4" />
                        <span>Open Mail App</span>
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>