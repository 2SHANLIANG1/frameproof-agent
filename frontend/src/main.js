import { createApp } from 'vue'
if (import.meta.env.MODE === 'showcase') {
  import('./ShowcaseApp.vue').then(({ default: App }) => createApp(App).mount('#app'))
} else {
  Promise.all([import('./App.vue'), import('./style.css')])
    .then(([{ default: App }]) => createApp(App).mount('#app'))
}
