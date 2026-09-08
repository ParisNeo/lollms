<script setup>
import DropDownSubmenu from '../DropDownMenu/DropdownSubmenu.vue';

defineOptions({ inheritAttrs: false });
</script>

<template>
  <DropDownSubmenu v-bind="$attrs">
    <slot />
  </DropDownSubmenu>
</template>
