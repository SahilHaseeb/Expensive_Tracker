// Modern Theme & Navigation Controller

(function() {
    // Initial check before DOM load to avoid flash
    const savedTheme = localStorage.getItem('expensive_tracker_theme') || 
        (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', savedTheme);
})();

document.addEventListener('DOMContentLoaded', function() {
    const html = document.documentElement;
    const themeToggle = document.querySelector('.theme-toggle');
    const mobileNavToggle = document.querySelector('.mobile-nav-toggle');
    const sidebar = document.querySelector('.sidebar');

    // Theme Toggle Handler
    window.toggleTheme = function() {
        const currentTheme = html.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('expensive_tracker_theme', newTheme);
        
        // Dynamic Chart re-theming
        updatePlotlyCharts(newTheme);
        
        // Micro animation on toggle button
        if (themeToggle) {
            themeToggle.style.transform = 'scale(1.2) rotate(180deg)';
            setTimeout(() => {
                themeToggle.style.transform = '';
            }, 300);
        }
    };

    if (themeToggle) {
        themeToggle.addEventListener('click', window.toggleTheme);
    }

    // Keyboard shortcut: Ctrl/Cmd + Shift + D
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'D' || e.key === 'd')) {
            e.preventDefault();
            window.toggleTheme();
        }
    });

    // Mobile Navigation Drawer Toggle
    if (mobileNavToggle && sidebar) {
        mobileNavToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebar.classList.toggle('open');
            const icon = mobileNavToggle.querySelector('i');
            if (icon) {
                if (sidebar.classList.contains('open')) {
                    icon.className = 'fas fa-times';
                } else {
                    icon.className = 'fas fa-bars';
                }
            }
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 768 && sidebar.classList.contains('open') && !sidebar.contains(e.target) && !mobileNavToggle.contains(e.target)) {
                sidebar.classList.remove('open');
                const icon = mobileNavToggle.querySelector('i');
                if (icon) icon.className = 'fas fa-bars';
            }
        });
    }
});

// Update Plotly chart colors dynamically on theme switch
function updatePlotlyCharts(theme) {
    if (typeof Plotly === 'undefined') return;

    const isDark = theme === 'dark';
    const textColor = isDark ? '#E2E8F0' : '#334155';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.07)' : 'rgba(0, 0, 0, 0.05)';

    const pieChart = document.getElementById('pie-chart');
    if (pieChart && window.pieData) {
        Plotly.relayout('pie-chart', {
            'font.color': textColor,
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'plot_bgcolor': 'rgba(0,0,0,0)'
        });
    }

    const lineChart = document.getElementById('line-chart');
    if (lineChart && window.lineData) {
        Plotly.relayout('line-chart', {
            'font.color': textColor,
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'xaxis.gridcolor': gridColor,
            'yaxis.gridcolor': gridColor
        });
    }
}