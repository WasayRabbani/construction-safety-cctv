const fs = require('fs');
const path = require('path');
const dir = 'frontend';
const files = fs.readdirSync(dir);

for (const file of files) {
    if (!file.endsWith('.html')) continue;
    if (['video-analysis.html', 'landingpage.html', 'login.html', 'signup.html'].includes(file)) continue;
    
    const filePath = path.join(dir, file);
    let content = fs.readFileSync(filePath, 'utf-8');
    
    if (content.includes('video-analysis.html')) continue;
    
    if (content.includes('</nav>')) {
        content = content.replace('</nav>', '    <a href="video-analysis.html" class="nav-btn"><i class="fa-solid fa-upload"></i> Video Analysis</a>\n        </nav>');
        fs.writeFileSync(filePath, content, 'utf-8');
        console.log('Updated ' + file);
    }
}
