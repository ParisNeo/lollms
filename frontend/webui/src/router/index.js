import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import ProfileView from '../views/ProfileView.vue';
import SettingsView from '../views/SettingsView.vue';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomeView,
    // meta: { requiresAuth: true }
  },
  {
    path: '/profile/:username',
    name: 'Profile',
    component: ProfileView,
    // meta: { requiresAuth: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: SettingsView,
    // meta: { requiresAuth: true }
  },
  // If you need an admin route, ensure the component exists.
  // For now, it's commented out as it's part of the settings view.
  // {
  //   path: '/admin',
  //   name: 'Admin',
  //   component: AdminPanel, 
  //   meta: { requiresAuth: true, requiresAdmin: true }
  // },
];

const router = createRouter({
  // --- CORRECTED LINE ---
  // Replace process.env.BASE_URL with import.meta.env.BASE_URL
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

// Your authentication guard logic would go here
// import { useAuthStore } from '../stores/auth';
// router.beforeEach((to, from, next) => { ... });

export default router;