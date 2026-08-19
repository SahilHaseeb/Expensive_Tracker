// Theme Toggle Logic - Fixed Version
document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.querySelector('.theme-toggle');
    const html = document.documentElement;
    
    // Check saved theme or default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    html.setAttribute('data-theme', savedTheme);
    console.log('Current theme:', savedTheme);
    
    // Toggle function
    window.toggleTheme = function() {
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        console.log('Theme changed to:', newTheme);
        
        // Update chart colors if they exist
        updateChartColors(newTheme);
        
        // Button animation
        if (themeToggle) {
            themeToggle.style.transform = 'scale(1.2) rotate(180deg)';
            setTimeout(() => {
                themeToggle.style.transform = 'scale(1) rotate(0deg)';
            }, 300);
        }
    };
    
    // Click handler
    if (themeToggle) {
        themeToggle.addEventListener('click', window.toggleTheme);
    }
    
    // Keyboard shortcut: Ctrl/Cmd + Shift + D
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
            e.preventDefault();
            window.toggleTheme();
        }
    });
});

function updateChartColors(theme) {
    // Update Plotly charts if they exist
    const pieChart = document.getElementById('pie-chart');
    const lineChart = document.getElementById('line-chart');
    
    if (pieChart && window.pieData) {
        const textColor = theme === 'dark' ? '#e0e0e0' : '#2D3436';
        const newLayout = {
            ...window.pieData.layout,
            font: { ...window.pieData.layout.font, color: textColor }
        };
        Plotly.relayout('pie-chart', newLayout);
    }
    
    if (lineChart && window.lineData) {
        const textColor = theme === 'dark' ? '#e0e0e0' : '#2D3436';
        const newLayout = {
            ...window.lineData.layout,
            font: { ...window.lineData.layout.font, color: textColor }
        };
        Plotly.relayout('line-chart', newLayout);
    }
}