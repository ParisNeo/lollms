<script setup>
import { ref, computed } from 'vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArrowUp from '../../assets/icons/IconArrowUp.vue';
import IconArrowDown from '../../assets/icons/IconArrowDown.vue';

const props = defineProps({
  modelValue: {
    type: [String, Array],
    default: '',
  },
});

const emit = defineEmits(['update:modelValue']);

const newItem = ref('');

const items = computed({
  get: () => {
    const value = props.modelValue;
    if (Array.isArray(value)) {
      return value.map(item => String(item).trim()).filter(item => item);
    }
    if (typeof value === 'string') {
      return (value || '').split(',').map(item => item.trim()).filter(item => item);
    }
    return [];
  },
  set: (newItems) => {
    emit('update:modelValue', newItems.join(', '));
  },
});

function addItem() {
  if (newItem.value.trim() && !items.value.includes(newItem.value.trim())) {
    items.value = [...items.value, newItem.value.trim()];
    newItem.value = '';
  }
}

function removeItem(index) {
  const newItems = [...items.value];
  newItems.splice(index, 1);
  items.value = newItems;
}

function moveItem(index, direction) {
  const newItems = [...items.value];
  const newIndex = index + direction;
  if (newIndex >= 0 && newIndex < newItems.length) {
    [newItems[index], newItems[newIndex]] = [newItems[newIndex], newItems[index]];
    items.value = newItems;
  }
}
</script>

<template>
  <div class="space-y-2">
    <div v-for="(item, index) in items" :key="index" class="flex items-center gap-2">
      <input type="text" :value="item" @input="event => { const newItems = [...items]; newItems[index] = event.target.value; items = newItems; }" class="input-field flex-grow" />
      <button @click="moveItem(index, -1)" :disabled="index === 0" class="btn-icon" type="button" title="Move Up"><IconArrowUp class="w-4 h-4" /></button>
      <button @click="moveItem(index, 1)" :disabled="index === items.length - 1" class="btn-icon" type="button" title="Move Down"><IconArrowDown class="w-4 h-4" /></button>
      <button @click="removeItem(index)" class="btn-icon-danger" type="button" title="Remove"><IconTrash class="w-4 h-4" /></button>
    </div>
    <div class="flex items-center gap-2">
      <input type="text" v-model="newItem" @keyup.enter.prevent="addItem" class="input-field flex-grow" placeholder="Add new origin" />
      <button @click="addItem" class="btn btn-secondary" type="button"><IconPlus class="w-4 h-4 mr-1" /> Add</button>
    </div>
  </div>
</template>