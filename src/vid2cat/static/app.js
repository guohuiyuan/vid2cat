document.addEventListener("DOMContentLoaded", () => {
    const parseForm = document.getElementById("parse-form");
    const parseInput = document.getElementById("parse-text-input");
    const parseButton = document.getElementById("parse-submit-btn");
    const loadingOverlay = document.getElementById("parse-loading");
    const starRatings = document.querySelectorAll("[data-star-rating]");

    if (parseForm && parseInput && parseButton && loadingOverlay) {
        parseForm.addEventListener("submit", () => {
            const value = parseInput.value.trim();
            if (!value) return;
            parseButton.disabled = true;
            parseButton.textContent = "解析中...";
            loadingOverlay.classList.remove("hidden");
            loadingOverlay.setAttribute("aria-hidden", "false");
        });
    }

    starRatings.forEach((ratingRoot) => {
        const track = ratingRoot.querySelector("[data-star-track]");
        const hiddenInput = ratingRoot.querySelector("input[type='hidden']");
        const valueText = ratingRoot.querySelector("[data-star-value-text]");

        if (!track || !hiddenInput || !valueText) {
            return;
        }

        const stars = Array.from(track.querySelectorAll("[data-star-value]"));
        let dragging = false;

        const clampValue = (value) => Math.max(1, Math.min(10, value));

        const paint = (value) => {
            const normalized = clampValue(value);
            hiddenInput.value = String(normalized);
            valueText.textContent = `${normalized}/10`;
            track.setAttribute("aria-valuenow", String(normalized));
            stars.forEach((star, index) => {
                star.classList.toggle("active", index < normalized);
            });
        };

        const valueFromEvent = (event) => {
            const rect = track.getBoundingClientRect();
            const offset = Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
            const raw = Math.ceil((offset / rect.width) * 10);
            return clampValue(raw || 1);
        };

        paint(Number(hiddenInput.value || ratingRoot.dataset.value || 5));

        track.addEventListener("pointerdown", (event) => {
            dragging = true;
            track.setPointerCapture(event.pointerId);
            paint(valueFromEvent(event));
        });

        track.addEventListener("pointermove", (event) => {
            if (!dragging) {
                return;
            }
            paint(valueFromEvent(event));
        });

        const stopDragging = (event) => {
            if (!dragging) {
                return;
            }
            dragging = false;
            if (track.hasPointerCapture(event.pointerId)) {
                track.releasePointerCapture(event.pointerId);
            }
        };

        track.addEventListener("pointerup", stopDragging);
        track.addEventListener("pointercancel", stopDragging);

        track.addEventListener("click", (event) => {
            const target = event.target.closest("[data-star-value]");
            if (!target) {
                return;
            }
            paint(Number(target.dataset.starValue || 1));
        });

        track.addEventListener("keydown", (event) => {
            const currentValue = Number(hiddenInput.value || 5);
            if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
                event.preventDefault();
                paint(currentValue - 1);
            }
            if (event.key === "ArrowRight" || event.key === "ArrowUp") {
                event.preventDefault();
                paint(currentValue + 1);
            }
        });
    });

    window.addEventListener("pageshow", () => {
        if (parseButton) {
            parseButton.disabled = false;
            parseButton.textContent = "开始解析生成图鉴";
        }
        if (loadingOverlay) {
            loadingOverlay.classList.add("hidden");
            loadingOverlay.setAttribute("aria-hidden", "true");
        }
    });
});
