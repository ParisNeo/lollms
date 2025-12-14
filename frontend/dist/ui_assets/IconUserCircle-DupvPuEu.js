const r=`<script setup>\r
defineProps({\r
  class: {\r
    type: String,\r
    default: 'w-6 h-6'\r
  }\r
});\r
<\/script>\r
<template>\r
<svg width="20px" height="20px" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">\r
  <circle cx="12" cy="9" r="3" stroke="currentColor" stroke-width="1.5"/>\r
  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/>\r
  <path d="M17.9691 20C17.81 17.1085 16.9247 15 11.9999 15C7.07521 15 6.18991 17.1085 6.03076 20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>\r
</svg>\r
</template>`;export{r as default};
