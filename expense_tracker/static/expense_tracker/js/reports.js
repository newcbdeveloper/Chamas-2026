// Reports JavaScript
$(document).ready(function() {
    
    // Initialize date range picker behavior
    const $periodSelect = $('[name="period"]');
    const $customDates = $('#custom-dates');
    const $customDatesEnd = $('#custom-dates-end');
    
    $periodSelect.on('change', function() {
        if ($(this).val() === 'custom') {
            $customDates.show();
            $customDatesEnd.show();
            $('[name="start_date"]').prop('required', true);
            $('[name="end_date"]').prop('required', true);
        } else {
            $customDates.hide();
            $customDatesEnd.hide();
            $('[name="start_date"]').prop('required', false);
            $('[name="end_date"]').prop('required', false);
        }
    });
    
    // Trigger on page load
    $periodSelect.trigger('change');
    
    // Export functionality with loading indicator
    $('.btn-export').on('click', function(e) {
        const $btn = $(this);
        const originalText = $btn.html();
        
        // Show loading
        $btn.html('<span class="spinner-border spinner-border-sm me-2"></span>Exporting...');
        $btn.prop('disabled', true);
        
        // Reset after delay (actual export happens via link)
        setTimeout(function() {
            $btn.html(originalText);
            $btn.prop('disabled', false);
        }, 2000);
    });
    
    // Print report
    $('#print-report').on('click', function(e) {
        e.preventDefault();
        window.print();
    });
    
    // Toggle breakdown tables
    $('.toggle-breakdown').on('click', function() {
        const target = $(this).data('target');
        $(target).slideToggle();
        $(this).find('i').toggleClass('fa-chevron-down fa-chevron-up');
    });
    
    // Comparison chart
    if ($('#comparisonChart').length) {
        const ctx = document.getElementById('comparisonChart').getContext('2d');
        
        const currentIncome = parseFloat($('#current-income').data('value')) || 0;
        const currentExpense = parseFloat($('#current-expense').data('value')) || 0;
        const previousIncome = parseFloat($('#previous-income').data('value')) || 0;
        const previousExpense = parseFloat($('#previous-expense').data('value')) || 0;
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Income', 'Expenses'],
                datasets: [
                    {
                        label: 'Current Period',
                        data: [currentIncome, currentExpense],
                        backgroundColor: ['#27ae60', '#e74c3c'],
                        borderRadius: 8
                    },
                    {
                        label: 'Previous Period',
                        data: [previousIncome, previousExpense],
                        backgroundColor: ['rgba(39, 174, 96, 0.5)', 'rgba(231, 76, 60, 0.5)'],
                        borderRadius: 8
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': KSh ' + 
                                    context.parsed.y.toLocaleString('en-KE', {
                                        minimumFractionDigits: 2
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
    }
    
    // Email report
    $('#email-report').on('click', function(e) {
        e.preventDefault();
        
        $('#emailModal').modal('show');
    });
    
    $('#send-email-report').on('click', function() {
        const email = $('#recipient-email').val();
        
        if (!email || !isValidEmail(email)) {
            alert('Please enter a valid email address');
            return;
        }
        
        const $btn = $(this);
        const originalText = $btn.text();
        
        $btn.html('<span class="spinner-border spinner-border-sm me-2"></span>Sending...');
        $btn.prop('disabled', true);
        
        // Send report via AJAX
        $.ajax({
            url: '/expense-tracker/reports/email/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            data: {
                email: email,
                period: $periodSelect.val(),
                start_date: $('[name="start_date"]').val(),
                end_date: $('[name="end_date"]').val()
            },
            success: function(response) {
                alert('Report sent successfully!');
                $('#emailModal').modal('hide');
            },
            error: function() {
                alert('Error sending report. Please try again.');
            },
            complete: function() {
                $btn.text(originalText);
                $btn.prop('disabled', false);
            }
        });
    });
    
    // Savings rate calculation
    function calculateSavingsRate() {
        const income = parseFloat($('#total-income').data('value')) || 0;
        const expenses = parseFloat($('#total-expenses').data('value')) || 0;
        
        if (income > 0) {
            const savings = income - expenses;
            const rate = (savings / income) * 100;
            $('#savings-rate').text(rate.toFixed(1) + '%');
            
            // Update progress bar
            $('#savings-progress').css('width', Math.max(0, rate) + '%');
            
            // Color code
            if (rate >= 20) {
                $('#savings-progress').removeClass().addClass('progress-bar bg-success');
            } else if (rate >= 10) {
                $('#savings-progress').removeClass().addClass('progress-bar bg-warning');
            } else {
                $('#savings-progress').removeClass().addClass('progress-bar bg-danger');
            }
        }
    }
    
    // Filter breakdown by amount threshold
    $('#amount-threshold').on('input', function() {
        const threshold = parseFloat($(this).val()) || 0;
        
        $('.breakdown-row').each(function() {
            const amount = parseFloat($(this).data('amount')) || 0;
            
            if (amount >= threshold) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    });
    
    // Sort breakdown table
    $('.sort-breakdown').on('click', function() {
        const sortBy = $(this).data('sort');
        const $table = $(this).closest('table');
        const $tbody = $table.find('tbody');
        const $rows = $tbody.find('tr').toArray();
        
        // Toggle sort direction
        const isAscending = $(this).hasClass('sort-asc');
        $(this).toggleClass('sort-asc sort-desc');
        
        // Sort rows
        $rows.sort(function(a, b) {
            let aVal, bVal;
            
            if (sortBy === 'amount') {
                aVal = parseFloat($(a).data('amount')) || 0;
                bVal = parseFloat($(b).data('amount')) || 0;
            } else if (sortBy === 'percentage') {
                aVal = parseFloat($(a).data('percentage')) || 0;
                bVal = parseFloat($(b).data('percentage')) || 0;
            } else {
                aVal = $(a).find('td:first').text();
                bVal = $(b).find('td:first').text();
            }
            
            if (isAscending) {
                return aVal > bVal ? 1 : -1;
            } else {
                return aVal < bVal ? 1 : -1;
            }
        });
        
        // Re-append sorted rows
        $.each($rows, function(index, row) {
            $tbody.append(row);
        });
    });
    
    // Helper functions
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    // Initialize calculations
    if ($('#total-income').length) {
        calculateSavingsRate();
    }
    
    // Download table as CSV
    $('#download-breakdown-csv').on('click', function(e) {
        e.preventDefault();
        
        const $table = $('#breakdown-table');
        let csv = [];
        
        // Headers
        const headers = [];
        $table.find('thead th').each(function() {
            headers.push($(this).text());
        });
        csv.push(headers.join(','));
        
        // Rows
        $table.find('tbody tr:visible').each(function() {
            const row = [];
            $(this).find('td').each(function() {
                row.push('"' + $(this).text().replace(/"/g, '""') + '"');
            });
            csv.push(row.join(','));
        });
        
        // Download
        const csvContent = 'data:text/csv;charset=utf-8,' + csv.join('\n');
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement('a');
        link.setAttribute('href', encodedUri);
        link.setAttribute('download', 'breakdown.csv');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });
});