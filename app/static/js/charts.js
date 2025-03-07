/**
 * charts.js - Scripts para gráficos y visualizaciones de datos
 */

// Función para inicializar todos los gráficos
function initCharts() {
    // Verificar si Chart.js está disponible
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js no está disponible. Los gráficos no se inicializarán.');
        return;
    }
    
    // Configuración global de Chart.js
    Chart.defaults.font.family = "'Open Sans', sans-serif";
    Chart.defaults.color = '#666';
    Chart.defaults.responsive = true;
    
    // Colores para los gráficos
    const chartColors = {
        primary: '#3498db',
        secondary: '#2ecc71',
        accent: '#f39c12',
        danger: '#e74c3c',
        dark: '#2c3e50',
        light: '#ecf0f1',
        gray: '#95a5a6'
    };
    
    // Inicializar gráfico de actividad emprendedora
    initActivityChart();
    
    // Inicializar gráfico de horas de mentoría
    initMentorshipHoursChart();
    
    // Inicializar gráfico de progreso de emprendedores
    initEntrepreneurProgressChart();
    
    // Inicializar gráfico de distribución por industria
    initIndustryDistributionChart();
    
    // Función para inicializar gráfico de actividad emprendedora
    function initActivityChart() {
        const activityChartEl = document.getElementById('activity-chart');
        if (!activityChartEl) return;
        
        // Datos de ejemplo - Esto debería venir de tu backend
        const activityData = {
            labels: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
            datasets: [{
                label: 'Nuevos emprendedores',
                data: [5, 8, 12, 10, 15, 20, 18, 25, 22, 30, 28, 35],
                backgroundColor: chartColors.primary,
                borderColor: chartColors.primary,
                tension: 0.4,
                fill: false
            }, {
                label: 'Reuniones realizadas',
                data: [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65],
                backgroundColor: chartColors.secondary,
                borderColor: chartColors.secondary,
                tension: 0.4,
                fill: false
            }]
        };
        
        new Chart(activityChartEl, {
            type: 'line',
            data: activityData,
            options: {
                plugins: {
                    title: {
                        display: true,
                        text: 'Actividad Emprendedora Anual',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Cantidad'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Mes'
                        }
                    }
                }
            }
        });
    }
    
    // Función para inicializar gráfico de horas de mentoría
    function initMentorshipHoursChart() {
        const mentorshipChartEl = document.getElementById('mentorship-hours-chart');
        if (!mentorshipChartEl) return;
        
        // Datos de ejemplo - Esto debería venir de tu backend
        const mentorshipData = {
            labels: ['Semana 1', 'Semana 2', 'Semana 3', 'Semana 4'],
            datasets: [{
                label: 'Horas asignadas',
                data: [40, 40, 40, 40],
                backgroundColor: chartColors.light,
                borderColor: chartColors.gray,
                borderWidth: 1
            }, {
                label: 'Horas utilizadas',
                data: [25, 30, 35, 20],
                backgroundColor: chartColors.accent,
                borderColor: chartColors.accent,
                borderWidth: 1
            }]
        };
        
        new Chart(mentorshipChartEl, {
            type: 'bar',
            data: mentorshipData,
            options: {
                plugins: {
                    title: {
                        display: true,
                        text: 'Horas de Mentoría - Mes Actual',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Horas'
                        }
                    }
                }
            }
        });
    }
    
    // Función para inicializar gráfico de progreso de emprendedores
    function initEntrepreneurProgressChart() {
        const progressChartEl = document.getElementById('entrepreneur-progress-chart');
        if (!progressChartEl) return;
        
        // Datos de ejemplo - Esto debería venir de tu backend
        const progressData = {
            labels: ['Idea', 'Validación', 'MVP', 'Primeras ventas', 'Crecimiento', 'Escalabilidad'],
            datasets: [{
                label: 'Cantidad de emprendedores',
                data: [15, 12, 8, 6, 4, 2],
                backgroundColor: [
                    chartColors.primary,
                    chartColors.secondary,
                    chartColors.accent,
                    chartColors.dark,
                    chartColors.danger,
                    chartColors.gray
                ],
                borderWidth: 0
            }]
        };
        
        new Chart(progressChartEl, {
            type: 'pie',
            data: progressData,
            options: {
                plugins: {
                    title: {
                        display: true,
                        text: 'Distribución por Etapa de Emprendimiento',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    },
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
    }
    
    // Función para inicializar gráfico de distribución por industria
    function initIndustryDistributionChart() {
        const industryChartEl = document.getElementById('industry-distribution-chart');
        if (!industryChartEl) return;
        
        // Datos de ejemplo - Esto debería venir de tu backend
        const industryData = {
            labels: ['Tecnología', 'Alimentación', 'Salud', 'Educación', 'Finanzas', 'Otros'],
            datasets: [{
                label: 'Cantidad de emprendimientos',
                data: [20, 15, 10, 8, 5, 7],
                backgroundColor: [
                    chartColors.primary,
                    chartColors.secondary,
                    chartColors.accent,
                    chartColors.dark,
                    chartColors.danger,
                    chartColors.gray
                ],
                borderWidth: 0
            }]
        };
        
        new Chart(industryChartEl, {
            type: 'doughnut',
            data: industryData,
            options: {
                plugins: {
                    title: {
                        display: true,
                        text: 'Distribución por Industria',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    },
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
    }
}

// Inicializar gráficos cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    initCharts();
    
    // Reinicializar gráficos cuando cambie el tamaño de la ventana
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            initCharts();
        }, 250);
    });
});

// Función para actualizar gráficos con nuevos datos
function updateChartData(chartId, newData) {
    const chartElement = document.getElementById(chartId);
    if (!chartElement) return;
    
    const chartInstance = Chart.getChart(chartElement);
    if (!chartInstance) return;
    
    // Actualizar datos
    chartInstance.data = newData;
    chartInstance.update();
}

// Exportar funciones para uso en otros scripts
window.chartUtils = {
    initCharts: initCharts,
    updateChartData: updateChartData
};