
<!-- frontend/webui/src/components/admin/bindings/TTSBindingsSettings.vue -->
<script setup>
import { defineAsyncComponent } from 'vue';

const BindingSettingsPanel = defineAsyncComponent(
    () => import('./BindingSettingsPanel.vue')
);
</script>

<template>
    <BindingSettingsPanel binding-type="tts" />
</template>
