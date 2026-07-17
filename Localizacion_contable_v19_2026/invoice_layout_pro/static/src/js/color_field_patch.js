/**
 * ILP Real-time preview fix — Legacy script (pas de @odoo-module).
 *
 * Approche : intercept XHR pour pousser le nouveau preview HTML dans l'iframe
 * dès que le serveur retourne la réponse onchange base.document.layout.
 *
 * Root cause : OWL ne re-render pas l'iframe o_preview_iframe quand le champ
 * preview change via onchange. On bypass OWL et on met à jour srcdoc directement.
 */
(function () {
    'use strict';

    const _origOpen = XMLHttpRequest.prototype.open;
    const _origSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function (method, url) {
        this.__ilpUrl = url || '';
        return _origOpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function (body) {
        const url = this.__ilpUrl || '';
        if (url.indexOf('call_kw') !== -1 &&
            typeof body === 'string' &&
            body.indexOf('base.document.layout') !== -1) {

            this.addEventListener('load', function () {
                try {
                    var resp = JSON.parse(this.responseText);
                    var newPreview = resp && resp.result && resp.result.value && resp.result.value.preview;
                    if (newPreview) {
                        var iframe = document.querySelector('.o_preview_iframe');
                        if (iframe) {
                            iframe.srcdoc = newPreview;
                        }
                    }
                } catch (e) { /* ignore */ }
            });
        }
        return _origSend.apply(this, arguments);
    };

    console.log('[ILP] XHR preview patch actif');
})();
