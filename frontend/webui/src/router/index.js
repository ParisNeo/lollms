import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import ProfileView from '../views/ProfileView.vue';
import SettingsView from '../views/SettingsView.vue';
import MessagesView from '../views/MessagesView.vue';
import HelpView from '../views/HelpView.vue'; // NEW IMPORT
import ResetPasswordView from '../views/ResetPasswordView.vue';
import AdminView from '../views/AdminView.vue';
import DataStoresView from '../views/DataStoresView.vue';
import FriendsView from '../views/FriendsView.vue';
import SsoLoginView from '../views/SsoLoginView.vue';

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
    path: '/admin',
    name: 'Admin',
    component: AdminView,
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/messages',
    name: 'Messages',
    component: MessagesView,
    meta: { requiresAuth: true }
  },
  {
    path: '/friends',
    name: 'Friends',
    component: FriendsView,
    meta: { requiresAuth: true }
  },
  {
    path: '/datastores',
    name: 'DataStores',
    component: DataStoresView,
    meta: { requiresAuth: true }
  },
  {
    path: '/help', // NEW ROUTE
    name: 'Help',
    component: HelpView,
    props: (route) => ({ topic: route.query.topic, section: route.query.section }), // Pass query params as props
    meta: { requiresAuth: true }
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: ResetPasswordView,
    meta: { requiresGuest: true }
  },
  {
    path: '/app/:clientId',
    name: 'SsoLogin',
    component: SsoLoginView,
    meta: { isSsoRoute: true }
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;