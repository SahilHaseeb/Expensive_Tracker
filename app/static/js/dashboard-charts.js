// Dashboard Charts Configuration

// Common Plotly layout settings
const commonLayout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: {
        family: 'Poppins, sans-serif',
        color: '#6c757d'
    },
    margin: { t: 30, b: 0, l: 0, r: 0 },
    showlegend: true,
    legend: {
        orientation: 'h',
        yanchor: 'bottom',
        y: -0.2,
        xanchor: 'center',
        x: 0.5
    }
};

// Responsive charts — resize handler with guard
window.addEventListener('resize', () => {
    const pieEl = document.getElementById('pie-chart');
    const lineEl = document.getElementById('line-chart');
    if (pieEl && typeof Plotly !== 'undefined') {
        try { Plotly.Plots.resize(pieEl); } catch(e) {}
    }
    if (lineEl && typeof Plotly !== 'undefined') {
        try { Plotly.Plots.resize(lineEl); } catch(e) {}
    }
});

// Add hover effects to charts (desktop only — skip on touch devices)
if (window.matchMedia('(hover: hover)').matches) {
    document.querySelectorAll('.chart-container').forEach(container => {
        container.addEventListener('mouseenter', () => {
            container.style.transform = 'scale(1.02)';
            container.style.transition = 'transform 0.3s ease';
        });
        
        container.addEventListener('mouseleave', () => {
            container.style.transform = 'scale(1)';
        });
    });
}

// Export chart as image
function exportChart(chartId) {
    Plotly.downloadImage(chartId, {
        format: 'png',
        width: 1200,
        height: 800,
        filename: 'expense_chart'
    });
}