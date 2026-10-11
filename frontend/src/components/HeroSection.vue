<script setup lang="ts">
const cvUrl = `${import.meta.env.BASE_URL}Veljko_Gligorijevic_CV.pdf`
</script>

<template>
  <section class="hero container" aria-labelledby="hero-title">
    <p class="eyebrow">Backend Engineer · Belgrade, Serbia</p>
    <h1 id="hero-title">Veljko <span>Gligorijević</span></h1>
    <p class="hero-description">Backend Engineer with 3 years of professional experience developing and maintaining production systems at Yettel, contributing to customer-facing digital products with over 1 million monthly active users.</p>
    <div class="hero-actions">
      <RouterLink class="button button-primary" to="/#products">Explore my work <span aria-hidden="true">↓</span></RouterLink>
      <RouterLink class="button button-secondary" to="/#experience">View experience</RouterLink>
      <a class="button button-secondary" :href="cvUrl" target="_blank" rel="noopener noreferrer">View CV <span aria-hidden="true">↗</span><span class="sr-only"> (opens in a new tab)</span></a>
    </div>
  </section>
</template>
