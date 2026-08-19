import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import { useAuthStore } from '../stores/auth';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomeView
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('../views/AboutView.vue')
  },
  {
    path: '/help',
    name: 'Help',
    component: () => import('../views/HelpView.vue')
  },
  {
    path: '/news',
    name: 'News',
    component: () => import('../views/NewsView.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/AdminView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/profile/:username',
    name: 'Profile',
    component: () => import('../views/ProfileView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/friends',
    name: 'Friends',
    component: () => import('../views/FriendsView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/messages',
    name: 'Messages',
    component: () => import('../views/MessagesView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/personality-studio',
    name: 'PersonalityStudio',
    component: () => import('../views/PersonalityStudioView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/datastores',
    name: 'DataStores',
    component: () => import('../views/DataStoresView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/notebooks',
    alias: ['/notebook-studio'],
    name: 'Notebooks',
    component: () => import('../views/NotebookStudioView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/flow-studio',
    name: 'FlowStudio',
    component: () => import('../views/FlowStudioView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/voices-studio',
    name: 'VoicesStudio',
    component: () => import('../views/VoicesStudioView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/image-studio',
    name: 'ImageStudio',
    component: () => import('../views/ImageStudioView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/image-studio/edit/:id?',
    name: 'ImageEditor',
    component: () => import('../views/ImageEditorView.vue'),
    props: true,
    meta: { requiresAuth: true }
  },
  {
    path: '/image-studio/timelapse',
    name: 'Timelapse',
    component: () => import('../views/TimelapseView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('../views/ResetPasswordView.vue')
  },
  {
    path: '/app/:appId',
    name: 'AppSsoLogin',
    component: () => import('../views/SsoLoginView.vue')
  },
  {
    path: '/sso-login',
    name: 'SsoLogin',
    component: () => import('../views/SsoLoginView.vue')
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
});

router.beforeEach(async (to, from) => {
  const authStore = useAuthStore();

  // Allow public routes
  if (!to.meta.requiresAuth) {
    return true;
  }

  // Check if authenticated
  if (!authStore.isAuthenticated) {
    return { name: 'Home' };
  }

  // Check admin privileges
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return { name: 'Home' };
  }

  return true;
});

export default router;