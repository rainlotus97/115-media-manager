<script setup lang="ts">
import MainLayout from './components/MainLayout.vue'
import ToastContainer from './components/ToastContainer.vue'
import SessionExpiredModal from './components/SessionExpiredModal.vue'
import ProgressOverlay from './components/ProgressOverlay.vue'
import { useSessionEvents } from './composables/useSessionEvents'

const session = useSessionEvents()
</script>

<template>
  <MainLayout />
  <ToastContainer />
  <ProgressOverlay />
  <SessionExpiredModal v-if="session.expired.value" @close="session.dismiss()" />
</template>
