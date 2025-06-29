<script setup>
import { computed } from 'vue';

const props = defineProps({
  // The Base64 data URI of the user's icon
  icon: {
    type: String,
    default: null,
  },
  // The username, used for the letter fallback and accessibility
  username: {
    type: String,
    required: true,
  },
  // Additional classes for sizing, etc. e.g., 'h-8 w-8' or 'h-10 w-10'
  sizeClass: {
    type: String,
    default: 'h-8 w-8',
  },
});

const showImage = computed(() => !!props.icon);

// Creates a fallback with the first letter of the username
const fallbackInitial = computed(() => {
  return props.username ? props.username.charAt(0).toUpperCase() : '?';
});

// Generates a consistent background color based on the username
const fallbackBgColor = computed(() => {
  if (!props.username) return 'bg-gray-500';
  const colors = [
    'bg-red-500', 'bg-orange-500', 'bg-amber-500', 'bg-yellow-500',
    'bg-lime-500', 'bg-green-500', 'bg-emerald-500', 'bg-teal-500',
    'bg-cyan-500', 'bg-sky-500', 'bg-blue-500', 'bg-indigo-500',
    'bg-violet-500', 'bg-purple-500', 'bg-fuchsia-500', 'bg-pink-500', 'bg-rose-500'
  ];
  const charCodeSum = props.username.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return colors[charCodeSum % colors.length];
});

// A generic user SVG icon for a complete fallback
const defaultUserIcon = `
  <svg xmlns="http://www.w3.org/2000/svg" class="h-full w-full" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
  </svg>
`;

</script>

<template>
  <div
    class="relative inline-flex items-center justify-center overflow-hidden rounded-full"
    :class="[sizeClass, { [fallbackBgColor]: !showImage }]"
    :aria-label="`Avatar for ${username}`"
    :title="username"
  >
    <!-- Display user's custom image if available -->
    <img
      v-if="showImage"
      :src="icon"
      alt="User Avatar"
      class="object-cover w-full h-full"
    />
    <!-- Display fallback initial if no image -->
    <span
      v-else
      class="font-medium text-white select-none"
      :style="{ fontSize: `calc(${parseInt(sizeClass.split(' ')[0].split('-')[1])}rem / 2.5)` }"
    >
      {{ fallbackInitial }}
    </span>
  </div>
</template>