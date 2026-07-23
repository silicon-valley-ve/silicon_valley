# License: LGPL-3
from odoo import api, fields, models
from odoo.tools import is_html_empty
from markupsafe import Markup

MODE_SELECTION = [('wysiwyg', 'Wysiwyg'), ('html', 'Html')]

ILP_FIELDS = (
    'ilp_th_bg_color', 'ilp_th_text_color', 'ilp_title_color',
    'ilp_total_bg_color', 'ilp_total_text_color',
    'ilp_address_mode', 'ilp_address_html',
    'ilp_tagline_mode', 'ilp_tagline_html',
    'ilp_footer_mode',  'ilp_footer_html',
    'ilp_legal_mode',   'ilp_legal_terms', 'ilp_legal_html',
    'ilp_custom_css',
)


class BaseDocumentLayout(models.TransientModel):
    _inherit = 'base.document.layout'

    # ── Couleurs ──────────────────────────────────────────────────────
    ilp_th_bg_color      = fields.Char(default='#2c3e50')
    ilp_th_text_color    = fields.Char(default='#ffffff')
    ilp_title_color      = fields.Char(default='#2c3e50')
    ilp_total_bg_color   = fields.Char(default='#ecf0f1')
    ilp_total_text_color = fields.Char(default='#2c3e50')

    ilp_hide_page_number = fields.Boolean(string='Masquer numérotation de page (PDF)')

    # ── Modes ─────────────────────────────────────────────────────────
    ilp_address_mode = fields.Selection(MODE_SELECTION, default='wysiwyg')
    ilp_tagline_mode = fields.Selection(MODE_SELECTION, default='wysiwyg')
    ilp_footer_mode  = fields.Selection(MODE_SELECTION, default='wysiwyg')
    ilp_legal_mode   = fields.Selection(MODE_SELECTION, default='wysiwyg')

    # ── Champs Html brut ──────────────────────────────────────────────
    ilp_address_html = fields.Text(string='Adresse (Html)')
    ilp_tagline_html = fields.Text(string='Tagline (Html)')
    ilp_footer_html  = fields.Text(string='Footer (Html)')
    ilp_legal_html   = fields.Text(string='Mentions légales / CGV (Html)')

    # ── CSS custom ───────────────────────────────────────────────────────
    ilp_custom_css = fields.Text(string='CSS personnalisé')

    # ── CGV Wysiwyg ───────────────────────────────────────────────────
    ilp_legal_terms = fields.Html(
        string='Mentions légales / CGV (Wysiwyg)', sanitize=True)

    # ── Computed : surcharge des champs natifs (related=False) ────────
    # company_details ← adresse
    @api.depends('ilp_address_mode', 'ilp_address_html', 'company_id')
    def _compute_company_details(self):
        for w in self:
            if w.ilp_address_mode == 'html' and w.ilp_address_html and w.ilp_address_html.strip():
                w.company_details = Markup(w.ilp_address_html)
            else:
                w.company_details = w.company_id.company_details

    company_details = fields.Html(
        related=False, compute='_compute_company_details',
        readonly=False, store=False)

    @api.depends('company_details')
    def _compute_is_company_details_empty(self):
        for w in self:
            w.is_company_details_empty = is_html_empty(w.company_details)

    is_company_details_empty = fields.Boolean(
        related=False, compute='_compute_is_company_details_empty', store=False)

    # report_header ← tagline
    @api.depends('ilp_tagline_mode', 'ilp_tagline_html', 'company_id')
    def _compute_report_header(self):
        for w in self:
            if w.ilp_tagline_mode == 'html' and w.ilp_tagline_html and w.ilp_tagline_html.strip():
                w.report_header = Markup(w.ilp_tagline_html)
            else:
                w.report_header = w.company_id.report_header

    report_header = fields.Html(
        related=False, compute='_compute_report_header',
        readonly=False, store=False)

    # report_footer ← footer
    @api.depends('ilp_footer_mode', 'ilp_footer_html', 'company_id')
    def _compute_report_footer(self):
        for w in self:
            if w.ilp_footer_mode == 'html' and w.ilp_footer_html and w.ilp_footer_html.strip():
                w.report_footer = Markup(w.ilp_footer_html)
            else:
                w.report_footer = w.company_id.report_footer

    report_footer = fields.Html(
        related=False, compute='_compute_report_footer',
        readonly=False, store=False)



    # ── ilp_css : CSS complet pour le preview en temps réel ───────────────
    # company = wizard dans le preview → doit avoir ilp_css basé sur
    # les valeurs wizard actuelles (pas encore sauvées sur res.company).
    @api.depends(
        'ilp_th_bg_color', 'ilp_th_text_color', 'ilp_title_color',
        'ilp_total_bg_color', 'ilp_total_text_color', 'ilp_custom_css',
    )
    def _compute_ilp_css(self):
        from markupsafe import Markup
        _LAYOUT_CLASSES = [
            'o_report_layout_bold', 'o_report_layout_boxed',
            'o_report_layout_bubble', 'o_report_layout_folder',
            'o_report_layout_standard', 'o_report_layout_striped',
            'o_report_layout_wave',
        ]
        for w in self:
            th_bg    = w.ilp_th_bg_color    or '#2c3e50'
            th_text  = w.ilp_th_text_color  or '#ffffff'
            title    = w.ilp_title_color    or '#2c3e50'
            tot_bg   = w.ilp_total_bg_color  or '#ecf0f1'
            tot_text = w.ilp_total_text_color or '#2c3e50'
            thead_sel = ',\n'.join(
                f'.{c} table.o_main_table thead tr th,\n.{c} table.o_main_table thead tr td'
                for c in _LAYOUT_CLASSES
            )
            h2_sel  = ',\n'.join(
                f'.{c} h2, .{c} h2 span, .{c} h2 *' for c in _LAYOUT_CLASSES)
            tot_sel = ',\n'.join(
                f'.{c} .o_total_table .o_total td' for c in _LAYOUT_CLASSES)
            css = (
                f'{thead_sel} {{\n'
                f'    background-color: {th_bg} !important;\n'
                f'    color: {th_text} !important;\n'
                f'    font-weight: 600 !important;\n'
                f'}}\n'
                f'{h2_sel} {{\n'
                f'    color: {title} !important;\n'
                f'}}\n'
                f'{tot_sel} {{\n'
                f'    background-color: {tot_bg} !important;\n'
                f'    color: {tot_text} !important;\n'
                f'    font-weight: 600 !important;\n'
                f'}}\n'
            )
            if w.ilp_custom_css:
                css += w.ilp_custom_css
            w.ilp_css = Markup(css)

    ilp_css = fields.Html(compute='_compute_ilp_css', sanitize=False, store=False)

    # ── Computed style strings (mirror de res.company) ────────────────────
    # Dans le preview, company = wizard → doit aussi avoir ces champs.
    @api.depends('ilp_title_color')
    def _compute_ilp_h2_style(self):
        for w in self:
            w.ilp_h2_style = (
                f'color: {w.ilp_title_color} !important;'
                if w.ilp_title_color else ''
            )
    ilp_h2_style = fields.Char(compute='_compute_ilp_h2_style', store=False)

    @api.depends('ilp_total_text_color')
    def _compute_ilp_total_text_style(self):
        for w in self:
            w.ilp_total_text_style = (
                f'color: {w.ilp_total_text_color} !important;'
                if w.ilp_total_text_color else ''
            )
    ilp_total_text_style = fields.Char(compute='_compute_ilp_total_text_style', store=False)

    @api.depends('ilp_total_bg_color', 'ilp_total_text_color')
    def _compute_ilp_total_style(self):
        for w in self:
            bg, text = w.ilp_total_bg_color, w.ilp_total_text_color
            w.ilp_total_style = (
                f'background-color: {bg} !important; color: {text} !important; font-weight: 600;'
                if (bg or text) else ''
            )
    ilp_total_style = fields.Char(compute='_compute_ilp_total_style', store=False)

    @api.depends('ilp_th_bg_color', 'ilp_th_text_color')
    def _compute_ilp_th_style(self):
        for w in self:
            bg, text = w.ilp_th_bg_color, w.ilp_th_text_color
            w.ilp_th_style = (
                f'background-color: {bg} !important; color: {text} !important; font-weight: 600;'
                if (bg or text) else ''
            )
    ilp_th_style = fields.Char(compute='_compute_ilp_th_style', store=False)

    # ── Chargement depuis la société ──────────────────────────────────
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        for fname in ILP_FIELDS:
            val = getattr(company, fname, None)
            if val is not None:
                res[fname] = val
        return res

    # ── Preview temps réel ────────────────────────────────────────────
    @api.onchange(*ILP_FIELDS)
    def _onchange_ilp_preview(self):
        # Invalider les computed fields dépendants — dans le contexte onchange
        # le cache ORM peut contenir des valeurs obsolètes
        self.invalidate_recordset([
            'ilp_css', 'ilp_h2_style', 'ilp_total_style', 'ilp_th_style'
        ])
        self._compute_preview()

    # ── Sauvegarde ────────────────────────────────────────────────────
    def document_layout_save(self):
        # Normaliser secondary_color → noir car on cache les Colors natifs.
        # Cela normalise les labels "Invoice Date" / "Due Date" qui utilisent cette couleur.
        for wizard in self:
            if wizard.company_id:
                wizard.company_id.primary_color = '#000000'
                wizard.company_id.secondary_color = '#000000'

        # super() EN PREMIER : gère layout, report_header/footer/company_details natifs
        result = super().document_layout_save()

        for wizard in self:
            vals = {fname: getattr(wizard, fname, None) for fname in ILP_FIELDS}

            # En mode html : écraser le champ natif avec le HTML brut
            if wizard.ilp_address_mode == 'html' and wizard.ilp_address_html and wizard.ilp_address_html.strip():
                vals['company_details'] = Markup(wizard.ilp_address_html)
            elif wizard.ilp_address_mode == 'wysiwyg':
                # company_details déjà sauvé par super() via le champ wysiwyg
                vals.pop('company_details', None)

            if wizard.ilp_tagline_mode == 'html' and wizard.ilp_tagline_html and wizard.ilp_tagline_html.strip():
                vals['report_header'] = Markup(wizard.ilp_tagline_html)
            elif wizard.ilp_tagline_mode == 'wysiwyg':
                vals.pop('report_header', None)

            if wizard.ilp_footer_mode == 'html' and wizard.ilp_footer_html and wizard.ilp_footer_html.strip():
                vals['report_footer'] = Markup(wizard.ilp_footer_html)
            elif wizard.ilp_footer_mode == 'wysiwyg':
                vals.pop('report_footer', None)

            wizard.company_id.write(vals)

        return result
