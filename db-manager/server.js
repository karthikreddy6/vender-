import 'dotenv/config';
import cors from 'cors';
import express from 'express';
import pg from 'pg';

const { Pool } = pg;
const port = Number(process.env.PORT || 8002);
// Allows reuse of the Python service's postgresql+asyncpg DATABASE_URL.
const databaseUrl = (process.env.DATABASE_URL || '').replace('postgresql+asyncpg://', 'postgresql://');

if (!databaseUrl) throw new Error('DATABASE_URL is required. Copy .env.admin.example to .env and configure it.');

const pool = new Pool({ connectionString: databaseUrl });
const app = express();
app.use(cors());
app.use(express.json({ limit: '1mb' }));
app.use(express.static('public'));

const resources = {
  colleges: { table: 'colleges', id: 'id', fields: ['name', 'is_active'] },
  canteens: { table: 'canteens', id: 'id', fields: ['name', 'is_active'] },
  categories: { table: 'categories', id: 'id', fields: ['name', 'icon_url', 'display_order', 'is_active'] },
  menu: { table: 'menu_items', id: 'id', fields: ['name', 'price', 'original_price', 'discount_percent', 'category_id', 'canteen_id', 'image_url', 'description', 'stock', 'is_student_visible', 'is_special_offer', 'is_available', 'preparation_time_minutes'] },
  orders: { table: 'orders', id: 'id', fields: ['status', 'canteen_id', 'pickup_number', 'order_token', 'estimated_ready_at', 'actual_ready_at', 'scheduled_date', 'scheduled_slot_id', 'notes'] },
  users: { table: 'users', id: 'id', fields: ['name', 'email', 'phone', 'roll_number', 'college', 'college_id', 'preferred_canteen_id', 'use_roll_number_as_order_token'] },
  vendors: { table: 'vendor_accounts', id: 'id', fields: ['name', 'email', 'role', 'is_active', 'canteen_id'] },
  staff: { table: 'staff_members', id: 'id', fields: ['name', 'role', 'status', 'image_url', 'canteen_id'] },
  time_slots: { table: 'time_slots', id: 'id', fields: ['start_time', 'end_time', 'max_orders', 'is_active'] },
  kitchen_settings: { table: 'kitchen_settings', id: 'id', fields: ['base_prep_buffer_minutes', 'max_concurrent_orders', 'is_accepting_orders'] }
};

function resourceOr404(name, res) {
  const resource = resources[name];
  if (!resource) { res.status(404).json({ error: 'Unknown resource' }); return null; }
  return resource;
}
function permittedValues(resource, body) {
  return Object.entries(body || {}).filter(([key, value]) => resource.fields.includes(key) && value !== undefined);
}

app.get('/health', async (_req, res, next) => {
  try { await pool.query('SELECT 1'); res.json({ ok: true }); } catch (error) { next(error); }
});
app.get('/api/admin', (_req, res) => res.json({ resources: Object.keys(resources) }));
app.get('/api/admin/:resource', async (req, res, next) => {
  const resource = resourceOr404(req.params.resource, res); if (!resource) return;
  const limit = Math.min(Math.max(Number(req.query.limit) || 100, 1), 500);
  try {
    const { rows } = await pool.query(`SELECT * FROM ${resource.table} ORDER BY ${resource.id} DESC LIMIT $1`, [limit]);
    res.json(rows);
  } catch (error) { next(error); }
});
app.get('/api/admin/:resource/:id', async (req, res, next) => {
  const resource = resourceOr404(req.params.resource, res); if (!resource) return;
  try {
    const { rows } = await pool.query(`SELECT * FROM ${resource.table} WHERE ${resource.id} = $1`, [req.params.id]);
    if (!rows[0]) return res.status(404).json({ error: 'Record not found' });
    res.json(rows[0]);
  } catch (error) { next(error); }
});
app.post('/api/admin/:resource', async (req, res, next) => {
  const resource = resourceOr404(req.params.resource, res); if (!resource) return;
  const values = permittedValues(resource, req.body);
  if (!values.length) return res.status(400).json({ error: 'No permitted fields supplied' });
  const columns = values.map(([key]) => key);
  try {
    const { rows } = await pool.query(`INSERT INTO ${resource.table} (${columns.join(', ')}) VALUES (${columns.map((_, i) => `$${i + 1}`).join(', ')}) RETURNING *`, values.map(([, value]) => value));
    res.status(201).json(rows[0]);
  } catch (error) { next(error); }
});
app.patch('/api/admin/:resource/:id', async (req, res, next) => {
  const resource = resourceOr404(req.params.resource, res); if (!resource) return;
  const values = permittedValues(resource, req.body);
  if (!values.length) return res.status(400).json({ error: 'No permitted fields supplied' });
  const set = values.map(([key], i) => `${key} = $${i + 1}`).join(', ');
  try {
    const { rows } = await pool.query(`UPDATE ${resource.table} SET ${set} WHERE ${resource.id} = $${values.length + 1} RETURNING *`, [...values.map(([, value]) => value), req.params.id]);
    if (!rows[0]) return res.status(404).json({ error: 'Record not found' });
    res.json(rows[0]);
  } catch (error) { next(error); }
});
app.delete('/api/admin/:resource/:id', async (req, res, next) => {
  const resource = resourceOr404(req.params.resource, res); if (!resource) return;
  try {
    const result = await pool.query(`DELETE FROM ${resource.table} WHERE ${resource.id} = $1`, [req.params.id]);
    if (!result.rowCount) return res.status(404).json({ error: 'Record not found' });
    res.status(204).end();
  } catch (error) { next(error); }
});

app.use((error, _req, res, _next) => {
  console.error(error);
  res.status(500).json({ error: 'Database operation failed', detail: error.message });
});

app.listen(port, '0.0.0.0', () => console.log(`OnFood database manager listening at http://0.0.0.0:${port}`));
