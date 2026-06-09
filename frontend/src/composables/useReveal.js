import { onMounted, onUnmounted } from "vue";

export function useReveal() {
  let observer;

  onMounted(() => {
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
          }
        });
      },
      { threshold: 0.18 }
    );

    document.querySelectorAll("[data-reveal]").forEach((node) => observer.observe(node));
  });

  onUnmounted(() => {
    if (observer) observer.disconnect();
  });
}
