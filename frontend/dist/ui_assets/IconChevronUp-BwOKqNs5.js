const r=`<script setup>\r
defineProps({\r
  class: {\r
    type: String,\r
    default: 'w-6 h-6'\r
  }\r
});\r
<\/script>\r
<template>\r
  <svg \r
    xmlns="http://www.w3.org/2000/svg" \r
    :class="class" \r
    fill="none" \r
    viewBox="0 0 24 24" \r
    stroke-width="1.5" \r
    stroke="currentColor"\r
  >\r
    <path stroke-linecap="round" stroke-linejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />\r
  </svg>\r
</template>`;export{r as default};
