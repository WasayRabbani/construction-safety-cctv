const db = require('./config/database');
const bcrypt = require('bcrypt');

async function createAdmin() {
    try {
        const username = 'admin';
        const password = 'password123';
        const hashedPassword = await bcrypt.hash(password, 10);
        
        // Check if admin already exists
        const [existing] = await db.query('SELECT * FROM users WHERE username = ?', [username]);
        if (existing.length > 0) {
            console.log('Admin user already exists. Updating password...');
            await db.query('UPDATE users SET password_hash = ? WHERE username = ?', [hashedPassword, username]);
        } else {
            console.log('Creating new admin user...');
            await db.query(
                'INSERT INTO users (username, password_hash, full_name, role, status) VALUES (?, ?, ?, ?, ?)',
                [username, hashedPassword, 'System Administrator', 'admin', 'active']
            );
        }
        
        console.log('\n✅ Admin account is ready!');
        console.log('Username: admin');
        console.log('Password: password123');
        process.exit(0);
    } catch (err) {
        console.error('❌ Error creating admin:', err.message);
        process.exit(1);
    }
}

createAdmin();
