<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { useSocialStore } from '../stores/social';
import UserAvatar from '../components/ui/UserAvatar.vue';
import PostCard from '../components/social/PostCard.vue';

const route = useRoute();
const authStore = useAuthStore();
const socialStore = useSocialStore();

const profileUser = ref(null);

const isLoading = computed(() => socialStore.isLoadingProfile);
const posts = computed(() => {
    if (!profileUser.value) return [];
    return socialStore.getPostsByUsername(profileUser.value.username);
});

// We need a way to check if the current user is following the profile user.
// This requires more state/logic, for now we'll placeholder it.
const isFollowing = ref(false); 

const isOwnProfile = computed(() => {
    return authStore.user?.username === profileUser.value?.username;
});

async function fetchProfileData(username) {
    // In a real app, you'd have an endpoint to fetch just the user profile.
    // We'll simulate this by fetching their posts and extracting the author info.
    if(username == "me"){
        username = useAuthStore.user.name
    }
    await socialStore.fetchUserPosts(username);
    const userPosts = socialStore.getPostsByUsername(username);
    if (userPosts.length > 0) {
        profileUser.value = userPosts[0].author;
    } else {
        // If the user has no posts, we need a fallback way to get their info.
        // This highlights the need for a dedicated `/api/users/{username}` endpoint.
        // For now, we'll show a basic profile.
        profileUser.value = { username: username, icon: null };
    }
    // TODO: Fetch follow status
}

function handleFollow() {
    if (!profileUser.value || isOwnProfile.value) return;
    socialStore.followUser(profileUser.value.id);
    isFollowing.value = true; // Optimistic update
}

function handleUnfollow() {
    if (!profileUser.value || isOwnProfile.value) return;
    socialStore.unfollowUser(profileUser.value.id);
    isFollowing.value = false; // Optimistic update
}

// Fetch data when the component mounts
onMounted(() => {
    fetchProfileData(route.params.username);
});

// Watch for changes in the route params (e.g., navigating from one profile to another)
watch(() => route.params.username, (newUsername) => {
    if (newUsername) {
        profileUser.value = null; // Reset profile before fetching new one
        fetchProfileData(newUsername);
    }
});

</script>

<template>
  <div class="flex-grow bg-gray-100 dark:bg-gray-900 overflow-y-auto">
    <div class="max-w-3xl mx-auto py-6 px-4">
        
        <router-link to="/" class="w-full text-left flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800">Back</router-link>
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
                        <!-- Placeholder for bio/stats -->
                        <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">User bio and other information will go here.</p>

                        <!-- Action Buttons -->
                        <div v-if="!isOwnProfile" class="mt-4">
                            <button v-if="!isFollowing" @click="handleFollow" class="btn btn-primary">Follow</button>
                            <button v-else @click="handleUnfollow" class="btn btn-secondary">Unfollow</button>
                             <button class="btn btn-secondary ml-2">Message</button>
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
                 <div v-if="isLoading" class="text-center py-10">
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