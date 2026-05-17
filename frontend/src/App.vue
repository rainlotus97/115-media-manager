<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuth } from './composables/useAuth'
import LoginPage from './components/LoginPage.vue'
import MainLayout from './components/MainLayout.vue'
import ToastContainer from './components/ToastContainer.vue'

const { isLoggedIn, restoreSession } = useAuth()
const loading = ref(true)

onMounted(async () => {
  await restoreSession()
  loading.value = false
})
</script>

<template>
  <div v-if="loading" class="app-loading">
    <div class="spinner"></div>
  </div>
  <template v-else>
    <LoginPage v-if="!isLoggedIn" />
    <MainLayout v-else />
  </template>
  <ToastContainer />
</template>

<style scoped>
.app-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: var(--bg-primary);
}
</style>
