import { withInkSuspended } from '@vael/ink'

import { t } from '../../../i18n/runtime.js'
import { launchVaelCommand } from '../../../lib/externalCli.js'
import { runExternalSetup } from '../../setupHandoff.js'
import type { SlashCommand } from '../types.js'

export const setupCommands: SlashCommand[] = [
  {
    help: 'run full setup wizard (launches `vael setup`)',
    name: 'setup',
    run: (arg, ctx) =>
      void runExternalSetup({
        args: ['setup', ...arg.split(/\s+/).filter(Boolean)],
        ctx,
        done: t('slashCmd.setup.setup.done'),
        launcher: launchVaelCommand,
        suspend: withInkSuspended
      })
  }
]
