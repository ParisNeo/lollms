import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LoginView from '../components/modals/LoginModal.vue' // Keep existing if used, or adjust
// Note: Since HomeView handles sub-views like Chat and Feed via state, we keep routes simple.
// However, we should check if explicit routes are needed for direct linking.

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomeView
  },
  {
    path: '/profile/:username',
    name: 'Profile',
    component: () => import('../views/ProfileView.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue')
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/AdminView.vue')
  },
  {
    path: '/help',
    name: 'Help',
    component: () => import('../views/HelpView.vue')
  },
  {
    path: '/datastores',
    name: 'DataStores',
    component: () => import('../views/DataStoresView.vue')
  },
  {
    path: '/friends',
    name: 'Friends',
    component: () => import('../views/FriendsView.vue')
  },
  {
      path: '/news',
      name: 'News',
      component: () => import('../views/NewsView.vue')
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('../views/ResetPasswordView.vue')
  },
  {
    path: '/app/:appId', // For SSO client apps
    name: 'SsoLogin',
    component: () => import('../views/SsoLoginView.vue')
  },
  {
    path: '/voices-studio',
    name: 'VoicesStudio',
    component: () => import('../views/VoicesStudioView.vue')
  },
  {
    path: '/image-studio',
    name: 'ImageStudio',
    component: () => import('../views/ImageStudioView.vue')
  },
  {
    path: '/image-studio/edit/:id',
    name: 'ImageEditor',
    component: () => import('../views/ImageEditorView.vue'),
    props: true
  },
  // Add direct route for messages if desired, though HomeView handles it too via state
  {
    path: '/messages',
    name: 'Messages',
    component: () => import('../views/MessagesView.vue') // Or redirect to Home with state
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
