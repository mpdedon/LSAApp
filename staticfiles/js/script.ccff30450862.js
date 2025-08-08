// --- Navbar Scroll Effect ---
document.addEventListener('DOMContentLoaded', function() {
    const navbar = document.querySelector('.main-navbar');
    const mainContentPadding = document.querySelector('.main-content-padding'); // Get the padding div
    let navbarHeight = navbar.offsetHeight; // Get navbar height

    // Set initial padding based on navbar height
    if (mainContentPadding) {
        mainContentPadding.style.paddingTop = navbarHeight + 'px';
    }

    // Function to handle navbar style change
    const handleScroll = () => {
        // Recalculate height in case it changes (e.g., window resize)
        navbarHeight = navbar.offsetHeight;
        if (mainContentPadding) {
             mainContentPadding.style.paddingTop = navbarHeight + 'px';
        }

        if (window.scrollY > 50) { // Adjust scroll threshold (50px) as needed
            navbar.classList.add('navbar-scrolled');
            navbar.classList.remove('navbar-transparent');
            navbar.classList.remove('navbar-dark'); // Switch to light mode for text
            navbar.classList.add('navbar-light');
        } else {
            navbar.classList.remove('navbar-scrolled');
            navbar.classList.add('navbar-transparent');
            navbar.classList.remove('navbar-light'); // Switch back to dark mode for text
            navbar.classList.add('navbar-dark');
        }
    };

    // Initial check in case the page loads already scrolled
    handleScroll();

    // Add scroll event listener
    window.addEventListener('scroll', handleScroll);

    // Optional: Recalculate on resize if navbar height might change significantly
    window.addEventListener('resize', () => {
        navbarHeight = navbar.offsetHeight;
         if (mainContentPadding) {
             mainContentPadding.style.paddingTop = navbarHeight + 'px';
        }
    });
});