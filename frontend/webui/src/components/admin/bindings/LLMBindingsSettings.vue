
<!-- frontend/webui/src/components/admin/bindings/LLMBindingsSettings.vue -->
<script setup>
import { defineAsyncComponent } from 'vue';

const BindingSettingsPanel = defineAsyncComponent(
    () => import('./BindingSettingsPanel.vue')
);
</script>

<template>
    <BindingSettingsPanel binding-type="llm" />
</template>
