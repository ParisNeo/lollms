import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import './assets/css/main.css'
import clickOutside from './directives/clickOutside';

// Create the root Vue app instance.
const app = createApp(App)
app.directive('on-click-outside', clickOutside);

// Install Pinia for global state management.
app.use(createPinia())

// Install Vue Router for handling navigation.
app.use(router)

// --- FIX: Register the on-click-outside directive globally ---
app.directive('on-click-outside', {
  mounted(el, binding) {
    el.__vueClickOutside__ = event => {
      // Check if the click is outside the element and its children
      if (!(el === event.target || el.contains(event.target))) {
        // Call the provided method
        binding.value(event);
      }
    };
    document.body.addEventListener('click', el.__vueClickOutside__);
  },
  unmounted(el) {
    document.body.removeEventListener('click', el.__vueClickOutside__);
  },
});


// Mount the application to the <div id="app"></div> in index.html.
app.mount('#app')