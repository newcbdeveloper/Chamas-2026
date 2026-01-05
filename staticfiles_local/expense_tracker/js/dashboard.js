// Dashboard JavaScript
$(document).ready(function() {
    
    // Auto-refresh data every 30 seconds
    let autoRefreshInterval;
    
    function startAutoRefresh() {
        autoRefreshInterval = setInterval(function() {
            loadDashboardData();
        }, 30000); // 30 seconds
    }
    
    function stopAutoRefresh() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
        }
    }
    
    // Load dashboard data via AJAX
    function loadDashboardData() {
        const selectedDate = $('#date-picker').val();
        
        $.ajax({
            url: '/expense-tracker/api/summary/',
            data: {
                date: selectedDate
            },
            success: function(data) {
                updateSummaryCards(data);
            },
            error: function(xhr, status, error) {
                console.error('Error loading dashboard data:', error);
            }
        });
    }
    
    // Update summary cards
    function updateSummaryCards(data) {
        $('.income-card .card-value').text('KSh ' + formatCurrency(data.income));
        $('.expense-card .card-value').text('KSh ' + formatCurrency(data.expenses));
        $('.balance-card .card-value').text('KSh ' + formatCurrency(data.balance));
        
        // Update balance card styling
        if (data.balance < 0) {
            $('.balance-card').addClass('negative');
        } else {
            $('.balance-card').removeClass('negative');
        }
    }
    
    // Format currency
    function formatCurrency(amount) {
        return parseFloat(amount).toLocaleString('en-KE', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }
    
    // Delete transaction handler
    $('.delete-transaction').on('click', function(e) {
        const transactionId = $(this).data('transaction-id');
        const $card = $(this).closest('.transaction-card');
        
        // The modal will handle the actual deletion
        // This is just for visual feedback
        $('#deleteModal' + transactionId).on('hidden.bs.modal', function() {
            if ($(this).data('deleted')) {
                $card.fadeOut(300, function() {
                    $(this).remove();
                    loadDashboardData(); // Refresh summary
                });
            }
        });
    });
    
    // Date picker change handler
    $('#date-picker').on('change', function() {
        const selectedDate = $(this).val();
        window.location.href = '?date=' + selectedDate;
    });
    
    // Quick add transaction (if implementing AJAX form)
    $('#quick-add-form').on('submit', function(e) {
        e.preventDefault();
        
        const formData = {
            type: $('#quick-type').val(),
            category_id: $('#quick-category').val(),
            amount: $('#quick-amount').val(),
            description: $('#quick-description').val(),
            date: $('#date-picker').val(),
            time: new Date().toTimeString().slice(0, 5)
        };
        
        $.ajax({
            url: '/expense-tracker/transactions/quick-add/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.success) {
                    // Show success message
                    showToast('Transaction added successfully!', 'success');
                    
                    // Reset form
                    $('#quick-add-form')[0].reset();
                    
                    // Reload transactions list
                    location.reload();
                }
            },
            error: function(xhr, status, error) {
                showToast('Error adding transaction', 'danger');
                console.error('Error:', error);
            }
        });
    });
    
    // Get CSRF token
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
    
    // Show toast notification
    function showToast(message, type = 'info') {
        const toast = $('<div>')
            .addClass('toast align-items-center text-white bg-' + type + ' border-0')
            .attr('role', 'alert')
            .attr('aria-live', 'assertive')
            .attr('aria-atomic', 'true')
            .html(`
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            `);
        
        $('.toast-container').append(toast);
        const bsToast = new bootstrap.Toast(toast[0]);
        bsToast.show();
        
        // Remove toast after it's hidden
        toast.on('hidden.bs.toast', function() {
            $(this).remove();
        });
    }
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Start auto-refresh if enabled
    if (localStorage.getItem('autoRefresh') === 'true') {
        startAutoRefresh();
    }
    
    // Toggle auto-refresh
    $('#toggle-auto-refresh').on('change', function() {
        if ($(this).is(':checked')) {
            localStorage.setItem('autoRefresh', 'true');
            startAutoRefresh();
        } else {
            localStorage.setItem('autoRefresh', 'false');
            stopAutoRefresh();
        }
    });
    
    // Keyboard shortcuts
    $(document).on('keydown', function(e) {
        // Ctrl/Cmd + N: New transaction
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            window.location.href = '/expense-tracker/transactions/create/';
        }
        
        // Ctrl/Cmd + Left Arrow: Previous day
        if ((e.ctrlKey || e.metaKey) && e.key === 'ArrowLeft') {
            e.preventDefault();
            const currentDate = new Date($('#date-picker').val());
            currentDate.setDate(currentDate.getDate() - 1);
            const newDate = currentDate.toISOString().split('T')[0];
            window.location.href = '?date=' + newDate;
        }
        
        // Ctrl/Cmd + Right Arrow: Next day
        if ((e.ctrlKey || e.metaKey) && e.key === 'ArrowRight') {
            e.preventDefault();
            const currentDate = new Date($('#date-picker').val());
            currentDate.setDate(currentDate.getDate() + 1);
            const newDate = currentDate.toISOString().split('T')[0];
            window.location.href = '?date=' + newDate;
        }
    });
    
    // Smooth scroll for navigation
    $('a[href^="#"]').on('click', function(e) {
        const target = $(this.getAttribute('href'));
        if (target.length) {
            e.preventDefault();
            $('html, body').stop().animate({
                scrollTop: target.offset().top - 80
            }, 500);
        }
    });
    
});