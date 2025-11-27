<!-- [UPDATE] frontend/webui/src/views/SettingsView.vue -->
<script setup>
import { computed, defineAsyncComponent, markRaw } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import IconUserCircle from '../assets/icons/IconUserCircle.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconCpuChip from '../assets/icons/IconCpuChip.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconSpeakerWave from '../assets/icons/IconSpeakerWave.vue';
import IconMicrophone from '../assets/icons/IconMicrophone.vue';
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconKey from '../assets/icons/IconKey.vue';
import IconTool from '../assets/icons/IconTool.vue';
import IconSquares2x2 from '../assets/icons/IconSquares2x2.vue';
import IconMcp from '../assets/icons/IconMcp.vue';

const route = useRoute();
const router = useRouter();

// Define components for async loading
const AccountSettings = defineAsyncComponent(() => import('../components/settings/AccountSettings.vue'));
const GeneralSettings = defineAsyncComponent(() => import('../components/settings/GeneralSettings.vue'));
const LLMSettings = defineAsyncComponent(() => import('../components/settings/LLMSettings.vue'));
const RAGSettings = defineAsyncComponent(() => import('../components/settings/RAGSettings.vue'));
const TTISettings = defineAsyncComponent(() => import('../components/settings/TTISettings.vue'));
const TTSSettings = defineAsyncComponent(() => import('../components/settings/TTSSettings.vue'));
const STTSettings = defineAsyncComponent(() => import('../components/settings/STTSettings.vue'));
const ApiKeysSettings = defineAsyncComponent(() => import('../components/settings/ApiKeysSettings.vue'));
const PersonalitiesSettings = defineAsyncComponent(() => import('../components/settings/PersonalitiesSettings.vue'));
const PromptsSettings = defineAsyncComponent(() => import('../components/settings/PromptsSettings.vue'));
const McpsSettings = defineAsyncComponent(() => import('../components/settings/McpsSettings.vue'));
const AppsSettings = defineAsyncComponent(() => import('../components/settings/AppsSettings.vue'));

const sections = [
    { id: 'account', name: 'Account', icon: markRaw(IconUserCircle), component: AccountSettings },
    { id: 'general', name: 'General', icon: markRaw(IconCog), component: GeneralSettings },
    { type: 'divider' },
    { id: 'personalities', name: 'Personalities', icon: markRaw(IconUserCircle), component: PersonalitiesSettings },
    { id: 'prompts', name: 'Prompts', icon: markRaw(IconSparkles), component: PromptsSettings },
    { id: 'mcps', name: 'MCPs', icon: markRaw(IconMcp), component: McpsSettings },
    { id: 'apps', name: 'Apps', icon: markRaw(IconSquares2x2), component: AppsSettings },
    { type: 'divider' },
    { id: 'llm', name: 'LLM', icon: markRaw(IconCpuChip), component: LLMSettings },
    { id: 'rag', name: 'RAG', icon: markRaw(IconDatabase), component: RAGSettings },
    { id: 'tti', name: 'TTI', icon: markRaw(IconPhoto), component: TTISettings },
    { id: 'tts', name: 'TTS', icon: markRaw(IconSpeakerWave), component: TTSSettings },
    { id: 'stt', name: 'STT', icon: markRaw(IconMicrophone), component: STTSettings },
    { type: 'divider' },
    { id: 'api_keys', name: 'API Keys', icon: markRaw(IconKey), component: ApiKeysSettings },
];

const activeSectionId = computed({
    get: () => route.query.section || 'account',
    set: (sectionId) => {
        router.push({ query: { ...route.query, section: sectionId } });
    }
});

const activeComponent = computed(() => {
    return sections.find(s => s.id === activeSectionId.value)?.component || AccountSettings;
});
</script>

<template>
    <PageViewLayout title="Settings" :title-icon="IconCog">
        <template #sidebar>
            <template v-for="(section, index) in sections" :key="section.id || `divider-${index}`">
                <div v-if="section.type === 'divider'" class="my-2 border-t border-gray-200 dark:border-gray-700"></div>
                <a v-else
                   href="#"
                   @click.prevent="activeSectionId = section.id"
                   class="flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors"
                   :class="activeSectionId === section.id ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'"
                >
                    <component :is="section.icon" class="w-5 h-5" />
                    <span>{{ section.name }}</span>
                </a>
            </template>
        </template>
        <template #main>
            <div class="p-4 sm:p-6">
                 <Suspense>
                    <template #default>
                        <component :is="activeComponent" />
                    </template>
                    <template #fallback>
                        <div class="text-center py-10">
                            <p class="text-gray-500 dark:text-gray-400">Loading settings...</p>
                        </div>
                    </template>
                </Suspense>
            </div>
        </template>
    </PageViewLayout>
</template>
