// backend/scripts/reset_workers_db.js
const db = require('../config/database');

async function resetWorkersData() {
  console.log('🔄 Cleaning workers database...');
  try {
    // Delete dependent tables first to respect foreign keys
    await db.query('DELETE FROM attendance');
    console.log('  → Cleared attendance');

    await db.query('DELETE FROM face_photos');
    console.log('  → Cleared face_photos');

    await db.query('DELETE FROM violations');
    console.log('  → Cleared violations');

    await db.query('DELETE FROM salary');
    console.log('  → Cleared salary');

    await db.query('DELETE FROM workers');
    console.log('  → Cleared workers');

    console.log('✅ SQLite worker data completely wiped.');
    process.exit(0);
  } catch (error) {
    console.error('❌ Error clearing database:', error);
    process.exit(1);
  }
}

resetWorkersData();
