import { Chat } from '@/features/chat/presentation/Chat'
import { ApiStatus } from '@/features/health/presentation/ApiStatus'

import { Layout } from './Layout'

export function App() {
  return (
    <Layout actions={<ApiStatus />}>
      <Chat />
    </Layout>
  )
}
