import { column, Schema, Table } from '@powersync/react-native';

/**
 * Local SQLite schema = FrontendArchitect.md §4.0 (the backend data contract).
 * `id` is implicit (text). Column names must match the backend exactly.
 * numeric amounts arrive as TEXT, booleans as INTEGER 0/1, timestamps as TEXT.
 */

const common = {
  owner_id: column.text,
  created_at: column.text,
  updated_at: column.text,
  client_updated_at: column.text,
  deleted_at: column.text,
};

const profiles = new Table({ ...common, display_name: column.text, locale: column.text });

const apiaries = new Table({
  ...common,
  name: column.text,
  kind: column.text,
  notes: column.text,
  lat: column.real,
  lng: column.real,
});

const colonies = new Table({
  ...common,
  label: column.text,
  number: column.integer,
  mode: column.text,
  status: column.text,
  queen_year: column.integer,
  notes: column.text,
});

const colony_placements = new Table(
  {
    ...common,
    colony_id: column.text,
    apiary_id: column.text,
    started_at: column.text,
    ended_at: column.text,
  },
  { indexes: { colony: ['colony_id'], apiary: ['apiary_id'] } },
);

const inventory_items = new Table({
  ...common,
  name: column.text,
  category: column.text,
  unit: column.text,
  apiary_id: column.text,
  notes: column.text,
});

const inventory_adjustments = new Table(
  {
    ...common,
    item_id: column.text,
    delta: column.text,
    unit: column.text,
    reason: column.text,
    apiary_id: column.text,
    adjusted_at: column.text,
    treatment_id: column.text,
    notes: column.text,
    source: column.text,
  },
  { indexes: { item: ['item_id'] } },
);

const treatments = new Table(
  {
    ...common,
    colony_id: column.text,
    apiary_id: column.text,
    inventory_item_id: column.text,
    product_name: column.text,
    amount: column.text,
    unit: column.text,
    treated_at: column.text,
    notes: column.text,
    source: column.text,
  },
  { indexes: { colony: ['colony_id'] } },
);

const harvests = new Table(
  {
    ...common,
    apiary_id: column.text,
    colony_id: column.text,
    quantity: column.text,
    unit: column.text,
    harvested_at: column.text,
    notes: column.text,
    source: column.text,
  },
  { indexes: { apiary: ['apiary_id'], colony: ['colony_id'] } },
);

const colony_notes = new Table(
  {
    ...common,
    colony_id: column.text,
    apiary_id: column.text,
    noted_at: column.text,
    queen_seen: column.integer,
    temperament: column.text,
    text: column.text,
    source: column.text,
  },
  { indexes: { colony: ['colony_id'] } },
);

const voice_notes = new Table({
  ...common,
  transcript: column.text,
  audio_path: column.text,
  locale: column.text,
  context_colony_id: column.text,
  context_apiary_id: column.text,
  status: column.text,
  thread_id: column.text,
  result_record_type: column.text,
  result_record_id: column.text,
  error: column.text,
});

/**
 * Local-only (never synced): uploads the server rejected, kept so the Sync screen can show
 * them — after the next sync the rejected change disappears from the synced tables.
 */
const upload_rejections = new Table(
  {
    table_name: column.text,
    record_id: column.text,
    op: column.text,
    data: column.text,
    error: column.text,
    created_at: column.text,
  },
  { localOnly: true },
);

export const AppSchema = new Schema({
  profiles,
  apiaries,
  colonies,
  colony_placements,
  inventory_items,
  inventory_adjustments,
  treatments,
  harvests,
  colony_notes,
  voice_notes,
  upload_rejections,
});

export type Database = (typeof AppSchema)['types'];
