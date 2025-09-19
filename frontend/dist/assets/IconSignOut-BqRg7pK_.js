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
    <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />\r
  </svg>\r
</template>`;export{r as default};
