<template>
  <div class="card">
    <div class="p-4">
      <div class="flex items-start space-x-4">
        <UserAvatar :icon="app.icon" :username="app.name" size-class="h-12 w-12" class="flex-shrink-0" />
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between">
            <h3 class="card-title truncate" :title="app.name">{{ app.name }}</h3>
            <div class="flex items-center gap-2">
              <span v-if="app.status === 'running'" class="status-badge status-running" title="App is running"></span>
              <span v-if="app.status === 'starting'" class="status-badge status-starting"
                title="App is starting..."></span>
              <span v-if="app.status === 'stopped' && isInstalled" class="status-badge status-stopped"
                title="App is stopped"></span>
              <span v-if="isBroken" class="status-badge status-broken" title="Installation is broken"></span>
            </div>
          </div>
          <p class="text-xs text-gray-500 dark:text-gray-400">by {{ app.author }}</p>
          <p class="text-sm text-gray-600 dark:text-gray-300 mt-2 h-10 overflow-hidden text-ellipsis">
            {{ app.description }}
          </p>
        </div>
      </div>
    </div>

    <div v-if="appTask" class="px-4 pb-4">
      <div class="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700">
        <div class="bg-blue-600 h-2.5 rounded-full" :style="{ width: `${appTask.progress}%` }"></div>
      </div>
      <p class="text-xs text-center mt-1 text-blue-600 dark:text-blue-400 font-semibold capitalize">{{ appTask.type
        }}... ({{ appTask.progress }}%)</p>
    </div>

    <div class="card-footer" v-else>
      <div class="flex items-center justify-between w-full">
        <div class="flex items-center space-x-2">
          <button @click="handleDetails" class="btn-secondary-sm">Details</button>
          <button v-if="isInstalled && app.settings_found" @click="handleConfigure" class="btn-secondary-sm">Configure</button>
        </div>

        <div class="flex items-center space-x-2">
          <template v-if="isInstalled">
            <button v-if="app.status === 'running' || app.status === 'starting'" @click="handleStop"
              :disabled="app.status === 'starting'" class="btn-danger-sm">Stop</button>
            <button v-else-if="!isBroken" @click="handleStart" class="btn-primary-sm">Start</button>
          </template>
        </div>
      </div>
    </div>

    <div class="card-footer" v-if="!appTask">
      <div class-="w-full">
        <div class="flex w-full items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <p v-if="isInstalled">Version: <span class="font-semibold">{{ installedVersion }}</span></p>
          <p v-else class="text-gray-400 dark:text-gray-500">Not Installed</p>

          <p v-if="isUpdateAvailable" class="text-green-600 dark:text-green-400 font-semibold">
            Update Available: {{ latestVersion }}
          </p>
        </div>

        <div class="mt-2 flex items-center w-full" :class="isInstalled ? 'justify-between' : 'justify-end'">
          <button v-if="isInstalled" @click="handleUninstall" class="btn-danger-sm">Uninstall</button>

          <button v-if="isBroken" @click="handleFix" class="btn-warning-sm">Fix</button>
          <button v-else-if="isUpdateAvailable" @click="handleUpdate" class="btn-success-sm">Update</button>
          <button v-else-if="!isInstalled" @click="handleInstall" class="btn-primary-sm">Install</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  @apply bg-white dark:bg-gray-800 rounded-lg shadow-md flex flex-col h-full border dark:border-gray-700 transition-all hover:shadow-lg;
}

.card-title {
  @apply font-semibold text-gray-800 dark:text-white;
}

.card-footer {
  @apply mt-auto p-4 bg-gray-50 dark:bg-gray-800/50 border-t dark:border-gray-700;
}

.btn-primary-sm {
  @apply bg-blue-500 text-white px-3 py-1 rounded-md text-sm font-semibold hover:bg-blue-600 disabled:opacity-50;
}

.btn-secondary-sm {
  @apply bg-gray-200 text-gray-700 px-3 py-1 rounded-md text-sm font-semibold hover:bg-gray-300 disabled:opacity-50 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600;
}

.btn-danger-sm {
  @apply bg-red-500 text-white px-3 py-1 rounded-md text-sm font-semibold hover:bg-red-600 disabled:opacity-50;
}

.btn-success-sm {
  @apply bg-green-500 text-white px-3 py-1 rounded-md text-sm font-semibold hover:bg-green-600 disabled:opacity-50;
}

.btn-warning-sm {
  @apply bg-yellow-500 text-white px-3 py-1 rounded-md text-sm font-semibold hover:bg-yellow-600 disabled:opacity-50;
}

.status-badge {
  @apply w-3 h-3 rounded-full;
}

.status-running {
  @apply bg-green-500;
}

.status-starting {
  @apply bg-yellow-500 animate-pulse;
}

.status-stopped {
  @apply bg-gray-400;
}
.status-broken {
  @apply bg-red-500;
}
</style>

<script setup>
import { computed } from 'vue';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import UserAvatar from './UserAvatar.vue';

const props = defineProps({
  app: {
    type: Object,
    required: true
  },
  task: {
    type: Object,
    default: null
  }
});

const adminStore = useAdminStore();
const uiStore = useUiStore();

const isInstalled = computed(() => props.app.is_installed);

const installedVersion = computed(() => {
  if (!isInstalled.value) return null;
  return props.app.version;
});

const latestVersion = computed(() => {
  if (!props.app.versions || props.app.versions.length === 0) return installedVersion.value;
  // Assuming versions are sorted latest first if it's an array
  return props.app.versions[0];
});

const isUpdateAvailable = computed(() => {
  if (!isInstalled.value || !latestVersion.value || !installedVersion.value) return false;
  // Simple version comparison, can be improved with semver library
  return latestVersion.value !== installedVersion.value;
});

const isBroken = computed(() => isInstalled.value && !props.app.settings_found);

const appTask = computed(() => {
  if (!props.task) return null;
  const taskName = props.task.name.toLowerCase();
  if (props.app.folder_name && taskName.includes(props.app.folder_name)) {
    if (taskName.includes('installing')) return { type: 'install', progress: props.task.progress };
    if (taskName.includes('updating')) return { type: 'update', progress: props.task.progress };
    if (taskName.includes('uninstalling')) return { type: 'uninstall', progress: props.task.progress };
    if (taskName.includes('starting')) return { type: 'start', progress: props.task.progress };
    if (taskName.includes('stopping')) return { type: 'stop', progress: props.task.progress };
    if (taskName.includes('fixing')) return { type: 'fix', progress: props.task.progress };
  }
  return null;
});


const isBusy = computed(() => !!appTask.value || isBroken.value || props.app.status === 'running' || props.app.status === 'starting');


function handleInstall() {
  uiStore.openModal('appInstall', { app: props.app, version: latestVersion.value });
}

function handleUpdate() {
  adminStore.updateApp(props.app.id);
}

function handleUninstall() {
  adminStore.uninstallApp(props.app.id);
}

function handleDetails() {
  uiStore.openModal('appDetails', { app: props.app });
}

function handleConfigure() {
  uiStore.openModal('appConfig', { app: props.app });
}

function handleStart() {
  adminStore.startApp(props.app.id);
}

function handleStop() {
  adminStore.stopApp(props.app.id);
}

async function handleFix() {
  await adminStore.fixBrokenInstallation(props.app);
}

</script>