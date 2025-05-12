// Initialize Feather icons
document.addEventListener('DOMContentLoaded', function() {
  // Initialize feather icons
  if (typeof feather !== 'undefined') {
    feather.replace();
  }
  
  // Activate tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });
  
  // Add active class to current nav item
  const currentLocation = window.location.pathname;
  const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
  
  navLinks.forEach(link => {
    if (link.getAttribute('href') === currentLocation) {
      link.classList.add('active');
    }
  });
  
  // Code highlighting for code snippets
  const codeBlocks = document.querySelectorAll('.code-snippet pre code');
  if (codeBlocks.length > 0 && typeof hljs !== 'undefined') {
    codeBlocks.forEach(block => {
      hljs.highlightElement(block);
    });
  }
  
  // Handle environment checklist items
  const checkItems = document.querySelectorAll('.form-check-input');
  checkItems.forEach(item => {
    item.addEventListener('change', function() {
      // Save checkbox state to localStorage
      localStorage.setItem(this.id, this.checked);
    });
    
    // Restore checkbox state from localStorage
    const savedState = localStorage.getItem(item.id);
    if (savedState === 'true') {
      item.checked = true;
    }
  });
  
  // Animate cards on scroll
  const animateOnScroll = function() {
    const cards = document.querySelectorAll('.card');
    
    cards.forEach(card => {
      const cardPosition = card.getBoundingClientRect().top;
      const screenPosition = window.innerHeight / 1.3;
      
      if (cardPosition < screenPosition) {
        card.classList.add('animated');
      }
    });
  };
  
  // Run on load
  animateOnScroll();
  
  // Run on scroll
  window.addEventListener('scroll', animateOnScroll);
  
  // Handle tab navigation with URL hash
  const handleHashChange = function() {
    const hash = window.location.hash;
    if (hash) {
      const tab = document.querySelector(`[data-bs-target="${hash}"]`);
      if (tab) {
        new bootstrap.Tab(tab).show();
      }
    }
  };
  
  // Run on load
  handleHashChange();
  
  // Run on hash change
  window.addEventListener('hashchange', handleHashChange);
  
  // Copy code button functionality
  document.querySelectorAll('.code-snippet').forEach(snippet => {
    // Create copy button
    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn btn-sm btn-outline-secondary copy-btn';
    copyBtn.innerHTML = '<i data-feather="clipboard"></i> Copy';
    copyBtn.style.position = 'absolute';
    copyBtn.style.top = '0.5rem';
    copyBtn.style.right = '0.5rem';
    
    // Make the snippet container position relative for absolute positioning
    snippet.style.position = 'relative';
    
    // Add button to snippet
    snippet.prepend(copyBtn);
    
    // Initialize feather icon
    if (typeof feather !== 'undefined') {
      feather.replace();
    }
    
    // Add click handler
    copyBtn.addEventListener('click', function() {
      const code = snippet.querySelector('code').innerText;
      navigator.clipboard.writeText(code).then(() => {
        copyBtn.innerHTML = '<i data-feather="check"></i> Copied!';
        if (typeof feather !== 'undefined') {
          feather.replace();
        }
        setTimeout(() => {
          copyBtn.innerHTML = '<i data-feather="clipboard"></i> Copy';
          if (typeof feather !== 'undefined') {
            feather.replace();
          }
        }, 2000);
      });
    });
  });
});
