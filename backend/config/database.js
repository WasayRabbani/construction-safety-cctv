// File: backend/config/database.js
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

const DB_PATH = path.join(__dirname, '..', 'database', 'safety.sqlite');

const db = new sqlite3.Database(DB_PATH, (err) => {
    if (err) {
        console.error('❌ SQLite connection failed:', err.message);
    } else {
        console.log('✅ SQLite database connected successfully:', DB_PATH);
    }
});

// Enable foreign key constraints in SQLite
db.run('PRAGMA foreign_keys = ON');

/**
 * Normalizes common MySQL date/time functions to SQLite syntax
 * so existing queries in backend routes continue working without modification.
 */
function normalizeQuery(sql) {
    let converted = sql;

    // NOW() -> datetime('now', 'localtime')
    converted = converted.replace(/\bNOW\(\)/gi, "datetime('now', 'localtime')");

    // CURDATE() -> date('now', 'localtime')
    converted = converted.replace(/\bCURDATE\(\)/gi, "date('now', 'localtime')");

    // DATE_SUB(NOW(), INTERVAL X DAY) -> datetime('now', 'localtime', '-X days')
    converted = converted.replace(
        /DATE_SUB\(\s*NOW\(\)\s*,\s*INTERVAL\s*(\d+)\s*DAY\s*\)/gi,
        "datetime('now', 'localtime', '-$1 days')"
    );

    // DATE_SUB(CURDATE(), INTERVAL X DAY) -> date('now', 'localtime', '-X days')
    converted = converted.replace(
        /DATE_SUB\(\s*CURDATE\(\)\s*,\s*INTERVAL\s*(\d+)\s*DAY\s*\)/gi,
        "date('now', 'localtime', '-$1 days')"
    );

    // DATE_ADD(CURDATE(), INTERVAL -X DAY) -> date('now', 'localtime', '-X days')
    converted = converted.replace(
        /DATE_ADD\(\s*CURDATE\(\)\s*,\s*INTERVAL\s*-(\d+)\s*DAY\s*\)/gi,
        "date('now', 'localtime', '-$1 days')"
    );

    return converted;
}

/**
 * Adapter providing the `db.query(sql, params)` interface identical to `mysql2/promise`.
 * Returns a Promise that resolves to `[rows, fields]` or `[result, fields]`.
 */
function query(sql, params = []) {
    return new Promise((resolve, reject) => {
        const cleanSql = normalizeQuery(sql.trim());
        const isSelect = /^SELECT|^PRAGMA/i.test(cleanSql);

        if (isSelect) {
            db.all(cleanSql, params, (err, rows) => {
                if (err) return reject(err);
                resolve([rows || [], []]);
            });
        } else {
            db.run(cleanSql, params, function (err) {
                if (err) return reject(err);
                const result = {
                    insertId: this.lastID,
                    affectedRows: this.changes,
                    changes: this.changes
                };
                resolve([result, []]);
            });
        }
    });
}

module.exports = {
    query,
    rawDb: db
};