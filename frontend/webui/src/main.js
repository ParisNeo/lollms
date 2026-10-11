import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import './assets/css/main.css';

// Explicitly import all vibes to ensure they are bundled and not tree-shaken
import '@/assets/css/vibes/glass.css';
import '@/assets/css/vibes/skeuo.css';
import '@/assets/css/vibes/paper.css';
import '@/assets/css/vibes/flat.css';
import '@/assets/css/vibes/indigo.css';
import '@/assets/css/vibes/midnight.css';
import '@/assets/css/vibes/cyberpunk.css';
import '@/assets/css/vibes/forest.css';
import '@/assets/css/vibes/ocean.css';
import '@/assets/css/vibes/sunset.css';
import '@/assets/css/vibes/lavender.css';
import '@/assets/css/vibes/monochrome.css';

// NEW: Import Chart.js components
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  ArcElement
} from 'chart.js';

// NEW: Register Chart.js components
ChartJS.register(
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement
);


const app = createApp(App);

app.use(createPinia());
app.use(router);

app.mount('#app');