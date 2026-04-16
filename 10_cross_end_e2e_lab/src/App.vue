<script setup lang="ts">
import { ref } from 'vue'
import Ros2RealtimeDashboard from './components/Ros2RealtimeDashboard.vue'
import SortingArmControlPanel from './components/SortingArmControlPanel.vue'

type Page = 'dashboard' | 'control'
const page = ref<Page>('dashboard')
</script>

<template>
  <div class="app">
    <header class="top">
      <h1 class="title">跨端数据格式统一与联调测试：综合项目</h1>
      <div class="tabs">
        <button class="tab" type="button" :data-active="page === 'dashboard'" @click="page = 'dashboard'">实时监控</button>
        <button class="tab" type="button" :data-active="page === 'control'" @click="page = 'control'">指令下发</button>
      </div>
    </header>

    <main class="main">
      <Ros2RealtimeDashboard v-if="page === 'dashboard'" />
      <SortingArmControlPanel v-else />
    </main>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
}

.top {
  max-width: 1160px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.title {
  font-size: 16px;
  margin: 0;
  font-weight: 600;
  color: #111;
  line-height: 1.4;
  letter-spacing: 0;
}

.tabs {
  display: flex;
  gap: 10px;
}

.tab {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  background: #fff;
}

.tab[data-active='true'] {
  border-color: #2563eb;
  color: #1d4ed8;
}

.main {
  padding: 0 16px 24px;
}
</style>
