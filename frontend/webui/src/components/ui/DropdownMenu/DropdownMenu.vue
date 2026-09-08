<script setup>
import DropDownMenu from '../DropDownMenu/DropdownMenu.vue';

defineOptions({ inheritAttrs: false });
</script>

<template>
  <DropDownMenu v-bind="$attrs">
    <template #icon>
      <slot name="icon" />
    </template>
    <slot />
  </DropDownMenu>
</template>
