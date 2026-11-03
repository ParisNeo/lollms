<script setup>
import { ref, onMounted } from 'vue';
import apiClient from '@/services/api';
import { useUiStore } from '@/stores/ui';
import GenericModal from '@/components/modals/GenericModal.vue';
import IconUserGroup from '@/assets/icons/IconUserGroup.vue';

const props = defineProps({
  handbagName: { type: String, required: true },
  owner: { type: String, default: null },
});
const emit = defineEmits(['close', 'shared']);

const uiStore = useUiStore();

const friends = ref([]);
const groups = ref([]);
const isLoadingTargets = ref(true);
const selectedFriendId = ref(null);
const selectedGroupId = ref(null);
const shareType = ref('friend'); // 'friend' | 'group'
const isSubmitting = ref(false);

// Friend/group id normalization: `/api/friends/list` and `/api/groups/` have
// drifted between LoLLMS builds (`id` vs `friendship_id` vs `user_id`). Accept
// any of them so the <select> actually binds a value the backend can use.
const friendId = (f) => f?.id ?? f?.friend_id ?? f?.user_id ?? f?.target_id ?? null;
const friendLabel = (f) => f?.username || f?.name || f?.display_name || '';
const groupId = (g) => g?.id ?? g?.group_id ?? null;
const groupLabel = (g) => g?.name || g?.title || '';

// The groups router is mounted inconsistently across LoLLMS builds: some
// versions expose `GET /api/groups/` (FastAPI `@router.get("/")`), others
// `GET /api/groups`, and `/api/groups/my` collides with the `{group_id}`
// int route (→ 422 Unprocessable Content). Probe the common variants and use
// the first array (or wrapped array) that comes back.
async function fetchGroups() {
  for (const url of ['/api/groups/', '/api/groups', '/api/groups/my']) {
    try {
      const res = await apiClient.get(url);
      const payload = res?.data;
      if (Array.isArray(payload)) return payload;
      for (const key of ['groups', 'items', 'data']) {
        if (Array.isArray(payload?.[key])) return payload[key];
      }
    } catch {
      // try the next candidate
    }
  }
  return [];
}

async function loadTargets() {
  isLoadingTargets.value = true;
  try {
    const [friendsRes, groupsData] = await Promise.all([
      apiClient.get('/api/friends/list').catch(() => ({ data: [] })),
      fetchGroups(),
    ]);
    const friendsPayload = friendsRes?.data;
    let friendsArray = [];
    if (Array.isArray(friendsPayload)) {
      friendsArray = friendsPayload;
    } else {
      for (const key of ['friends', 'items', 'data']) {
        if (Array.isArray(friendsPayload?.[key])) {
          friendsArray = friendsPayload[key];
          break;
        }
      }
    }
    friends.value = friendsArray;
    groups.value = groupsData;
  } finally {
    isLoadingTargets.value = false;
  }
}

async function submitShare() {
  if (shareType.value === 'friend' && !selectedFriendId.value) {
    uiStore.addNotification('Please select a friend.', 'warning');
    return;
  }
  if (shareType.value === 'group' && !selectedGroupId.value) {
    uiStore.addNotification('Please select a group.', 'warning');
    return;
  }
  isSubmitting.value = true;
  try {
    await apiClient.post('/api/personalities/share', {
      handbag_name: props.handbagName,
      shared_with_user_id: shareType.value === 'friend' ? selectedFriendId.value : null,
      group_id: shareType.value === 'group' ? selectedGroupId.value : null,
      permission: 'read',
    });
    uiStore.addNotification(`"${props.handbagName}" shared successfully.`, 'success');
    emit('shared');
    emit('close');
  } catch (e) {
    uiStore.addNotification(e?.response?.data?.detail || 'Failed to share personality.', 'error');
    // eslint-disable-next-line no-console
    console.error('[SharePersonalityModal] share failed', e);
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(loadTargets);
</script>

<template>
  <GenericModal :title="`Share Personality`" @close="emit('close')">
    <template #body>
      <div class="space-y-4">
        <div class="rounded bg-gray-50 dark:bg-gray-800 p-3">
          <p class="text-sm">
            Sharing <strong>{{ handbagName }}</strong>
            <span v-if="owner" class="text-gray-500"> (owned by {{ owner }})</span>
            — read-only access.
          </p>
        </div>

        <div class="flex gap-2">
          <button
            class="px-3 py-1.5 text-sm rounded"
            :class="shareType === 'friend' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700'"
            @click="shareType = 'friend'"
          >
            Friend
          </button>
          <button
            class="px-3 py-1.5 text-sm rounded"
            :class="shareType === 'group' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700'"
            @click="shareType = 'group'"
          >
            Group
          </button>
        </div>

        <p v-if="isLoadingTargets" class="text-sm text-gray-500">Loading targets…</p>

        <div v-else>
          <div v-if="shareType === 'friend'" class="space-y-2">
            <label class="block text-sm font-medium">Select friend</label>
            <select
              v-model="selectedFriendId"
              class="w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700"
            >
              <option :value="null" disabled>Choose a friend…</option>
              <option v-for="f in friends" :key="friendId(f)" :value="friendId(f)">
                {{ friendLabel(f) }}
              </option>
            </select>
            <p v-if="!friends.length" class="text-xs text-gray-400">No friends found.</p>
          </div>

          <div v-else class="space-y-2">
            <label class="block text-sm font-medium">Select group</label>
            <select
              v-model="selectedGroupId"
              class="w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700"
            >
              <option :value="null" disabled>Choose a group…</option>
              <option v-for="g in groups" :key="groupId(g)" :value="groupId(g)">
                {{ groupLabel(g) }}
              </option>
            </select>
            <p v-if="!groups.length" class="text-xs text-gray-400">No groups found.</p>
          </div>
        </div>

        <div class="flex items-center gap-2 pt-2">
          <IconUserGroup class="w-5 h-5 text-gray-500" />
          <p class="text-xs text-gray-500">
            Recipients can list and select this personality but cannot modify its files.
          </p>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-2 pt-2">
        <button
          class="px-4 py-2 text-sm rounded bg-gray-200 dark:bg-gray-700 hover:bg-gray-300"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          class="px-4 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          :disabled="isSubmitting || isLoadingTargets"
          @click="submitShare"
        >
          {{ isSubmitting ? 'Sharing…' : 'Share' }}
        </button>
      </div>
    </template>
  </GenericModal>
</template>