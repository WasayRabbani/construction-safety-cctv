const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../.env') });

const express = require('express');
const cors = require('cors');

const app = express();
const PORT = process.env.API_PORT || 4000;

// Middleware
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Static files
app.use(express.static(path.join(__dirname, '../frontend')));
app.use('/uploads', express.static(path.join(__dirname, '../uploads')));
app.use('/hls', express.static(path.join(__dirname, '../hls')));

// Routes
const authRoutes = require('./routes/auth');
const workersRoutes = require('./routes/workers');
const attendanceRoutes = require('./routes/attendance');
const violationsRoutes = require('./routes/violations');
const salaryRoutes = require('./routes/salary');
const healthRoutes = require('./routes/health');
const testRoutes = require('./routes/test');
const faceAttendanceRoutes = require('./routes/face_attendance');

app.use('/api/auth', authRoutes);
app.use('/api/workers', workersRoutes);
app.use('/api/attendance', attendanceRoutes);
app.use('/api/violations', violationsRoutes);
app.use('/api/salary', salaryRoutes);
app.use('/api/health', healthRoutes);
app.use('/api/test', testRoutes);
app.use('/api/face-attendance', faceAttendanceRoutes);

// =======================
// Pages
// =======================

// Landing Page (Default Home Page)
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/landingpage.html'));
});

// Optional Landing Page Route
app.get('/landingpage', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/landingpage.html'));
});

// Login
app.get('/login', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/login.html'));
});

// Signup
app.get('/signup', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/signup.html'));
});

// Dashboard
app.get('/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/dashboard.html'));
});

app.get('/dashboard.html', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/dashboard.html'));
});

// =======================
// Catch-All Route
// =======================
app.use((req, res) => {
    const filePath = path.join(
        __dirname,
        '../frontend',
        req.path.replace(/\/$/, '') + '.html'
    );

    res.sendFile(filePath, (err) => {
        if (err) {
            res.status(404).sendFile(
                path.join(__dirname, '../frontend/landingpage.html')
            );
        }
    });
});

// =======================
// Error Handler
// =======================
app.use((err, req, res, next) => {
    console.error('Server error:', err);
    res.status(500).json({ error: 'Internal server error' });
});

// =======================
// Start Server
// =======================
app.listen(PORT, () => {
    console.log('='.repeat(60));
    console.log('✅ Server running on http://localhost:' + PORT);
    console.log('🏠 Landing Page : http://localhost:' + PORT + '/');
    console.log('🌐 Landing URL  : http://localhost:' + PORT + '/landingpage');
    console.log('🔐 Login Page   : http://localhost:' + PORT + '/login');
    console.log('📝 Signup Page  : http://localhost:' + PORT + '/signup');
    console.log('📊 Dashboard    : http://localhost:' + PORT + '/dashboard');
    console.log('='.repeat(60));
    console.log('\n📋 Demo Credentials:');
    console.log('   Admin      : admin / admin123');
    console.log('   Supervisor : supervisor / super123');
    console.log('   Worker     : worker1 / worker123');
    console.log('='.repeat(60));
});