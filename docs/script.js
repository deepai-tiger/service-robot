// Loading animation
window.addEventListener('load', function() {
  document.body.classList.add('loaded');
  
  // Remove loader after animation completes
  setTimeout(function() {
    const loader = document.querySelector('.loader-wrapper');
    if (loader) loader.remove();
  }, 500);
});

// Parallax effect
document.addEventListener('DOMContentLoaded', function() {
  const parallaxWrapper = document.querySelector('.parallax-wrapper');
  
  if (parallaxWrapper) {
    window.addEventListener('scroll', function() {
      const scrollPosition = window.pageYOffset;
      parallaxWrapper.style.transform = `translateY(${scrollPosition * 0.3}px)`;
    });
  }
});


// Initialize particles.js
document.addEventListener('DOMContentLoaded', function() {
  particlesJS('particles-js', {
    "particles": {
      "number": {
        "value": 80,
        "density": {
          "enable": true,
          "value_area": 800
        }
      },
      "color": {
        "value": "#00ffc8"
      },
      "shape": {
        "type": "circle",
        "stroke": {
          "width": 0,
          "color": "#000000"
        },
        "polygon": {
          "nb_sides": 5
        }
      },
      "opacity": {
        "value": 0.5,
        "random": false,
        "anim": {
          "enable": false,
          "speed": 1,
          "opacity_min": 0.1,
          "sync": false
        }
      },
      "size": {
        "value": 3,
        "random": true,
        "anim": {
          "enable": false,
          "speed": 40,
          "size_min": 0.1,
          "sync": false
        }
      },
      "line_linked": {
        "enable": true,
        "distance": 150,
        "color": "#00a8ff",
        "opacity": 0.4,
        "width": 1
      },
      "move": {
        "enable": true,
        "speed": 2,
        "direction": "none",
        "random": false,
        "straight": false,
        "out_mode": "out",
        "bounce": false,
        "attract": {
          "enable": false,
          "rotateX": 600,
          "rotateY": 1200
        }
      }
    },
    "interactivity": {
      "detect_on": "canvas",
      "events": {
        "onhover": {
          "enable": true,
          "mode": "grab"
        },
        "onclick": {
          "enable": true,
          "mode": "push"
        },
        "resize": true
      },
      "modes": {
        "grab": {
          "distance": 140,
          "line_linked": {
            "opacity": 1
          }
        },
        "push": {
          "particles_nb": 4
        }
      }
    },
    "retina_detect": true
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const steps = document.querySelectorAll(".flow-step");
  const tooltip = document.getElementById("step-desc");

  steps.forEach((step) => {
    step.addEventListener("mouseover", () => {
      tooltip.textContent = step.getAttribute("data-desc");
    });
    step.addEventListener("mouseout", () => {
      tooltip.textContent = "Hover over a step to see more info";
    });
  });
});
