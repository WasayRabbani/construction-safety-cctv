const API_BASE = 'http://localhost:4000/api';

const PAGE_ROLE_PERMISSIONS = {
    'dashboard.html': ['admin', 'safety officer', 'hr', 'monitor', 'accounts', 'supervisor', 'worker'],
    'attendance.html': ['admin', 'safety officer', 'hr', 'supervisor'],
    'health.html': ['admin', 'safety officer', 'hr', 'supervisor'],
    'violations.html': ['admin', 'safety officer', 'supervisor'],
    'salary.html': ['admin', 'hr', 'accounts'],
    'workers.html': ['admin', 'hr', 'supervisor'],
    'cctv.html': ['admin', 'monitor', 'supervisor'],
    'face-recognition.html': ['admin', 'monitor', 'supervisor'],
};

function getPageName() {
    let page = window.location.pathname.split('/').pop();
    if (!page) {
        return 'dashboard.html';
    }
    if (!page.endsWith('.html')) {
        page = page + '.html';
    }
    return page;
}

function getStoredUser() {
    try {
        return JSON.parse(localStorage.getItem('user') || 'null');
    } catch (error) {
        return null;
    }
}

function redirectToLogin() {
    window.location.href = 'login.html';
}

function redirectToDashboard() {
    window.location.href = 'dashboard.html';
}

function applyNavPermissions(user) {
    if (!user) {
        return;
    }

    document.querySelectorAll('.nav-menu .nav-btn').forEach((btn) => {
        const href = btn.getAttribute('href');
        const allowed = PAGE_ROLE_PERMISSIONS[href];
        if (allowed && !allowed.includes(user.role)) {
            btn.style.display = 'none';
        }
    });
}

function protectPageAccess() {
    const page = getPageName();
    const token = localStorage.getItem('token');
    const user = getStoredUser();

    if (page === 'login.html' || page === 'signup.html') {
        if (token && user) {
            redirectToDashboard();
        }
        return;
    }

    if (!token || !user) {
        redirectToLogin();
        return;
    }

    const allowedRoles = PAGE_ROLE_PERMISSIONS[page];
    if (allowedRoles && !allowedRoles.includes(user.role)) {
        alert('Access denied: your role does not have permission to view this page.');
        redirectToDashboard();
        return;
    }

    applyNavPermissions(user);
}

window.addEventListener('load', protectPageAccess);

if (!window.handleLogout) {
    window.handleLogout = function () {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = 'login.html';
    };
}
