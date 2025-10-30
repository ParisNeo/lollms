<template>
    <GenericModal modal-name="cameraCapture" title="Take a Photo" max-width-class="max-w-2xl">
        <template #body>
            <div class="relative aspect-video bg-black rounded-lg overflow-hidden">
                <!-- Video Element (always in DOM but visibility is controlled) -->
                <video :ref="setVideoRef" autoplay playsinline class="w-full h-full object-contain transition-opacity" :class="{'opacity-100': cameraState === 'streaming', 'opacity-0': cameraState !== 'streaming'}"></video>
                
                <!-- Captured Image Preview -->
                <img v-if="cameraState === 'captured'" :src="capturedImage" class="absolute inset-0 w-full h-full object-contain z-10" alt="Captured Photo Preview">
                
                <!-- Overlay for Status Messages -->
                <div v-if="cameraState !== 'streaming'" class="absolute inset-0 flex items-center justify-center text-white bg-black/70 p-4 z-20">
                    <div v-if="cameraState === 'requesting'" class="text-center">
                        <IconAnimateSpin class="w-8 h-8 mx-auto mb-2 animate-spin" />
                        <p>Waiting for camera permission...</p>
                        <p class="text-xs text-gray-400 mt-1">Please check for a browser pop-up.</p>
                    </div>
                    <p v-if="cameraState === 'error'" class="text-center">{{ error }}</p>
                    <p v-if="cameraState === 'idle'">Initializing...</p>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('cameraCapture')" class="btn btn-secondary">Cancel</button>
            <div class="flex-grow"></div>
            <button v-if="cameraState === 'streaming'" @click="capturePhoto" class="btn btn-primary">Take Photo</button>
            <button v-if="cameraState === 'captured'" @click="retakePhoto" class="btn btn-secondary">Retake</button>
            <button v-if="cameraState === 'captured'" @click="savePhoto" class="btn btn-primary" :disabled="isSaving">
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
const cameraState = ref('idle'); // 'idle', 'requesting', 'streaming', 'captured', 'error'
const error = ref(null);
const capturedImage = ref(null);
const isSaving = ref(false);

// Template ref function to ensure the element is available
const setVideoRef = (el) => {
    videoRef.value = el;
};

function resetState() {
    if (videoStream.value) {
        videoStream.value.getTracks().forEach(track => track.stop());
    }
    if (videoRef.value) {
        videoRef.value.srcObject = null;
        videoRef.value.onplaying = null;
    }
    videoStream.value = null;
    cameraState.value = 'idle';
    capturedImage.value = null;
    error.value = null;
    isSaving.value = false;
}

watch(() => uiStore.isModalOpen('cameraCapture'), (isOpen) => {
    if (isOpen) {
        // The watcher on videoRef will handle calling startCamera
        // This is a fallback in case the ref is already set from a previous open
        if (videoRef.value) {
            startCamera();
        }
    } else {
        resetState();
    }
});

// Watch the videoRef itself. When Vue mounts the element and assigns it,
// this watcher will trigger, ensuring we have the element before we use it.
watch(videoRef, (newEl) => {
    if (newEl && uiStore.isModalOpen('cameraCapture')) {
        startCamera();
    }
});


onUnmounted(resetState);

async function startCamera() {
    // Prevent starting multiple times if watchers fire rapidly
    if (cameraState.value === 'requesting' || cameraState.value === 'streaming') {
        return;
    }

    resetState();
    cameraState.value = 'requesting';

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        error.value = 'Camera access is not supported by your browser.';
        cameraState.value = 'error';
        return;
    }
    
    // This check is now reliable because it runs after the element is mounted
    if (!videoRef.value) {
        error.value = 'Camera component did not load correctly. Please try again.';
        cameraState.value = 'error';
        return;
    }

    try {
        videoStream.value = await navigator.mediaDevices.getUserMedia({ video: true });
        
        if (videoRef.value) {
            videoRef.value.srcObject = videoStream.value;
            videoRef.value.onplaying = () => {
                cameraState.value = 'streaming';
            };
        }

    } catch (err) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            error.value = 'Camera access was denied. Please allow camera permissions in your browser settings.';
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
            error.value = 'No camera found. Please ensure a camera is connected and enabled.';
        } else {
            error.value = 'An error occurred while accessing the camera.';
        }
        cameraState.value = 'error';
        console.error("Camera access error:", err);
    }
}

function capturePhoto() {
    if (!videoRef.value || cameraState.value !== 'streaming') return;

    const canvas = document.createElement('canvas');
    canvas.width = videoRef.value.videoWidth;
    canvas.height = videoRef.value.videoHeight;
    const context = canvas.getContext('2d');
    context.drawImage(videoRef.value, 0, 0, canvas.width, canvas.height);
    
    capturedImage.value = canvas.toDataURL('image/jpeg');
    cameraState.value = 'captured';
    
    // Stop the stream after capture
    if (videoStream.value) {
        videoStream.value.getTracks().forEach(track => track.stop());
    }
}

function retakePhoto() {
    startCamera();
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
    if (cameraState.value !== 'captured' || !capturedImage.value) return;

    isSaving.value = true;
    try {
        const blob = dataURLtoBlob(capturedImage.value);
        if (blob) {
            const file = new File([blob], `webcam_capture_${Date.now()}.jpg`, { type: 'image/jpeg' });
            await imageStore.uploadImages([file]);
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