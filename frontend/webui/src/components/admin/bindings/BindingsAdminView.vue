
<!-- frontend/webui/src/components/admin/bindings/BindingsAdminView.vue -->
<script setup>
import { computed, defineAsyncComponent, ref, watch } from 'vue';
import { BINDING_TYPES } from './bindingConfigs';

const BindingSettingsPanel = defineAsyncComponent(
    () => import('./BindingSettingsPanel.vue')
);

// The modality is chosen exclusively from the AdminView sidebar ("Bindings &
// Engines" links, which route to ?section=<modality>_bindings). This host MUST
// NOT render its own modality selector — doing so duplicates the sidebar's
// navigation (LLM / TTI / TTS / STT / TTV / TTM / RAG) into a second in-panel
// tab strip, which is redundant and confusing.
const props = defineProps({
    initialModality: { type: String, default: 'llm' },
});

// Normalize the incoming prop to a known modality; unknown values fall back.
const activeModality = ref(
    BINDING_TYPES[props.initialModality] ? props.initialModality : 'llm'
);

// Follow sidebar switches so the panel remounts (via :key) for the new slice.
watch(
    () => props.initialModality,
    (newModality) => {
        activeModality.value = BINDING_TYPES[newModality] ? newModality : 'llm';
    }
);
</script>

<template>
    <!-- Single panel for the sidebar-selected modality. The :key forces a
         clean remount whenever the admin switches modality in the sidebar,
         guaranteeing the correct store slice is reloaded with no stale state. -->
    <BindingSettingsPanel :key="activeModality" :binding-type="activeModality" />
</template>

<style scoped>
@reference "tailwindcss";
</style>
