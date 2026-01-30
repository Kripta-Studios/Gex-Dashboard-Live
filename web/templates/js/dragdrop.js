/**
 * Drag and Drop Module
 * Chart panel drag and drop reordering with row support
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

    // Clean up empty rows
    cleanupEmptyRows();

    // Reordering logic - collect panels in order from all rows with their row indices
    const container = document.getElementById("charts-wrapper");
    const rows = container.querySelectorAll(".chart-row");

    if (document.body.classList.contains('detached-layout-mode')) {
        console.log("Reordenado en vista local");
        return;
    }

    const tab = tabs.find((t) => t.id === currentTabId);
    if (!tab) return;

    const newChartOrder = [];
    rows.forEach((row, rowIndex) => {
        const panels = row.querySelectorAll(".chart-panel");
        panels.forEach((panel) => {
            const originalIndex = parseInt(panel.dataset.index);
            if (!isNaN(originalIndex) && tab.charts[originalIndex]) {
                const chartObj = tab.charts[originalIndex];
                chartObj.rowIndex = rowIndex;  // Update the row index
                newChartOrder.push(chartObj);
            }
        });
    });
    tab.charts = newChartOrder;

    // Re-render to update indices but preserve row structure
    updateChartIndices();
}

/**
 * Update chart panel indices without re-rendering
 */
function updateChartIndices() {
    const container = document.getElementById("charts-wrapper");
    const panels = container.querySelectorAll(".chart-panel");
    panels.forEach((panel, newIndex) => {
        panel.dataset.index = newIndex;
        // Update buttons with new index
        const closeBtn = panel.querySelector('.btn-close');
        if (closeBtn) closeBtn.setAttribute('onclick', `removeChart(${newIndex})`);
        const popoutBtn = panel.querySelector('.btn-popout');
        if (popoutBtn) popoutBtn.setAttribute('onclick', `openDetachedWindow(${newIndex})`);
    });
}

/**
 * Clean up empty rows
 */
function cleanupEmptyRows() {
    const container = document.getElementById("charts-wrapper");
    const rows = container.querySelectorAll(".chart-row");
    rows.forEach(row => {
        if (row.querySelectorAll(".chart-panel").length === 0) {
            row.remove();
        }
    });
}

/**
 * Get the element after which to insert during drag within a row
 * @param {HTMLElement} row - Row element
 * @param {number} x - Mouse X position
 * @returns {HTMLElement|null} Element to insert before
 */
function getDragAfterElementInRow(row, x) {
    const draggableElements = [
        ...row.querySelectorAll(".chart-panel:not(.dragging)"),
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
 * Handle dragover on a chart row (horizontal positioning)
 */
function handleRowDragOver(e) {
    e.preventDefault();
    e.stopPropagation();

    const row = e.currentTarget;
    const draggable = document.querySelector(".dragging");

    if (!draggable) return;

    const afterElement = getDragAfterElementInRow(row, e.clientX);

    if (afterElement == null) {
        row.appendChild(draggable);
    } else {
        row.insertBefore(draggable, afterElement);
    }
}

/**
 * Handle dragover on charts wrapper (vertical positioning - between rows)
 */
function handleWrapperDragOver(e) {
    e.preventDefault();

    const container = document.getElementById("charts-wrapper");
    const draggable = document.querySelector(".dragging");

    if (!draggable) return;

    const rows = [...container.querySelectorAll(".chart-row")];
    const mouseY = e.clientY;

    // Check if we're between rows or below all rows (to create new row)
    let targetRow = null;
    let insertBefore = false;

    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const box = row.getBoundingClientRect();

        // If mouse is above the middle of first row, insert new row before
        if (i === 0 && mouseY < box.top + 30) {
            targetRow = row;
            insertBefore = true;
            break;
        }

        // If mouse is below this row's bottom edge (in the gap or below), create new row after it
        if (mouseY > box.bottom + 5) {
            // Check if there's a next row
            if (i === rows.length - 1) {
                // We're below the last row - create new row at end
                targetRow = null; // Will append at end
                insertBefore = false;
                break;
            }
            // Continue to check next row
            continue;
        }

        // Mouse is within this row's vertical bounds - let row handle horizontal
        return;
    }

    // Create new row for the dragged element
    const newRow = document.createElement("div");
    newRow.className = "chart-row";
    newRow.addEventListener("dragover", handleRowDragOver);

    // Remove draggable from its current position
    draggable.parentElement?.removeChild(draggable);
    newRow.appendChild(draggable);

    if (targetRow && insertBefore) {
        container.insertBefore(newRow, targetRow);
    } else if (targetRow) {
        container.insertBefore(newRow, targetRow.nextSibling);
    } else {
        container.appendChild(newRow);
    }

    // Clean up old empty rows
    cleanupEmptyRows();
}

// Attach wrapper dragover event when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    const wrapper = document.getElementById("charts-wrapper");
    if (wrapper) {
        wrapper.addEventListener("dragover", handleWrapperDragOver);
    }
});
