(function () {
    function visibleModal(modals) {
        return (modals || [])
            .find(modal => modal && !modal.classList.contains('hidden')) || null;
    }

    function closeVisibleModal(modal, modalClosers) {
        const matchedCloser = (modalClosers || []).find(item => item.modal === modal);
        if (!matchedCloser || typeof matchedCloser.close !== 'function') return false;

        matchedCloser.close();
        return true;
    }

    function focusableElementsIn(modal) {
        if (!modal || typeof modal.querySelectorAll !== 'function') return [];

        return Array.from(modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )).filter(element => !element.disabled && element.getClientRects().length > 0);
    }

    function trapModalFocus(event, modal, documentRef = document) {
        if (event.key !== 'Tab') return false;

        const focusable = focusableElementsIn(modal);
        if (focusable.length === 0) {
            event.preventDefault();
            modal.focus();
            return true;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && documentRef.activeElement === first) {
            event.preventDefault();
            last.focus();
            return true;
        }
        if (!event.shiftKey && documentRef.activeElement === last) {
            event.preventDefault();
            first.focus();
            return true;
        }
        return false;
    }

    window.SAM2ModalKeyboardController = {
        visibleModal,
        closeVisibleModal,
        focusableElementsIn,
        trapModalFocus
    };
})();
