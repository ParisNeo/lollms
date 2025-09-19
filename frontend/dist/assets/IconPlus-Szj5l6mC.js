const r=`<script setup>\r
defineProps({\r
  class: { type: String, default: 'w-6 h-6' }\r
});\r
<\/script>\r
<template>\r
  <svg xmlns="http://www.w3.org/2000/svg" :class="class" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">\r
    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />\r
  </svg>\r
</template>`;export{r as default};
