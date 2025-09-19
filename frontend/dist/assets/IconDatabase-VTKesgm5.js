const r=`<script setup>\r
defineProps({\r
  class: {\r
    type: String,\r
    default: 'w-6 h-6'\r
  }\r
});\r
<\/script>\r
<template>\r
  <svg xmlns="http://www.w3.org/2000/svg" :class="class" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>\r
</template>`;export{r as default};
