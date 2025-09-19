<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { useSocialStore } from '../stores/social';
import UserAvatar from '../components/ui/Cards/UserAvatar.vue';
import PostCard from '../components/social/PostCard.vue';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const socialStore = useSocialStore();

const profileData = computed(() => {
    const username = route.params.username === 'me' ? authStore.user?.username : route.params.username;
    return socialStore.profiles[username] || null;
});

const profileUser = computed(() => profileData.value?.user || null);
const relationship = computed(() => profileData.value?.relationship || {});

const isLoading = computed(() => socialStore.isLoadingProfile);
const posts = computed(() => {
    if (!profileUser.value) return [];
    return socialStore.getPostsByUsername(profileUser.value.username);
});

const isOwnProfile = computed(() => {
    return authStore.user?.username === profileUser.value?.username;
});

async function fetchProfileData(username) {
    if (!username) return;
    const finalUsername = username === 'me' ? authStore.user?.username : username;
    if (!finalUsername) {
        router.push('/'); 
        return;
    }
    await socialStore.fetchUserProfile(finalUsername);
    await socialStore.fetchUserPosts(finalUsername);
}

// --- ACTION HANDLERS ---
function handleFollow() {
    if (!profileUser.value) return;
    socialStore.followUser(profileUser.value.id);
}

function handleUnfollow() {
    if (!profileUser.value) return;
    socialStore.unfollowUser(profileUser.value.id);
}

function handleSendFriendRequest() {
    if (!profileUser.value) return;
    socialStore.sendFriendRequest(profileUser.value.username);
}

function handleRemoveFriend() {
    if (!profileUser.value) return;
    socialStore.removeFriend(profileUser.value.id);
}

async function handleOpenMessage() {
    if (!profileUser.value) return;
    // Navigate home first, then open the conversation
    await router.push('/');
    socialStore.openConversation(profileUser.value);
}

// --- LIFECYCLE HOOKS ---
onMounted(() => {
    fetchProfileData(route.params.username);
});

watch(() => route.params.username, (newUsername) => {
    if (newUsername) {
        fetchProfileData(newUsername);
    }
});
</script>

<template>
  <div class="flex-grow bg-gray-100 dark:bg-gray-900 overflow-y-auto">
    <div class="max-w-3xl mx-auto py-6 px-4">
        
        <router-link to="/" class="inline-flex items-center space-x-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>
            <span>Back to Feed</span>
        </router-link>

        <!-- Loading State -->
        <div v-if="isLoading && !profileUser" class="text-center py-20">
            <p class="text-gray-500">Loading profile...</p>
        </div>

        <!-- Profile Loaded State -->
        <div v-else-if="profileUser">
            <!-- Profile Header -->
            <header class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6">
                <div class="flex flex-col sm:flex-row items-center sm:items-start space-y-4 sm:space-y-0 sm:space-x-6">
                    <UserAvatar :icon="profileUser.icon" :username="profileUser.username" size-class="h-24 w-24 text-4xl" />
                    <div class="flex-grow text-center sm:text-left">
                        <h1 class="text-3xl font-bold text-gray-900 dark:text-gray-100">{{ profileUser.username }}</h1>
                        <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ profileUser.bio || 'This user has not set a bio yet.' }}</p>

                        <!-- Action Buttons -->
                        <div v-if="!isOwnProfile" class="mt-4 flex items-center space-x-2 justify-center sm:justify-start">
                            <!-- Friendship Buttons -->
                            <button v-if="!relationship.friendship_status" @click="handleSendFriendRequest" class="btn btn-secondary">Add Friend</button>
                            <button v-else-if="relationship.friendship_status === 'PENDING'" class="btn btn-disabled" disabled>Request Sent</button>
                            <button v-else-if="relationship.friendship_status === 'ACCEPTED'" @click="handleRemoveFriend" class="btn btn-success-outline">Friends</button>

                            <!-- Follow Buttons -->
                            <button v-if="!relationship.is_following" @click="handleFollow" class="btn btn-primary">Follow</button>
                            <button v-else @click="handleUnfollow" class="btn btn-primary-outline">Following</button>
                            
                            <!-- Message Button -->
                            <button @click="handleOpenMessage" class="btn btn-secondary">Message</button>
                        </div>
                         <div v-else class="mt-4">
                             <router-link to="/settings" class="btn btn-secondary">Edit Profile</router-link>
                         </div>
                    </div>
                </div>
            </header>

            <!-- User's Posts -->
            <div>
                <h2 class="text-xl font-semibold text-gray-800 dark:text-gray-200 mb-4">Posts</h2>
                 <div v-if="isLoading && posts.length === 0" class="text-center py-10">
                    <p class="text-gray-500">Loading posts...</p>
                </div>
                <div v-else-if="posts.length > 0" class="space-y-4">
                    <PostCard
                        v-for="post in posts"
                        :key="post.id"
                        :post="post"
                    />
                </div>
                <div v-else class="text-center py-10 bg-white dark:bg-gray-800 rounded-lg shadow-md">
                    <p class="text-gray-500">{{ profileUser.username }} hasn't posted anything yet.</p>
                </div>
            </div>
        </div>
        
        <!-- Not Found State -->
        <div v-else class="text-center py-20">
             <h2 class="text-2xl font-bold text-red-500">User Not Found</h2>
             <p class="mt-2 text-gray-500">The profile for "{{ route.params.username }}" could not be found.</p>
        </div>
    </div>
  </div>
</template>