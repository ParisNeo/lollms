
<!-- frontend/webui/src/components/admin/bindings/TTVBindingsSettings.vue -->
<script setup>
import { defineAsyncComponent } from 'vue';

const BindingSettingsPanel = defineAsyncComponent(
    () => import('./BindingSettingsPanel.vue')
);
</script>

<template>
    <BindingSettingsPanel binding-type="ttv" />
</template>
