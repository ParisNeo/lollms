<template>
    <GenericModal modal-name="cameraCapture" title="Take a Photo" max-width-class="max-w-2xl">
        <template #body>
            <div class="relative aspect-video bg-black rounded-lg overflow-hidden">
                <video v-show="isStreaming && !capturedImage" ref="videoRef" autoplay playsinline class="w-full h-full object-contain"></video>
                <img v-if="capturedImage" :src="capturedImage" class="w-full h-full object-contain" alt="Captured Photo Preview">
                
                <div v-if="error" class="absolute inset-0 flex items-center justify-center text-white bg-black/50 p-4">
                    <p class="text-center">{{ error }}</p>
                </div>

                <div v-if="!isStreaming && !error" class="absolute inset-0 flex items-center justify-center text-white">
                    <p>Starting camera...</p>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('cameraCapture')" class="btn btn-secondary">Cancel</button>
            <div class="flex-grow"></div>
            <button v-if="isStreaming && !capturedImage" @click="capturePhoto" class="btn btn-primary">Take Photo</button>
            <button v-if="capturedImage" @click="retakePhoto" class="btn btn-secondary">Retake</button>
            <button v-if="capturedImage" @click="savePhoto" class="btn btn-primary" :disabled="isSaving">
                <IconAnimateSpin v-if="isSaving" class="w-5 h-5 mr-2 animate-spin" />
                Save Photo
            </button>
        </template>
    </GenericModal>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useImageStore } from '../../stores/images';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const imageStore = useImageStore();

const videoRef = ref(null);
const videoStream = ref(null);
const isStreaming = ref(false);
const error = ref(null);
const capturedImage = ref(null);
const isSaving = ref(false);

watch(() => uiStore.isModalOpen('cameraCapture'), (isOpen) => {
    if (isOpen) {
        startCamera();
    } else {
        stopCamera();
    }
});

onUnmounted(() => {
    stopCamera();
});

async function startCamera() {
    isStreaming.value = false;
    error.value = null;
    capturedImage.value = null;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        error.value = 'Camera access is not supported by your browser.';
        return;
    }

    try {
        videoStream.value = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.value) {
            videoRef.value.srcObject = videoStream.value;
            isStreaming.value = true;
        }
    } catch (err) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            error.value = 'Camera access was denied. Please allow camera permissions in your browser settings.';
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
            error.value = 'No camera found. Please ensure a camera is connected and enabled.';
        } else {
            error.value = 'An error occurred while accessing the camera.';
        }
        console.error("Camera access error:", err);
    }
}

function stopCamera() {
    if (videoStream.value) {
        videoStream.value.getTracks().forEach(track => track.stop());
        videoStream.value = null;
        isStreaming.value = false;
    }
}

function capturePhoto() {
    if (!videoRef.value) return;

    const canvas = document.createElement('canvas');
    canvas.width = videoRef.value.videoWidth;
    canvas.height = videoRef.value.videoHeight;
    const context = canvas.getContext('2d');
    context.drawImage(videoRef.value, 0, 0, canvas.width, canvas.height);
    
    capturedImage.value = canvas.toDataURL('image/jpeg');
}

function retakePhoto() {
    capturedImage.value = null;
}

function dataURLtoBlob(dataurl) {
    const arr = dataurl.split(',');
    const mimeMatch = arr[0].match(/:(.*?);/);
    if (!mimeMatch) return null;
    const mime = mimeMatch[1];
    const bstr = atob(arr[1]);
    let n = bstr.length;
    const u8arr = new Uint8Array(n);
    while(n--){
        u8arr[n] = bstr.charCodeAt(n);
    }
    return new Blob([u8arr], {type:mime});
}

async function savePhoto() {
    if (!capturedImage.value) return;

    isSaving.value = true;
    try {
        const blob = dataURLtoBlob(capturedImage.value);
        if (blob) {
            const file = new File([blob], `webcam_capture_${Date.now()}.jpg`, { type: 'image/jpeg' });
            await imageStore.uploadImages([file]);
            await imageStore.fetchImages();
            uiStore.addNotification('Photo saved to gallery!', 'success');
            uiStore.closeModal('cameraCapture');
        } else {
            throw new Error("Could not convert captured image to a file.");
        }
    } catch (err) {
        uiStore.addNotification('Failed to save photo.', 'error');
        console.error("Save photo error:", err);
    } finally {
        isSaving.value = false;
    }
}
</script>