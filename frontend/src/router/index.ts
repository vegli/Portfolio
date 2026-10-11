import { nextTick } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import PlaygroundView from '../views/PlaygroundView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', component: HomeView },
    { path: '/playground', component: PlaygroundView },
  ],
  async scrollBehavior(to, from, savedPosition) {
    await nextTick()
    if (savedPosition) return savedPosition

    const target = document.getElementById(to.hash.slice(1))
    if (target) {
      target.focus({ preventScroll: true })
      return {
        el: target,
        top: parseFloat(getComputedStyle(target).scrollMarginTop),
        behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
      }
    }

    if (to.path !== from.path) {
      document.getElementById('main-content')?.focus({ preventScroll: true })
    }
    return { top: 0 }
  },
})

router.afterEach((to) => {
  document.title = to.path === '/playground'
    ? 'Playground — Veljko Gligorijević'
    : 'Veljko Gligorijević — Backend Engineer'
})

export default router
