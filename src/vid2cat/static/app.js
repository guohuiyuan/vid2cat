function prefillParse(url) {
    const input = document.getElementById("parse-url-input");
    if (!input) return;
    input.value = url;
    input.focus();
    input.scrollIntoView({ behavior: "smooth", block: "center" });
}

document.addEventListener("DOMContentLoaded", () => {
    const keywordInput = document.getElementById("keyword-input");
    const parseInput = document.getElementById("parse-url-input");
    if (!keywordInput || !parseInput) return;

    keywordInput.addEventListener("blur", () => {
        const value = keywordInput.value.trim();
        if (value.includes("douyin.com")) {
            parseInput.value = value;
        }
    });
});
