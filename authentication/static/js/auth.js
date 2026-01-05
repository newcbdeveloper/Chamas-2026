document.addEventListener('DOMContentLoaded', function() {
    // Determine which page we're on
    const isLoginPage = document.getElementById('loginForm') !== null;
    const isSignupPage = document.getElementById('signupForm1') !== null;
    
    // Menu button functionality
    const menuButton = document.querySelector('.menu-button');
    if (menuButton) {
        menuButton.addEventListener('click', function() {
            alert('Menu clicked! This would open a navigation menu in a real app.');
        });
    }
    
    // Login page functionality
    if (isLoginPage) {
        setupLoginPage();
    }
    
    // Signup page functionality
    if (isSignupPage) {
        setupSignupPage();
    }
    
    // Login page setup
    function setupLoginPage() {
        const loginForm = document.getElementById('loginForm');
        const loginBtn = document.getElementById('loginBtn');
        const getCodeBtn = document.getElementById('getCodeBtn');
        const emailInput = document.getElementById('email');
        
        // Get Code button functionality
        getCodeBtn.addEventListener('click', function() {
            if (!emailInput.value) {
                alert('Please enter your email or phone number');
                return;
            }
            
            // In a real app, you would send a request to your backend to send a security code
            alert(`Security code would be sent to ${emailInput.value} in a real application`);
        });
        
        // Login form submission
        loginForm.addEventListener('submit', function(event) {
            event.preventDefault();
            
            // Get form values
            const email = emailInput.value;
            const password = document.getElementById('password').value;
            const securityCode = document.getElementById('securityCode').value;
            
            // Basic validation
            if (!email || !password || !securityCode) {
                alert('Please fill in all fields');
                return;
            }
            
            // Show loading state
            const originalText = loginBtn.textContent;
            loginBtn.textContent = 'Logging in...';
            loginBtn.disabled = true;
            
            // Simulate API call with timeout
            setTimeout(function() {
                // Reset button state
                loginBtn.textContent = originalText;
                loginBtn.disabled = false;
                
                // In a real app, you would validate credentials and redirect on success
                alert('Login successful! (This is just a demo)');
            }, 1500);
        });
    }
    
    // Generate date options for date of birth dropdown
    function populateDateOptions() {
        const dobSelect = document.getElementById('dob');
        if (!dobSelect) return;
        
        const currentYear = new Date().getFullYear();
        
        // Add a placeholder option
        const placeholderOption = document.createElement('option');
        placeholderOption.value = '';
        placeholderOption.textContent = '18/06/2023';
        placeholderOption.disabled = true;
        placeholderOption.selected = true;
        dobSelect.appendChild(placeholderOption);
        
        // In a real app, you would generate proper date options
        // This is just a simplified example
        for (let year = currentYear; year >= currentYear - 100; year--) {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = `01/01/${year}`;
            dobSelect.appendChild(option);
        }
    }
});