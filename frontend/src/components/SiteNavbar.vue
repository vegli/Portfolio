<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isOpen = ref(false)
const toggle = ref<HTMLButtonElement | null>(null)
const desktop = matchMedia('(min-width: 48rem)')
const links = [
  { label: 'About', hash: '#about' },
  { label: 'Products', hash: '#products' },
  { label: 'Experience', hash: '#experience' },
  { label: 'Contact', hash: '#contact' },
]

function closeMenu() {
  isOpen.value = false
}

function onEscape(event: KeyboardEvent) {
  if (event.key === 'Escape' && isOpen.value) {
    closeMenu()
    toggle.value?.focus()
  }
}

function onFocusOut(event: FocusEvent) {
  if (!event.currentTarget || !(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node)) {
    closeMenu()
  }
}

watch(() => route.fullPath, closeMenu)
onMounted(() => desktop.addEventListener('change', closeMenu))
onUnmounted(() => desktop.removeEventListener('change', closeMenu))
</script>

<template>
  <header class="site-header" @keydown="onEscape" @focusout="onFocusOut">
    <nav class="container navbar" aria-label="Main navigation">
      <RouterLink class="brand" :class="{ 'brand-back': route.path !== '/' }" to="/" aria-label="Home — Veljko Gligorijević" @click="closeMenu">
        <span class="brand-dot" aria-hidden="true"></span>
      </RouterLink>
      <button
        ref="toggle"
        class="menu-toggle"
        type="button"
        :aria-expanded="isOpen"
        aria-controls="navigation-links"
        :aria-label="isOpen ? 'Close navigation menu' : 'Open navigation menu'"
        @click="isOpen = !isOpen"
      >
        <span class="menu-icon" :class="{ 'is-open': isOpen }" aria-hidden="true"><span></span><span></span></span>
      </button>
      <div id="navigation-links" class="nav-links" :class="{ 'is-open': isOpen }">
        <RouterLink
          v-for="link in links"
          :key="link.hash"
          class="nav-link"
          :to="{ path: '/', hash: link.hash }"
          :aria-current="route.path === '/' && route.hash === link.hash ? 'location' : undefined"
          @click="closeMenu"
        >{{ link.label }}</RouterLink>
        <RouterLink class="button button-primary nav-cta" to="/playground" @click="closeMenu">Playground <span aria-hidden="true">↗</span></RouterLink>
      </div>
    </nav>
  </header>
</template>
