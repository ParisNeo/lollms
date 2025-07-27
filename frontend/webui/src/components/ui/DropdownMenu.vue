<script setup>
import { ref, computed } from 'vue';
import { useFloating, offset, flip, shift } from '@floating-ui/vue';
import { uiIconMap, languageIconMap } from '../../assets/icons/icon-maps';
import ToolbarButton from './ToolbarButton.vue';

const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, required: true },
  collection: { type: String, default: 'ui' },
  buttonClass: { type: [String, Object, Array], default: '' }
});

const isOpen = ref(false);
const reference = ref(null);
const floating = ref(null);

const { floatingStyles } = useFloating(reference, floating, {
  placement: 'bottom-start',
  middleware: [offset(5), flip(), shift({ padding: 5 })],
});

const iconComponent = computed(() => {
  const map = props.collection === 'languages' ? languageIconMap : uiIconMap;
  return map[props.icon] || null;
});

function openMenu() {
  isOpen.value = true;
}

function closeMenu() {
  isOpen.value = false;
}

const vOnClickOutside = {
  mounted: (el, binding) => {
    el.clickOutsideEvent = event => {
      const triggerEl = reference.value;
      if (!(el === event.target || el.contains(event.target) || triggerEl?.contains(event.target))) {
        binding.value();
      }
    };
    document.addEventListener('mousedown', el.clickOutsideEvent);
  },
  unmounted: el => {
    document.removeEventListener('mousedown', el.clickOutsideEvent);
  },
};
</script>

<template>
  <div class="relative">
    <ToolbarButton
      ref="reference"
      :title="title"
      :icon="icon"
      :collection="collection"
      :button-class="buttonClass"
      @click="isOpen = !isOpen"
    />
    <Teleport to="body">
      <Transition
        enter-active-class="transition ease-out duration-100"
        enter-from-class="transform opacity-0 scale-95"
        enter-to-class="transform opacity-100 scale-100"
        leave-active-class="transition ease-in duration-75"
        leave-from-class="transform opacity-100 scale-100"
        leave-to-class="transform opacity-0 scale-95"
      >
        <div
          v-if="isOpen"
          ref="floating"
          v-on-click-outside="closeMenu"
          :style="floatingStyles"
          class="z-50 w-56 origin-top-left rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none py-1"
        >
          <slot></slot>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>