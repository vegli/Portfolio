<script setup lang="ts">
import SiteNavbar from './components/SiteNavbar.vue'
</script>

<template>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <SiteNavbar />
  <main id="main-content" tabindex="-1">
    <RouterView />
  </main>
</template>
