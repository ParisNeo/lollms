
<template>
    <GenericModal modal-name="bluetoothImage" title="Receive Image over Bluetooth" max-width-class="max-w-3xl">
        <template #body>
            <div class="space-y-5">
                <!-- Capability notice -->
                <div
                    v-if="!isBluetoothSupported"
                    class="rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/30 p-3 text-xs text-amber-800 dark:text-amber-200"
                >
                    This browser does not expose the Web Bluetooth API. Use the <strong>Operating-System transfer</strong>
                    section below — the file your phone sends over classic Bluetooth lands here in one click.
                </div>

                <!-- 1. BLE (Web Bluetooth GATT) path -->
                <section class="rounded-2xl border dark:border-gray-700 p-4 space-y-3">
                    <header class="flex items-start justify-between gap-3">
                        <div>
                            <h3 class="text-sm font-black uppercase tracking-widest text-gray-700 dark:text-gray-200 flex items-center gap-2">
                                <IconBluetooth class="w-4 h-4 text-blue-600" />
                                Option A — Bluetooth LE device
                            </h3>
                            <p class="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                                Pair with a BLE device that exposes an image characteristic, then read the picture directly.
                            </p>
                        </div>
                    </header>

                    <div class="flex flex-wrap items-center gap-2">
                        <button
                            type="button"
                            class="btn btn-primary btn-sm flex items-center gap-1.5"
                            :disabled="isScanning || bleState === 'reading'"
                            @click="scanBleDevice"
                        >
                            <IconAnimateSpin v-if="isScanning || bleState === 'reading'" class="w-4 h-4 animate-spin" />
                            <IconBluetooth v-else class="w-4 h-4" />
                            <span>{{ isScanning ? 'Scanning…' : (bleState === 'reading' ? 'Reading…' : 'Scan & Read') }}</span>
                        </button>
                        <span v-if="bleDeviceName" class="text-[11px] font-mono text-gray-600 dark:text-gray-300">
                            {{ bleDeviceName }}
                        </span>
                    </div>

                    <p v-if="bleMessage" class="text-[11px]" :class="bleError ? 'text-rose-600 dark:text-rose-400' : 'text-gray-500 dark:text-gray-400'">
                        {{ bleMessage }}
                    </p>
                </section>

                <!-- 2. Classic Bluetooth (OS-assisted OPP) -->
                <section class="rounded-2xl border dark:border-gray-700 p-4 space-y-3">
                    <header>
                        <h3 class="text-sm font-black uppercase tracking-widest text-gray-700 dark:text-gray-200 flex items-center gap-2">
                            <IconBluetooth class="w-4 h-4 text-indigo-600" />
                            Option B — Phone photo transfer (classic Bluetooth)
                        </h3>
                        <p class="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                            Phones send photos with the classic Bluetooth <em>Object Push</em> profile. The OS receives
                            the file; drop it here (or use the file picker) and it is added to your gallery.
                        </p>
                    </header>

                    <!-- Receive zone -->
                    <div
                        @dragover.prevent="onDragOver"
                        @dragleave.prevent="onDragLeave"
                        @drop.prevent="onDrop"
                        @click="openPicker"
                        class="relative rounded-2xl border-2 border-dashed transition-colors cursor-pointer flex flex-col items-center justify-center gap-2 py-8 px-4 text-center"
                        :class="isDragOver
                            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                            : 'border-gray-300 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-500'"
                    >
                        <IconArrowUpTray class="w-8 h-8 text-gray-400" />
                        <p class="text-sm font-bold text-gray-700 dark:text-gray-200">Drop the received image here</p>
                        <p class="text-[11px] text-gray-500 dark:text-gray-400">or click to choose a file</p>
                        <input
                            ref="fileInputRef"
                            type="file"
                            accept="image/*"
                            multiple
                            class="hidden"
                            @change="onPickerChange"
                        />
                    </div>

                    <!-- OS helper steps -->
                    <details class="text-[11px] text-gray-600 dark:text-gray-300">
                        <summary class="cursor-pointer font-bold select-none">How to send a photo from your phone</summary>
                        <ol class="list-decimal list-inside space-y-1 mt-2">
                            <li>On this computer, open the OS Bluetooth file receive (Windows: <em>Settings → Bluetooth &amp; devices → “Send or receive files”</em>).</li>
                            <li>On your phone, pair with this computer and share the photo via Bluetooth.</li>
                            <li>When the transfer saves the file, drag it into the zone above (or paste it with <kbd>Ctrl</kbd>+<kbd>V</kbd>).</li>
                        </ol>
                    </details>
                </section>

                <!-- Received files preview -->
                <div v-if="receivedFiles.length" class="rounded-2xl border dark:border-gray-700 p-4 space-y-3">
                    <h3 class="text-sm font-black uppercase tracking-widest text-gray-700 dark:text-gray-200">
                        Ready to import ({{ receivedFiles.length }})
                    </h3>
                    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        <div
                            v-for="(item, i) in receivedFiles"
                            :key="item.url"
                            class="relative rounded-xl overflow-hidden border dark:border-gray-700 aspect-square bg-gray-100 dark:bg-gray-800"
                        >
                            <img :src="item.url" :alt="item.file.name" class="w-full h-full object-cover" />
                            <button
                                type="button"
                                class="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/70 hover:bg-rose-600 text-white flex items-center justify-center"
                                title="Remove"
                                @click.stop="removeReceived(i)"
                            >
                                <IconXMark class="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #footer>
            <button class="btn btn-secondary" @click="closeModal">Cancel</button>
            <div class="grow"></div>
            <button
                class="btn btn-primary flex items-center gap-2"
                :disabled="isSaving || receivedFiles.length === 0"
                @click="saveReceived"
            >
                <IconAnimateSpin v-if="isSaving" class="w-4 h-4 animate-spin" />
                <IconCheckCircle v-else class="w-4 h-4" />
                <span>Add {{ receivedFiles.length || '' }} to Gallery</span>
            </button>
        </template>
    </GenericModal>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useImageStore } from '../../stores/images';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconBluetooth from '../../assets/icons/IconBluetooth.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const uiStore = useUiStore();
const imageStore = useImageStore();

const MODAL_NAME = 'bluetoothImage';

// ── Web Bluetooth (BLE GATT) state ─────────────────────────────────────────
const isBluetoothSupported = computed(
    () => typeof navigator !== 'undefined' && !!navigator.bluetooth
);
const isScanning = ref(false);
const bleState = ref('idle'); // idle | connected | reading
const bleDeviceName = ref('');
const bleMessage = ref('');
const bleError = ref(false);
let activeDevice = null;

// Common GATT services worth requesting so we can serve a broad range of
// devices. A characteristic can only be read when its service is declared
// up-front, so this list is intentionally generous (device info, battery,
// generic access, and vendor-agnostic custom spaces).
const OPTIONAL_GATT_SERVICES = [
    0x1800, // Generic Access
    0x1801, // Generic Attribute
    0x180a, // Device Information
    0x180f, // Battery Service
    0xffe0, // Common vendor "UART" service
    0xffe1,
    0xfff0,
    0xfff1,
    0xfe59, // Nordic
];

// Image magic-number sniffing so we only accept genuine image payloads and
// never accidentally ingest arbitrary device telemetry as an "image".
function looksLikeImage(bytes) {
    if (!bytes || bytes.length < 4) return false;
    const isJpeg = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
    const isPng = bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47;
    const isGif = bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46;
    const isWebp = bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46;
    return isJpeg || isPng || isGif || isWebp;
}

function bytesToFile(bytes, name) {
    const type = bytes[0] === 0xff ? 'image/jpeg'
        : bytes[0] === 0x89 ? 'image/png'
        : bytes[0] === 0x47 ? 'image/gif'
        : 'image/webp';
    const blob = new Blob([bytes], { type });
    return new File([blob], name, { type });
}

async function scanBleDevice() {
    bleError.value = false;
    bleMessage.value = '';
    if (!isBluetoothSupported.value) {
        bleError.value = true;
        bleMessage.value = 'Web Bluetooth is not available in this browser.';
        return;
    }
    isScanning.value = true;
    try {
        // requestDevice() must be called synchronously from the click handler.
        const device = await navigator.bluetooth.requestDevice({
            acceptAllDevices: true,
            optionalServices: OPTIONAL_GATT_SERVICES,
        });
        activeDevice = device;
        bleDeviceName.value = device.name || 'Unnamed BLE device';
        bleState.value = 'connected';
        bleMessage.value = 'Connected. Scanning for an image characteristic…';
        await readImageFromDevice(device);
    } catch (err) {
        bleError.value = true;
        bleMessage.value = describeBleError(err);
    } finally {
        isScanning.value = false;
    }
}

async function readImageFromDevice(device) {
    bleState.value = 'reading';
    try {
        const server = await device.gatt.connect();
        const services = await server.getPrimaryServices();
        for (const service of services) {
            let characteristics;
            try {
                characteristics = await service.getCharacteristics();
            } catch {
                continue;
            }
            for (const ch of characteristics) {
                if (!ch.properties || !ch.properties.read) continue;
                let value;
                try {
                    value = await ch.readValue();
                } catch {
                    continue;
                }
                const bytes = new Uint8Array(value.buffer);
                if (looksLikeImage(bytes)) {
                    addReceivedFile(
                        bytesToFile(bytes, `bluetooth_image_${Date.now()}.${bytes[0] === 0x89 ? 'png' : 'jpg'}`)
                    );
                    bleMessage.value = 'Image received from the BLE device.';
                    bleState.value = 'connected';
                    return;
                }
            }
        }
        bleError.value = true;
        bleMessage.value =
            'No image characteristic found on this device. Use Option B to transfer a phone photo.';
        bleState.value = 'connected';
    } catch (err) {
        bleError.value = true;
        bleMessage.value = describeBleError(err);
        bleState.value = 'idle';
    } finally {
        try {
            if (activeDevice?.gatt?.connected) activeDevice.gatt.disconnect();
        } catch {
            /* non-fatal */
        }
    }
}

function describeBleError(err) {
    const name = err?.name || '';
    if (name === 'NotFoundError') return 'No device was selected.';
    if (name === 'SecurityError') return 'Bluetooth access blocked by the browser or a permissions policy.';
    if (name === 'NetworkError' || name === 'InvalidStateError') return 'The device rejected the connection.';
    return err?.message || 'Bluetooth operation failed.';
}

// ── Received-file staging (shared by both options) ─────────────────────────
// Each entry is a wrapper { file, url } so the object-URL preview can be
// revoked deterministically without mutating the File host object (which is
// not reliably extensible across browsers).
const receivedFiles = ref([]);

function addReceivedFile(file) {
    if (!file || !file.type?.startsWith('image/')) return;
    receivedFiles.value.push({ file, url: URL.createObjectURL(file) });
}

function removeReceived(index) {
    const item = receivedFiles.value[index];
    if (item?.url) URL.revokeObjectURL(item.url);
    receivedFiles.value.splice(index, 1);
}

// ── Drag / drop / picker / paste ───────────────────────────────────────────
const isDragOver = ref(false);
const fileInputRef = ref(null);

function onDragOver() {
    isDragOver.value = true;
}
function onDragLeave() {
    isDragOver.value = false;
}
function onDrop(event) {
    isDragOver.value = false;
    if (event?.dataTransfer?.files) ingestImageFiles(Array.from(event.dataTransfer.files));
}
function openPicker() {
    fileInputRef.value?.click();
}
function onPickerChange(event) {
    if (event?.target?.files) ingestImageFiles(Array.from(event.target.files));
    if (fileInputRef.value) fileInputRef.value.value = '';
}

function ingestImageFiles(files) {
    let added = 0;
    for (const f of files) {
        if (f.type?.startsWith('image/')) {
            addReceivedFile(f);
            added++;
        }
    }
    if (added === 0 && files.length > 0) {
        uiStore.addNotification('Only image files can be imported.', 'warning');
    }
}

// Global paste handler — the OS often copies the received file to the clipboard.
function onPaste(event) {
    if (!uiStore.isModalOpen(MODAL_NAME)) return;
    const items = event.clipboardData?.items || [];
    const files = [];
    for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
            const f = item.getAsFile();
            if (f) files.push(f);
        }
    }
    if (files.length) {
        event.preventDefault();
        ingestImageFiles(files);
    }
}
window.addEventListener('paste', onPaste);

// ── Save into the gallery ──────────────────────────────────────────────────
const isSaving = ref(false);

async function saveReceived() {
    if (!receivedFiles.value.length) return;
    isSaving.value = true;
    try {
        await imageStore.uploadImages(receivedFiles.value.map((item) => item.file));
        uiStore.addNotification(
            `${receivedFiles.value.length} image(s) added to the gallery.`,
            'success'
        );
        closeModal();
    } catch (err) {
        uiStore.addNotification('Failed to add the received image(s).', 'error');
    } finally {
        isSaving.value = false;
    }
}

function closeModal() {
    receivedFiles.value.forEach((item) => item.url && URL.revokeObjectURL(item.url));
    receivedFiles.value = [];
    bleDeviceName.value = '';
    bleMessage.value = '';
    bleError.value = false;
    bleState.value = 'idle';
    uiStore.closeModal(MODAL_NAME);
}

onUnmounted(() => {
    window.removeEventListener('paste', onPaste);
    receivedFiles.value.forEach((item) => item.url && URL.revokeObjectURL(item.url));
    if (activeDevice?.gatt?.connected) {
        try { activeDevice.gatt.disconnect(); } catch { /* non-fatal */ }
    }
});
</script>
