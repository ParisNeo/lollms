import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
  },
  // Future routes like /login or /about could be added here
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;