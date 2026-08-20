// File: backend/config/database.js
const mysql = require('mysql2');
require('dotenv').config({ path: __dirname + '/.env' });

const pool = mysql.createPool({
    host: process.env.DB_HOST || '127.0.0.1',
      port: process.env.DB_PORT || 3306,
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_NAME || 'construction_safety',
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
});

// Create promise pool
const promisePool = pool.promise();

// Test connection
pool.getConnection((err, connection) => {
    if (err) {
        console.error('❌ Database connection failed:', err.message);
    } else {
        console.log('✅ Database connected successfully!');
        connection.release();
    }
});

// IMPORTANT: Export the promise pool, not the regular pool
module.exports = promisePool;