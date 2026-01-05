// Transactions JavaScript
$(document).ready(function() {
    
    // Get transaction type (from select or hidden input)
    function getTransactionType() {
        const typeSelect = $('#transaction-type');
        if (typeSelect.length) {
            return typeSelect.val();
        }
        const typeHidden = $('input[name="type"]');
        if (typeHidden.length) {
            return typeHidden.val();
        }
        return null;
    }
    
    // Filter categories based on transaction type
    $('#transaction-type').on('change', function() {
        const transactionType = $(this).val();
        filterCategoriesByType(transactionType);
    });
    
    // Filter categories
    function filterCategoriesByType(type) {
        if (!type) return;
        
        const $categorySelect = $('#transaction-category');
        
        // Make AJAX call to get filtered categories
        $.ajax({
            url: '/expense-tracker/api/categories/',
            data: { type: type },
            success: function(data) {
                // Clear existing options except placeholder
                $categorySelect.find('option:not(:first)').remove();
                
                // Add filtered categories
                data.categories.forEach(function(category) {
                    $categorySelect.append(
                        $('<option></option>')
                            .attr('value', category.id)
                            .text(category.name)
                            .prepend(category.icon + ' ')
                    );
                });
            },
            error: function() {
                console.error('Error loading categories');
            }
        });
    }
    
    // Form validation
    $('#transaction-form').on('submit', function(e) {
        let isValid = true;
        $('.is-invalid').removeClass('is-invalid');
        
        // Validate amount
        const amount = parseFloat($('#id_amount').val());
        if (isNaN(amount) || amount <= 0) {
            $('#id_amount').addClass('is-invalid');
            isValid = false;
        }
        
        // Validate category
        if (!$('#transaction-category').val()) {
            $('#transaction-category').addClass('is-invalid');
            isValid = false;
        }
        
        // Validate date
        if (!$('#id_date').val()) {
            $('#id_date').addClass('is-invalid');
            isValid = false;
        }
        
        if (!isValid) {
            e.preventDefault();
            showAlert('Please fill in all required fields correctly', 'danger');
        }
    });
    
    // Auto-calculate and display amount in real-time
    $('#id_amount').on('input', function() {
        const amount = parseFloat($(this).val());
        if (!isNaN(amount) && amount > 0) {
            const formatted = amount.toLocaleString('en-KE', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            $('#amount-preview').text('KSh ' + formatted);
        } else {
            $('#amount-preview').text('KSh 0.00');
        }
    });
    
    // Set current time by default
    if ($('#id_time').val() === '') {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        $('#id_time').val(`${hours}:${minutes}`);
    }
    
    // Set today's date by default
    if ($('#id_date').val() === '') {
        const today = new Date().toISOString().split('T')[0];
        $('#id_date').val(today);
    }
    
    // Quick category selection
    $('.category-quick-select').on('click', function() {
        const categoryId = $(this).data('category-id');
        $('#transaction-category').val(categoryId);
        $('.category-quick-select').removeClass('active');
        $(this).addClass('active');
    });
    
    // Show/hide recurring options
    $('#id_is_recurring').on('change', function() {
        if ($(this).is(':checked')) {
            $('#recurring-options').slideDown();
        } else {
            $('#recurring-options').slideUp();
        }
    });
    
    // Delete transaction confirmation
    $('.btn-delete-transaction').on('click', function(e) {
        if (!confirm('Are you sure you want to delete this transaction?')) {
            e.preventDefault();
        }
    });
    
    // Bulk actions
    let selectedTransactions = [];
    
    $('.transaction-checkbox').on('change', function() {
        const transactionId = $(this).val();
        if ($(this).is(':checked')) {
            selectedTransactions.push(transactionId);
        } else {
            selectedTransactions = selectedTransactions.filter(id => id !== transactionId);
        }
        updateBulkActionsVisibility();
    });
    
    function updateBulkActionsVisibility() {
        if (selectedTransactions.length > 0) {
            $('#bulk-actions').slideDown();
            $('#selected-count').text(selectedTransactions.length);
        } else {
            $('#bulk-actions').slideUp();
        }
    }
    
    // Bulk delete
    $('#bulk-delete').on('click', function() {
        if (confirm(`Are you sure you want to delete ${selectedTransactions.length} transaction(s)?`)) {
            // Implement bulk delete logic
            bulkDeleteTransactions(selectedTransactions);
        }
    });
    
    function bulkDeleteTransactions(ids) {
        $.ajax({
            url: '/expense-tracker/transactions/bulk-delete/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            data: JSON.stringify({ ids: ids }),
            contentType: 'application/json',
            success: function(response) {
                showAlert('Transactions deleted successfully', 'success');
                location.reload();
            },
            error: function(xhr, status, error) {
                showAlert('Error deleting transactions', 'danger');
                console.error('Error:', error);
            }
        });
    }
    
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
    
    function showAlert(message, type) {
        const alert = $(`
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `);
        
        $('.container').prepend(alert);
        
        setTimeout(function() {
            alert.fadeOut(300, function() {
                $(this).remove();
            });
        }, 5000);
    }
    
    // Initialize on page load
    if ($('#transaction-type').length) {
        const initialType = $('#transaction-type').val();
        if (initialType) {
            filterCategoriesByType(initialType);
        }
    }
});