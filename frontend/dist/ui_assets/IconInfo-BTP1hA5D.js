const n=`<script setup>\r
defineProps({\r
  class: {\r
    type: String,\r
    default: 'w-6 h-6' // Optional: a default size if no class is provided\r
  }\r
});\r
<\/script>\r
\r
<template>\r
  <svg \r
    xmlns="http://www.w3.org/2000/svg" \r
    fill="none" \r
    viewBox="0 0 24 24" \r
    stroke-width="1.5" \r
    stroke="currentColor" \r
    :class="class"\r
  >\r
    <path stroke-linecap="round" stroke-linejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" />\r
  </svg>\r
</template>`;export{n as default};
