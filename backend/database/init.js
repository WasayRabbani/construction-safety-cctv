// File: backend/database/init.js
const fs = require('fs');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();
const bcrypt = require('bcrypt');

const DB_DIR = path.join(__dirname);
const DB_FILE = path.join(DB_DIR, 'safety.sqlite');
const SCHEMA_FILE = path.join(DB_DIR, 'schema.sql');

if (!fs.existsSync(DB_DIR)) {
    fs.mkdirSync(DB_DIR, { recursive: true });
}

const db = new sqlite3.Database(DB_FILE, (err) => {
    if (err) {
        console.error('❌ Failed to open SQLite database:', err.message);
        process.exit(1);
    }
    console.log('✅ SQLite database file connected:', DB_FILE);
});

async function init() {
    return new Promise((resolve, reject) => {
        const schema = fs.readFileSync(SCHEMA_FILE, 'utf8');

        // Execute all schema table creation statements
        db.exec(schema, async (err) => {
            if (err) {
                console.error('❌ Failed to execute schema.sql:', err.message);
                return reject(err);
            }
            console.log('✅ Schema tables & indexes initialized.');

            try {
                // 1. Seed Admin User
                await seedAdmin();

                // 2. Seed Default Cameras
                await seedCameras();

                // 3. Seed Initial Workers
                await seedWorkers();

                console.log('\n🎉 Database initialization & seeding completed successfully!\n');
                resolve();
            } catch (seedErr) {
                reject(seedErr);
            }
        });
    });
}

function runAsync(sql, params = []) {
    return new Promise((resolve, reject) => {
        db.run(sql, params, function (err) {
            if (err) reject(err);
            else resolve(this);
        });
    });
}

function getAsync(sql, params = []) {
    return new Promise((resolve, reject) => {
        db.get(sql, params, (err, row) => {
            if (err) reject(err);
            else resolve(row);
        });
    });
}

async function seedAdmin() {
    const admin = await getAsync('SELECT * FROM users WHERE username = ?', ['admin']);
    if (!admin) {
        const hashedPassword = await bcrypt.hash('password123', 10);
        await runAsync(
            `INSERT INTO users (username, password_hash, full_name, role, status)
             VALUES (?, ?, ?, ?, ?)`,
            ['admin', hashedPassword, 'System Administrator', 'admin', 'active']
        );
        console.log('  → Admin created (username: "admin", password: "password123")');
    } else {
        console.log('  → Admin user already exists.');
    }
}

async function seedCameras() {
    const count = await getAsync('SELECT COUNT(*) as count FROM cameras');
    if (count && count.count === 0) {
        const cameras = [
            ['Camera 1 - Main Entrance', 'Main Gate Entry', '1920x1080', 30],
            ['Camera 2 - Construction Zone A', 'Zone A - Floor 2', '1920x1080', 30],
            ['Camera 3 - Equipment Storage', 'Storage Unit B', '1920x1080', 30],
            ['Camera 4 - Site Perimeter', 'North Perimeter', '1920x1080', 30]
        ];

        for (const cam of cameras) {
            await runAsync(
                `INSERT INTO cameras (camera_name, location, resolution, fps) VALUES (?, ?, ?, ?)`,
                cam
            );
        }
        console.log('  → Seeded 4 default CCTV cameras.');
    }
}

async function seedWorkers() {
    const count = await getAsync('SELECT COUNT(*) as count FROM workers');
    if (count && count.count === 0) {
        const workers = [
            ['W001', 'Ahmad Ali', '12345-1234567-1', '+92 300 1234567', 'Construction', 'daily', 500, '2024-01-15'],
            ['W002', 'Hassan Khan', '12345-2345678-2', '+92 301 2345678', 'Electrical', 'hourly', 50, '2024-02-20'],
            ['W003', 'Bilal Ahmed', '12345-3456789-3', '+92 302 3456789', 'Plumbing', 'daily', 500, '2024-03-10'],
            ['W004', 'Usman Tariq', '12345-4567890-4', '+92 303 4567890', 'Construction', 'daily', 500, '2024-04-05']
        ];

        for (const w of workers) {
            await runAsync(
                `INSERT INTO workers (worker_id, name, cnic, phone, department, wage_type, wage_rate, join_date)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
                w
            );
        }
        console.log('  → Seeded 4 initial construction workers.');
    }
}

init()
    .then(() => {
        db.close();
        process.exit(0);
    })
    .catch((err) => {
        console.error('❌ Init error:', err);
        db.close();
        process.exit(1);
    });
