// frontend/webui/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import ProfileView from '../views/ProfileView.vue';
import SettingsView from '../views/SettingsView.vue';
import MessagesView from '../views/MessagesView.vue';
import HelpView from '../views/HelpView.vue';
import ResetPasswordView from '../views/ResetPasswordView.vue';
import AdminView from '../views/AdminView.vue';
import DataStoresView from '../views/DataStoresView.vue';
import FriendsView from '../views/FriendsView.vue';
import SsoLoginView from '../views/SsoLoginView.vue';
import WelcomeView from '../views/WelcomeView.vue';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomeView,
  },
  {
    path: '/welcome',
    name: 'Welcome',
    component: WelcomeView,
  },
  {
    path: '/profile/:username',
    name: 'Profile',
    component: ProfileView,
    props: true,
  },
  {
    path: '/settings',
    name: 'Settings',
    component: SettingsView,
  },
  {
    path: '/admin',
    name: 'Admin',
    component: AdminView,
  },
  {
    path: '/messages',
    name: 'Messages',
    component: MessagesView,
  },
  {
    path: '/friends',
    name: 'Friends',
    component: FriendsView,
  },
  {
    path: '/datastores',
    name: 'DataStores',
    component: DataStoresView,
  },
  {
    path: '/help',
    name: 'Help',
    component: HelpView,
    props: (route) => ({ topic: route.query.topic, section: route.query.section }),
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: ResetPasswordView,
  },
  {
    path: '/app/:clientId',
    name: 'SsoLogin',
    component: SsoLoginView,
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;