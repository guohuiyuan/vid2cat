document.addEventListener("DOMContentLoaded", () => {
    const parseForm = document.getElementById("parse-form");
    const parseInput = document.getElementById("parse-text-input");
    const parseButton = document.getElementById("parse-submit-btn");
    const loadingOverlay = document.getElementById("parse-loading");

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
