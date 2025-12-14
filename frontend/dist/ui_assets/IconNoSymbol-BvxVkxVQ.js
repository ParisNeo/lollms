const r=`<script setup>\r
defineProps({\r
  class: { type: String, default: 'w-6 h-6' }\r
});\r
<\/script>\r
<template>\r
  <svg xmlns="http://www.w3.org/2000/svg" :class="class" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">\r
    <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />\r
  </svg>\r
</template>`;export{r as default};
