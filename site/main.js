(() => {
  const steps = document.querySelectorAll(".steps li");
  if (!steps.length || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.style.transition = "opacity 0.5s ease, transform 0.5s ease";
          entry.target.style.opacity = "1";
          entry.target.style.transform = "translateY(0)";
          io.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.2 }
  );
  steps.forEach((el, i) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(12px)";
    el.style.transitionDelay = `${i * 80}ms`;
    io.observe(el);
  });
})();
