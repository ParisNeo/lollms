<script setup>
import { ref, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/UserAvatar.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';

const authStore = useAuthStore();
const socialStore = useSocialStore();

const content = ref('');
const visibility = ref('PUBLIC'); // Default visibility
const isSubmitting = ref(false);

const user = computed(() => authStore.user);

const isPostDisabled = computed(() => {
  return isSubmitting.value || content.value.trim() === '';
});

async function handleSubmit() {
  if (isPostDisabled.value) return;

  isSubmitting.value = true;
  try {
    await socialStore.createPost({
      content: content.value,
      visibility: visibility.value,
      // Media will be handled here in the future
    });
    // Reset form on success
    content.value = '';
    visibility.value = 'PUBLIC';
  } catch (error) {
    // Error notification is handled by the store
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">
    <div class="flex space-x-4">
      <div class="flex-shrink-0">
        <UserAvatar v-if="user" :icon="user.icon" :username="user.username" size-class="h-10 w-10" />
      </div>

      <div class="flex-1 min-w-0">
        <CodeMirrorEditor v-model="content" />
        
        <div class="mt-3 flex justify-between items-center">
          <!-- Action buttons (e.g., for images, links) can go here -->
          <div class="flex items-center space-x-2">
            <!-- Placeholder for future media buttons -->
          </div>

          <div class="flex items-center space-x-3">
            <!-- Visibility Dropdown -->
            <select v-model="visibility" class="input-field !py-1.5 !px-2 text-sm">
              <option value="PUBLIC">Public</option>
              <option value="FOLLOWERS">Followers Only</option>
              <option value="FRIENDS">Friends Only</option>
            </select>

            <!-- Post Button -->
            <button
              @click="handleSubmit"
              :disabled="isPostDisabled"
              class="btn btn-primary"
            >
              {{ isSubmitting ? 'Posting...' : 'Post' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>