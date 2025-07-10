import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import ProfileView from '../views/ProfileView.vue';
import SettingsView from '../views/SettingsView.vue';
import MessagesView from '../views/MessagesView.vue';
import ResetPasswordView from '../views/ResetPasswordView.vue';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomeView,
  },
  {
    path: '/profile/:username',
    name: 'Profile',
    component: ProfileView,
  },
  {
    path: '/settings',
    name: 'Settings',
    component: SettingsView,
    meta: { requiresAuth: true }
  },
  {
    path: '/messages',
    name: 'Messages',
    component: MessagesView,
    meta: { requiresAuth: true }
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: ResetPasswordView,
    meta: { requiresGuest: true }
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;