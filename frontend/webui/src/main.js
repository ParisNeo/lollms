import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import './assets/css/main.css'

// Create the root Vue app instance.
const app = createApp(App)

// Install Pinia for global state management.
app.use(createPinia())

// Install Vue Router for handling navigation.
app.use(router)


// Mount the application to the <div id="app"></div> in index.html.
app.mount('#app')