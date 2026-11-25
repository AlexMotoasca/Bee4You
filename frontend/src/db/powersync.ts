import { PowerSyncDatabase } from '@powersync/react-native';

import { AppSchema } from './schema';

/** The one local database. The UI reads and writes ONLY this (FrontendArchitect.md §4). */
export const db = new PowerSyncDatabase({
  schema: AppSchema,
  database: { dbFilename: 'bee4you.db' },
});
