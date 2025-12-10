// [UPDATE] frontend/webui/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

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
    path: '/app/:appId',
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
  {
    path: '/image-studio/timelapse',
    name: 'Timelapse',
    component: () => import('../views/TimelapseView.vue')
  },
  {
    path: '/messages',
    name: 'Messages',
    component: () => import('../views/MessagesView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
