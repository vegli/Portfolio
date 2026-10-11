<script setup lang="ts">
import HeroSection from '../components/HeroSection.vue'

const products = [
  { name: 'Yettel App', category: 'Mobile Application / Backend Services', description: 'Customer-facing telecom application with over 1 million monthly active users, supported by backend APIs, integrations and business services.', url: 'https://www.yettel.rs/yettel/#/', icon: 'M8 2h8v20H8z M11 18h2' },
  { name: 'Yettel Nalog', category: 'Account Management / Identity', description: "Customer account and identity-related platform within Yettel’s digital ecosystem.", url: 'https://www.yettel.rs/nalog/app/dashboard', icon: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-2a8 8 0 0 1 16 0v2' },
  { name: 'Yettel TV Portal', category: 'TV / Digital Services', description: 'Digital TV service portal supporting customer subscription and service-management workflows.', url: 'https://www.yettel.rs/tv-portal/', icon: 'M2 4h20v14H2z M12 18v4 M8 22h8' },
  { name: 'USSD', category: 'Telecom / Interactive Services', description: 'Interactive telecom services within Yettel’s digital ecosystem.', url: null, icon: 'M5 3h14v18H5z M8 7h8 M8 11h1 M12 11h1 M16 11h1 M8 15h1 M12 15h1 M16 15h1' },
]
const skills = ['Backend services', 'REST & SOAP APIs', 'Relational databases', 'Redis caching', 'System integrations', 'Authentication flows', 'CI/CD pipelines', 'Production troubleshooting']
</script>

<template>
  <HeroSection />
  <div class="container portfolio-sections">
    <section id="about" class="portfolio-section" aria-labelledby="about-title" tabindex="-1">
      <h2 id="about-title">About Me</h2>
      <div class="section-copy">
        <p>I'm a Backend Engineer based in Belgrade, Serbia, with 3 years of professional experience at Yettel.</p>
        <p>My work focuses on building and maintaining backend services, integrating systems, implementing business logic and troubleshooting production applications. I've worked with REST and SOAP APIs, relational databases, Redis caching, authentication flows and CI/CD pipelines.</p>
        <p>I'm particularly interested in software architecture, understanding how systems work beneath the surface, and continuously improving my engineering skills.</p>
        <p>I also explore AI-assisted development workflows, using Claude Code and OpenAI Codex to support implementation, debugging and codebase analysis.</p>
      </div>
    </section>
    <section id="products" class="portfolio-section" aria-labelledby="products-title" tabindex="-1">
      <h2 id="products-title">Products I've Worked On</h2>
      <p class="section-intro">A selection of production applications and systems I've contributed to during my work at Yettel.</p>
      <div class="product-grid">
        <article v-for="product in products" :key="product.name" class="product-card">
          <svg class="product-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="product.icon" /></svg>
          <p class="product-category">{{ product.category }}</p>
          <h3>{{ product.name }}</h3>
          <p>{{ product.description }}</p>
          <a v-if="product.url" class="text-link" :href="product.url" target="_blank" rel="noopener noreferrer">Visit {{ product.name }} <span aria-hidden="true">↗</span><span class="sr-only"> (opens in a new tab)</span></a>
        </article>
      </div>
    </section>
    <section id="experience" class="portfolio-section" aria-labelledby="experience-title" tabindex="-1">
      <h2 id="experience-title">Professional Experience</h2>
      <div class="section-copy">
        <p class="eyebrow">Yettel · 3 years of professional experience</p>
        <h3>Backend Engineer</h3>
        <p>I develop and maintain production backend services supporting Yettel's customer-facing digital products. My work includes API and system integrations, business logic, authentication flows and troubleshooting production applications.</p>
      </div>
    </section>
    <section id="skills" class="portfolio-section" aria-labelledby="skills-title" tabindex="-1">
      <h2 id="skills-title">Technical Skills</h2>
      <ul class="skill-list"><li v-for="skill in skills" :key="skill">{{ skill }}</li></ul>
    </section>
    <section id="projects" class="portfolio-section" aria-labelledby="projects-title" tabindex="-1">
      <h2 id="projects-title">Personal Projects / Playground</h2>
      <div class="section-copy">
        <h3>Developer Portfolio &amp; Playground</h3>
        <p>This portfolio is a practical software engineering project built with Vue 3 and TypeScript. The Playground is being developed as a card-based technical interview game covering backend engineering, databases, networking, system design, security, DDD and performance.</p>
        <RouterLink class="text-link" to="/playground">Explore the Playground <span aria-hidden="true">↗</span></RouterLink>
      </div>
    </section>
    <section id="contact" class="portfolio-section" aria-labelledby="contact-title" tabindex="-1">
      <h2 id="contact-title">Contact Me</h2>
      <address class="section-copy contact-details">
        <p>Belgrade, Serbia</p>
        <a class="text-link" href="mailto:gligorijevicveljko3@gmail.com">gligorijevicveljko3@gmail.com</a>
      </address>
    </section>
  </div>
</template>
