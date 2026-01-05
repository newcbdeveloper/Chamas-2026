// Charts JavaScript using Chart.js
let incomeExpenseChart, expensePieChart, incomePieChart, spendingTrendChart, categoryBarChart;

// Initialize all charts
function initializeCharts(chartData) {
    initIncomeExpenseChart(chartData);
    initExpensePieChart(chartData);
    initIncomePieChart(chartData);
    initSpendingTrendChart(30);
    initCategoryBarChart(chartData);
}

// Income vs Expense Bar Chart
function initIncomeExpenseChart(chartData) {
    const ctx = document.getElementById('incomeExpenseChart');
    if (!ctx) return;
    
    fetch(`/expense-tracker/charts/data/?type=income_vs_expense&period=${chartData.period}`)
        .then(response => response.json())
        .then(data => {
            if (incomeExpenseChart) {
                incomeExpenseChart.destroy();
            }
            
            incomeExpenseChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Amount (KSh)',
                        data: data.data,
                        backgroundColor: data.colors,
                        borderRadius: 8,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'KSh ' + context.parsed.y.toLocaleString('en-KE', {
                                        minimumFractionDigits: 2,
                                        maximumFractionDigits: 2
                                    });
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return 'KSh ' + value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Error loading income/expense chart:', error));
}

// Expense Breakdown Pie Chart
function initExpensePieChart(chartData) {
    const ctx = document.getElementById('expensePieChart');
    if (!ctx) return;
    
    fetch(`/expense-tracker/charts/data/?type=category_breakdown&transaction_type=expense&period=${chartData.period}`)
        .then(response => response.json())
        .then(data => {
            if (expensePieChart) {
                expensePieChart.destroy();
            }
            
            if (data.labels && data.labels.length > 0) {
                expensePieChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            data: data.data,
                            backgroundColor: data.colors,
                            borderWidth: 2,
                            borderColor: '#fff'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    padding: 15,
                                    font: {
                                        size: 12
                                    }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.parsed;
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return label + ': KSh ' + value.toLocaleString('en-KE', {
                                            minimumFractionDigits: 2
                                        }) + ' (' + percentage + '%)';
                                    }
                                }
                            }
                        }
                    }
                });
            } else {
                ctx.getContext('2d').clearRect(0, 0, ctx.width, ctx.height);
                const parent = ctx.parentElement;
                parent.innerHTML = '<div class="text-center py-5"><p class="text-muted">No expense data available</p></div>';
            }
        })
        .catch(error => console.error('Error loading expense pie chart:', error));
}

// Income Breakdown Pie Chart
function initIncomePieChart(chartData) {
    const ctx = document.getElementById('incomePieChart');
    if (!ctx) return;
    
    fetch(`/expense-tracker/charts/data/?type=category_breakdown&transaction_type=income&period=${chartData.period}`)
        .then(response => response.json())
        .then(data => {
            if (incomePieChart) {
                incomePieChart.destroy();
            }
            
            if (data.labels && data.labels.length > 0) {
                incomePieChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            data: data.data,
                            backgroundColor: data.colors,
                            borderWidth: 2,
                            borderColor: '#fff'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    padding: 15,
                                    font: {
                                        size: 12
                                    }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.parsed;
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return label + ': KSh ' + value.toLocaleString('en-KE', {
                                            minimumFractionDigits: 2
                                        }) + ' (' + percentage + '%)';
                                    }
                                }
                            }
                        }
                    }
                });
            } else {
                ctx.getContext('2d').clearRect(0, 0, ctx.width, ctx.height);
                const parent = ctx.parentElement;
                parent.innerHTML = '<div class="text-center py-5"><p class="text-muted">No income data available</p></div>';
            }
        })
        .catch(error => console.error('Error loading income pie chart:', error));
}

// Spending Trend Line Chart
function initSpendingTrendChart(days) {
    const ctx = document.getElementById('spendingTrendChart');
    if (!ctx) return;
    
    fetch(`/expense-tracker/charts/data/?type=spending_trend&days=${days}`)
        .then(response => response.json())
        .then(data => {
            if (spendingTrendChart) {
                spendingTrendChart.destroy();
            }
            
            spendingTrendChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Daily Expenses (KSh)',
                        data: data.data,
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#e74c3c',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'KSh ' + context.parsed.y.toLocaleString('en-KE', {
                                        minimumFractionDigits: 2,
                                        maximumFractionDigits: 2
                                    });
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return 'KSh ' + value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Error loading spending trend chart:', error));
}

// Update trend chart with different time period
function updateTrendChart(days) {
    initSpendingTrendChart(days);
}

// Category Bar Chart
function initCategoryBarChart(chartData) {
    const ctx = document.getElementById('categoryBarChart');
    if (!ctx) return;
    
    fetch(`/expense-tracker/charts/data/?type=category_breakdown&transaction_type=expense&period=${chartData.period}`)
        .then(response => response.json())
        .then(data => {
            if (categoryBarChart) {
                categoryBarChart.destroy();
            }
            
            if (data.labels && data.labels.length > 0) {
                // Take top 5 categories
                const topLabels = data.labels.slice(0, 5);
                const topData = data.data.slice(0, 5);
                const topColors = data.colors.slice(0, 5);
                
                categoryBarChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: topLabels,
                        datasets: [{
                            label: 'Amount (KSh)',
                            data: topData,
                            backgroundColor: topColors,
                            borderRadius: 8,
                            borderWidth: 0
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        return 'KSh ' + context.parsed.x.toLocaleString('en-KE', {
                                            minimumFractionDigits: 2,
                                            maximumFractionDigits: 2
                                        });
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                beginAtZero: true,
                                ticks: {
                                    callback: function(value) {
                                        return 'KSh ' + value.toLocaleString();
                                    }
                                }
                            }
                        }
                    }
                });
            } else {
                ctx.getContext('2d').clearRect(0, 0, ctx.width, ctx.height);
                const parent = ctx.parentElement;
                parent.innerHTML = '<div class="text-center py-5"><p class="text-muted">No data available</p></div>';
            }
        })
        .catch(error => console.error('Error loading category bar chart:', error));
}

// Export chart as image
function exportChartAsImage(chartId, filename) {
    const canvas = document.getElementById(chartId);
    if (canvas) {
        const url = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        link.download = filename + '.png';
        link.href = url;
        link.click();
    }
}