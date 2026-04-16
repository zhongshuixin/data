import { ref, watch } from 'vue'

const STORAGE_KEY = 'rosbridge_url'

export function useRosbridgeUrl(defaultUrl = 'ws://localhost:9090') {
  const url = ref(localStorage.getItem(STORAGE_KEY) ?? defaultUrl)

  watch(
    url,
    (v) => {
      localStorage.setItem(STORAGE_KEY, v)
    },
    { flush: 'post' }
  )

  return { url }
}

