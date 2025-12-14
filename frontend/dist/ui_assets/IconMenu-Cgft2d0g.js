const r=`<script setup>\r
defineProps({\r
  class: {\r
    type: String,\r
    default: 'w-6 h-6'\r
  }\r
});\r
<\/script>\r
<template>\r
    <svg xmlns="http://www.w3.org/2000/svg" :class="class" fill="none" viewBox="0 0 24 24" stroke="currentColor">\r
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />\r
    </svg>\r
</template>`;export{r as default};
