/**
 * Drag and Drop Module
 * Chart panel drag and drop reordering
 */

/**
 * Handle drag start on chart panel
 */
function handleDragStart(e) {
    e.dataTransfer.effectAllowed = "move";
    this.classList.add("dragging");
}

/**
 * Handle drag end on chart panel
 */
function handleDragEnd(e) {
    this.classList.remove("dragging");

    const isDetached = document.body.classList.contains('detached-mode') ||
        document.body.classList.contains('detached-layout-mode');

    if (!isDetached) {
        // Check if dragged outside window
        const mouseX = e.screenX;
        const mouseY = e.screenY;
        const margin = 50;
        if (mouseX < window.screenX - margin || mouseX > (window.screenX + window.outerWidth) + margin) {
            const index = parseInt(this.dataset.index);
            const tab = tabs.find((t) => t.id === currentTabId);
            if (tab && tab.charts[index]) openDetachedWindow(index);
            return;
        }
    }

    // Reordering logic
    const container = document.getElementById("charts-wrapper");
    const panels = container.querySelectorAll(".chart-panel");

    if (document.body.classList.contains('detached-layout-mode')) {
        console.log("Reordenado en vista local");
        return;
    }

    const tab = tabs.find((t) => t.id === currentTabId);
    if (!tab) return;
    const newChartOrder = [];
    panels.forEach((panel) => {
        const originalIndex = parseInt(panel.dataset.index);
        if (!isNaN(originalIndex) && tab.charts[originalIndex])
            newChartOrder.push(tab.charts[originalIndex]);
    });
    tab.charts = newChartOrder;
    renderAllCharts();
}

/**
 * Get the element after which to insert during drag
 * @param {HTMLElement} container - Container element
 * @param {number} x - Mouse X position
 * @returns {HTMLElement|null} Element to insert before
 */
function getDragAfterElement(container, x) {
    const draggableElements = [
        ...container.querySelectorAll(".chart-panel:not(.dragging)"),
    ];

    return draggableElements.reduce(
        (closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = x - box.left - box.width / 2;

            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        },
        { offset: Number.NEGATIVE_INFINITY }
    ).element;
}

/**
 * Handle dragover on charts wrapper
 */
function handleWrapperDragOver(e) {
    e.preventDefault();
    const container = document.getElementById("charts-wrapper");
    const afterElement = getDragAfterElement(container, e.clientX);
    const draggable = document.querySelector(".dragging");
    if (draggable) {
        if (afterElement == null) container.appendChild(draggable);
        else container.insertBefore(draggable, afterElement);
    }
}

// Attach wrapper dragover event when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    const wrapper = document.getElementById("charts-wrapper");
    if (wrapper) {
        wrapper.addEventListener("dragover", handleWrapperDragOver);
    }
});
