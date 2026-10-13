import { Text } from '@vael/ink'

import { useT } from '../i18n/useT.js'
import { composerKeyHints } from '../lib/composerFrame.js'
import type { Theme } from '../theme.js'

/** The keys worth knowing, in one dim row under the framed input. */
export function KeyHints({ busy, t }: { busy: boolean; t: Theme }) {
  const T = useT()
  const hints = composerKeyHints(T.composer.keyHints, busy)

  return (
    <Text color={t.color.muted} wrap="truncate-end">
      {hints.map(([key, what], i) => (
        <Text key={key}>
          {i > 0 ? '   ' : ''}
          <Text bold color={t.color.primary}>
            {key}
          </Text>{' '}
          {what}
        </Text>
      ))}
    </Text>
  )
}
