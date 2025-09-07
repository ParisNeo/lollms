<script setup>
import { computed, ref, onMounted } from 'vue';

const props = defineProps({
  // The URL or Base64 data URI of the user's icon
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
  // Alternative text for the image
  alt: {
    type: String,
    default: '',
  },
  // Whether the avatar should be clickable
  clickable: {
    type: Boolean,
    default: false,
  },
  // Variant for different avatar styles
  variant: {
    type: String,
    default: 'circular',
    validator: (value) => ['circular', 'rounded', 'square'].includes(value),
  },
  // Custom background colors for fallback
  customColors: {
    type: Array,
    default: () => [],
  },
  // Loading state
  loading: {
    type: Boolean,
    default: false,
  },
  // Whether to show online indicator
  showStatus: {
    type: Boolean,
    default: false,
  },
  // Status type
  status: {
    type: String,
    default: 'offline',
    validator: (value) => ['online', 'offline', 'busy', 'away'].includes(value),
  },
  // Delay before showing fallback to prevent flash
  fallbackDelay: {
    type: Number,
    default: 0,
  },
});

const emit = defineEmits(['click', 'imageError', 'imageLoad']);

// Image loading states
const imageLoaded = ref(false);
const imageError = ref(false);
const showFallback = ref(!props.icon);
const fallbackTimeout = ref(null);

// Computed properties
const showImage = computed(() => 
  !!props.icon && imageLoaded.value && !imageError.value
);

const altText = computed(() => 
  props.alt || `Avatar for ${props.username}`
);

// Enhanced fallback with better initial handling
const fallbackInitial = computed(() => {
  if (!props.username) return '?';
  
  // Handle multiple words - take first letter of first two words
  const words = props.username.trim().split(/\s+/);
  if (words.length >= 2) {
    return (words[0].charAt(0) + words[1].charAt(0)).toUpperCase();
  }
  return props.username.charAt(0).toUpperCase();
});

// Enhanced color generation with better distribution
const fallbackBgColor = computed(() => {
  if (!props.username) return 'bg-gray-500';
  
  const colors = props.customColors.length > 0 
    ? props.customColors
    : [
        'bg-red-500', 'bg-orange-500', 'bg-amber-500', 'bg-yellow-500',
        'bg-lime-500', 'bg-green-500', 'bg-emerald-500', 'bg-teal-500',
        'bg-cyan-500', 'bg-sky-500', 'bg-blue-500', 'bg-indigo-500',
        'bg-violet-500', 'bg-purple-500', 'bg-fuchsia-500', 'bg-pink-500', 
        'bg-rose-500', 'bg-slate-600', 'bg-gray-600', 'bg-zinc-600'
      ];
  
  // Better hash function for more even distribution
  let hash = 0;
  for (let i = 0; i < props.username.length; i++) {
    const char = props.username.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  
  return colors[Math.abs(hash) % colors.length];
});

// Computed classes for different variants
const avatarClasses = computed(() => {
  const base = 'relative inline-flex items-center justify-center overflow-hidden transition-all duration-200';
  const variants = {
    circular: 'rounded-full',
    rounded: 'rounded-lg',
    square: 'rounded-none',
  };
  const interactive = props.clickable 
    ? 'cursor-pointer hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2' 
    : '';
  
  return [
    base,
    variants[props.variant],
    props.sizeClass,
    interactive,
    { [fallbackBgColor.value]: showFallback.value && !props.loading }
  ];
});

// Status indicator classes
const statusClasses = computed(() => {
  const statusColors = {
    online: 'bg-green-400',
    offline: 'bg-gray-400',
    busy: 'bg-red-400',
    away: 'bg-yellow-400',
  };
  return `absolute bottom-0 right-0 block h-2.5 w-2.5 rounded-full ring-2 ring-white ${statusColors[props.status]}`;
});

// Dynamic font size based on avatar size
const fontSize = computed(() => {
  const sizeMatch = props.sizeClass.match(/h-(\d+)/);
  if (sizeMatch) {
    const size = parseInt(sizeMatch[1]) * 4; // Convert to pixels (assuming 1rem = 16px)
    return `${Math.max(size / 40, 0.75)}rem`;
  }
  return '1rem';
});

// Image event handlers
const handleImageLoad = () => {
  imageLoaded.value = true;
  imageError.value = false;
  showFallback.value = false;
  emit('imageLoad');
};

const handleImageError = () => {
  imageError.value = true;
  imageLoaded.value = false;
  
  if (props.fallbackDelay > 0) {
    fallbackTimeout.value = setTimeout(() => {
      showFallback.value = true;
    }, props.fallbackDelay);
  } else {
    showFallback.value = true;
  }
  
  emit('imageError');
};

const handleClick = (event) => {
  if (props.clickable) {
    emit('click', event);
  }
};

// Handle keyboard events for accessibility
const handleKeydown = (event) => {
  if (props.clickable && (event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault();
    emit('click', event);
  }
};

// Cleanup timeout on unmount
onMounted(() => {
  // Set initial fallback state based on icon presence
  if (!props.icon) {
    showFallback.value = true;
  }
});

// Cleanup function
const cleanup = () => {
  if (fallbackTimeout.value) {
    clearTimeout(fallbackTimeout.value);
  }
};

// Watch for icon changes
import { watch, onUnmounted } from 'vue';

watch(() => props.icon, (newIcon) => {
  if (newIcon) {
    imageLoaded.value = false;
    imageError.value = false;
    showFallback.value = false;
    cleanup();
  } else {
    showFallback.value = true;
  }
});

onUnmounted(cleanup);
</script>

<template>
  <div
    :class="avatarClasses"
    :aria-label="altText"
    :title="props.username"
    :tabindex="clickable ? 0 : -1"
    :role="clickable ? 'button' : 'img'"
    @click="handleClick"
    @keydown="handleKeydown"
  >
    <!-- Loading State -->
    <div
      v-if="loading"
      class="absolute inset-0 flex items-center justify-center bg-gray-200 animate-pulse"
      :class="variant === 'circular' ? 'rounded-full' : variant === 'rounded' ? 'rounded-lg' : ''"
    >
      <svg
        class="w-1/2 h-1/2 text-gray-400 animate-spin"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        />
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    </div>

    <!-- User Image -->
    <img
      v-else-if="icon && !loading"
      :src="icon"
      :alt="altText"
      class="object-cover w-full h-full transition-opacity duration-200"
      :class="{ 'opacity-0': !imageLoaded || imageError }"
      @load="handleImageLoad"
      @error="handleImageError"
      loading="lazy"
    />

    <!-- Fallback Content -->
    <div
      v-if="showFallback && !loading"
      class="flex items-center justify-center w-full h-full"
    >
      <span
        class="font-semibold text-white select-none"
        :style="{ fontSize }"
        :aria-hidden="true"
      >
        {{ fallbackInitial }}
      </span>
    </div>

    <!-- Status Indicator -->
    <span
      v-if="showStatus"
      :class="statusClasses"
      :aria-label="`Status: ${status}`"
    />

    <!-- Screen Reader Only Content -->
    <span class="sr-only">
      {{ altText }}
      <span v-if="showStatus">, {{ status }}</span>
    </span>
  </div>
</template>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Focus styles for better accessibility */
[role="button"]:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* Smooth transitions */
.transition-all {
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 150ms;
}
</style>
