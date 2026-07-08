/** @odoo-module **/

const params = new URLSearchParams(window.location.search);

function hideOdooBranding() {
    if (params.get("ar_visiteur_popup") !== "1") {
        return;
    }
    document.documentElement.classList.add("ar_visiteur_survey_popup");
    for (const element of document.querySelectorAll("a, button, div, span")) {
        const text = (element.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
        if (text.includes("généré par") || text.includes("genere par") || text.includes("gÃ©nÃ©rÃ© par") || text.includes("powered by odoo")) {
            const container = element.closest("a, button, .card, .btn, div") || element;
            container.style.setProperty("display", "none", "important");
            container.style.setProperty("visibility", "hidden", "important");
        }
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hideOdooBranding);
} else {
    hideOdooBranding();
}

setTimeout(hideOdooBranding, 300);
setTimeout(hideOdooBranding, 1000);
