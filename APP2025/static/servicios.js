// Animación de entrada con GSAP
gsap.from(".bloque", {
  opacity: 0,
  y: 50,
  duration: 1,
  stagger: 0.3,
  ease: "power2.out"
});

gsap.from(".tarjeta", {
  opacity: 0,
  scale: 0.8,
  duration: 0.8,
  stagger: 0.2,
  ease: "back.out(1.7)"
});

// Girar tarjeta al hacer clic
document.querySelectorAll(".tarjeta").forEach(tarjeta => {
  tarjeta.addEventListener("click", () => {
    tarjeta.classList.toggle("girada");
  });
});

// Agregar a la fiesta