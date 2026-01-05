/* ========================================
   ChamaSpace Merry-Go-Round Main JavaScript
   ======================================== */

(function($) {
    'use strict';

    // CSRF Token Setup for AJAX
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

    const csrftoken = getCookie('csrftoken');

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!(/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });

    // Global Functions
    window.MGR = {
        // Show loading spinner
        showLoading: function() {
            if ($('#loading-overlay').length === 0) {
                $('body').append(`
                    <div id="loading-overlay" class="spinner-overlay">
                        <div class="spinner-border text-light" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                `);
            }
        },

        // Hide loading spinner
        hideLoading: function() {
            $('#loading-overlay').fadeOut(300, function() {
                $(this).remove();
            });
        },

        // Show toast notification
        showToast: function(message, type = 'info') {
            const toastTypes = {
                'success': 'bg-success',
                'error': 'bg-danger',
                'warning': 'bg-warning',
                'info': 'bg-info'
            };

            const toastClass = toastTypes[type] || toastTypes['info'];
            
            const toast = $(`
                <div class="toast align-items-center text-white ${toastClass} border-0" role="alert">
                    <div class="d-flex">
                        <div class="toast-body">${message}</div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>
                </div>
            `);

            if ($('#toast-container').length === 0) {
                $('body').append('<div id="toast-container" class="position-fixed top-0 end-0 p-3" style="z-index: 11"></div>');
            }

            $('#toast-container').append(toast);
            const bsToast = new bootstrap.Toast(toast[0]);
            bsToast.show();

            toast.on('hidden.bs.toast', function() {
                $(this).remove();
            });
        },

        // Format currency
        formatCurrency: function(amount) {
            return 'KES ' + parseFloat(amount).toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,');
        },

        // Format date
        formatDate: function(date) {
            const d = new Date(date);
            const options = { year: 'numeric', month: 'short', day: 'numeric' };
            return d.toLocaleDateString('en-US', options);
        },

        // Calculate time ago
        timeAgo: function(date) {
            const seconds = Math.floor((new Date() - new Date(date)) / 1000);
            
            let interval = seconds / 31536000;
            if (interval > 1) return Math.floor(interval) + " years ago";
            
            interval = seconds / 2592000;
            if (interval > 1) return Math.floor(interval) + " months ago";
            
            interval = seconds / 86400;
            if (interval > 1) return Math.floor(interval) + " days ago";
            
            interval = seconds / 3600;
            if (interval > 1) return Math.floor(interval) + " hours ago";
            
            interval = seconds / 60;
            if (interval > 1) return Math.floor(interval) + " minutes ago";
            
            return "just now";
        }
    };

    // Document Ready
    $(document).ready(function() {
        
        // Initialize tooltips
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

        // Auto-hide alerts after 5 seconds
        setTimeout(function() {
            $('.alert').fadeOut('slow', function() {
                $(this).remove();
            });
        }, 5000);

        // Mark notification as read
        $(document).on('click', '.notification-item', function() {
            const notificationId = $(this).data('notification-id');
            if (notificationId) {
                $.post(`/merry-go-round/notifications/${notificationId}/read/`)
                    .done(function() {
                        console.log('Notification marked as read');
                    });
            }
        });

        // Load user stats on dashboard
        if ($('#dashboard-stats').length > 0) {
            loadUserStats();
        }

        // Handle contribution payment
        $(document).on('click', '.pay-contribution-btn', function() {
            const contributionId = $(this).data('contribution-id');
            const amount = $(this).data('amount');
            showContributionModal(contributionId, amount);
        });

        // Handle post message
        $('#post-message-form').on('submit', function(e) {
            e.preventDefault();
            
            const formData = $(this).serialize();
            const roundId = $(this).data('round-id');
            
            MGR.showLoading();
            
            $.post(`/merry-go-round/round/${roundId}/message/`, formData)
                .done(function(response) {
                    if (response.success) {
                        MGR.showToast('Message posted successfully', 'success');
                        $('#post-message-form')[0].reset();
                        loadMessages(roundId);
                    }
                })
                .fail(function() {
                    MGR.showToast('Failed to post message', 'error');
                })
                .always(function() {
                    MGR.hideLoading();
                });
        });

        // Start round action
        $(document).on('click', '.start-round-btn', function() {
            const roundId = $(this).data('round-id');
            
            if (!confirm('Are you sure you want to start this round? This action cannot be undone.')) {
                return;
            }
            
            MGR.showLoading();
            
            $.post(`/merry-go-round/round/${roundId}/start/`)
                .done(function(response) {
                    if (response.success) {
                        MGR.showToast(response.message, 'success');
                        setTimeout(function() {
                            location.reload();
                        }, 1500);
                    }
                })
                .fail(function(xhr) {
                    const error = xhr.responseJSON?.error || 'Failed to start round';
                    MGR.showToast(error, 'error');
                })
                .always(function() {
                    MGR.hideLoading();
                });
        });

        // Filter form auto-submit on change
        $('#filter-form select').on('change', function() {
            $(this).closest('form').submit();
        });

        // Confirm actions
        $('.confirm-action').on('click', function(e) {
            if (!confirm('Are you sure you want to perform this action?')) {
                e.preventDefault();
                return false;
            }
        });

        // Copy invitation link
        $(document).on('click', '.copy-invitation-link', function() {
            const link = $(this).data('link');
            navigator.clipboard.writeText(link).then(function() {
                MGR.showToast('Invitation link copied to clipboard', 'success');
            });
        });

        // Real-time interest calculator
        $('#contribution-amount, #max-members, #frequency').on('change', function() {
            calculateProjectedInterest();
        });

    });

    // Helper Functions

    function loadUserStats() {
        $.get('/merry-go-round/api/user/stats/')
            .done(function(data) {
                $('#trust-score').text(data.trust_score);
                $('#total-contributions').text(MGR.formatCurrency(data.total_contributions));
                $('#completed-rounds').text(data.completed_rounds);
                $('#active-rounds').text(data.active_rounds);
            })
            .fail(function() {
                console.error('Failed to load user stats');
            });
    }

    function showContributionModal(contributionId, amount) {
        const modal = $(`
            <div class="modal fade" id="contributionModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Make Contribution</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <strong>Amount to Pay:</strong> ${MGR.formatCurrency(amount)}
                            </div>
                            <form id="contribution-payment-form">
                                <input type="hidden" name="contribution_id" value="${contributionId}">
                                <input type="hidden" name="amount" value="${amount}">
                                
                                <div class="mb-3">
                                    <label class="form-label">Payment Method</label>
                                    <select name="payment_method" class="form-select" required>
                                        <option value="mpesa">M-Pesa</option>
                                        <option value="bank">Bank Transfer</option>
                                    </select>
                                </div>
                                
                                <div class="mb-3 mpesa-phone-field">
                                    <label class="form-label">M-Pesa Phone Number</label>
                                    <input type="text" name="phone_number" class="form-control" 
                                           placeholder="+254700000000" required>
                                    <small class="form-text text-muted">
                                        You will receive an STK push prompt on your phone
                                    </small>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="process-payment-btn">
                                <i class="fas fa-lock"></i> Pay Now
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `);

        $('body').append(modal);
        const bsModal = new bootstrap.Modal(modal[0]);
        bsModal.show();

        modal.on('hidden.bs.modal', function() {
            $(this).remove();
        });

        // Handle payment method change
        modal.find('select[name="payment_method"]').on('change', function() {
            if ($(this).val() === 'mpesa') {
                modal.find('.mpesa-phone-field').show();
            } else {
                modal.find('.mpesa-phone-field').hide();
            }
        });

        // Handle payment processing
        modal.find('#process-payment-btn').on('click', function() {
            processContribution(contributionId, modal);
        });
    }

    function processContribution(contributionId, modal) {
        const formData = modal.find('#contribution-payment-form').serialize();
        
        MGR.showLoading();
        
        $.post(`/merry-go-round/contribution/${contributionId}/pay/`, formData)
            .done(function(response) {
                if (response.success) {
                    MGR.showToast('Payment processed successfully', 'success');
                    modal.modal('hide');
                    setTimeout(function() {
                        location.reload();
                    }, 1500);
                }
            })
            .fail(function(xhr) {
                const error = xhr.responseJSON?.error || 'Payment failed';
                MGR.showToast(error, 'error');
            })
            .always(function() {
                MGR.hideLoading();
            });
    }

    function loadMessages(roundId) {
        // Reload messages section
        $.get(`/merry-go-round/round/${roundId}/`)
            .done(function(html) {
                const messages = $(html).find('#messages-section').html();
                $('#messages-section').html(messages);
            });
    }

    function calculateProjectedInterest() {
        const contributionAmount = parseFloat($('#contribution-amount').val()) || 0;
        const maxMembers = parseInt($('#max-members').val()) || 0;
        const frequency = $('#frequency').val();
        
        if (contributionAmount > 0 && maxMembers > 0) {
            // Simple interest calculation (12% annual)
            const totalCycles = maxMembers;
            const totalContribution = contributionAmount * totalCycles;
            
            let daysPerCycle = 30; // monthly
            if (frequency === 'weekly') daysPerCycle = 7;
            if (frequency === 'biweekly') daysPerCycle = 14;
            
            const totalDays = totalCycles * daysPerCycle;
            const dailyRate = 12 / 365 / 100;
            const projectedInterest = totalContribution * dailyRate * totalDays;
            
            $('#projected-interest').text(MGR.formatCurrency(projectedInterest));
            $('#total-expected').text(MGR.formatCurrency(totalContribution + projectedInterest));
        }
    }

    // Export functions for use in templates
    window.loadUserStats = loadUserStats;
    window.showContributionModal = showContributionModal;
    window.calculateProjectedInterest = calculateProjectedInterest;

})(jQuery);