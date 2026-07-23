# License: LGPL-3
from odoo import api, fields, models
from markupsafe import Markup

MODE_SELECTION = [('wysiwyg', 'Wysiwyg'), ('html', 'Html')]

_LAYOUT_CLASSES = [
    'o_report_layout_bold',    'o_report_layout_boxed',
    'o_report_layout_bubble',  'o_report_layout_folder',
    'o_report_layout_standard','o_report_layout_striped',
    'o_report_layout_wave',
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # ── Couleurs ──────────────────────────────────────────────────────
    ilp_th_bg_color      = fields.Char(string='Fond entêtes colonnes',  default='#2c3e50')
    ilp_th_text_color    = fields.Char(string='Texte entêtes colonnes', default='#ffffff')
    ilp_title_color      = fields.Char(string='Couleur titre facture',  default='#2c3e50')
    ilp_total_bg_color   = fields.Char(string='Fond ligne total',       default='#ecf0f1')
    ilp_total_text_color = fields.Char(string='Texte ligne total',      default='#2c3e50')

    # ── Modes ─────────────────────────────────────────────────────────
    ilp_address_mode = fields.Selection(MODE_SELECTION, default='wysiwyg', string='Mode Adresse')
    ilp_tagline_mode = fields.Selection(MODE_SELECTION, default='wysiwyg', string='Mode Tagline')
    ilp_footer_mode  = fields.Selection(MODE_SELECTION, default='wysiwyg', string='Mode Footer')
    ilp_legal_mode   = fields.Selection(MODE_SELECTION, default='wysiwyg', string='Mode CGV')

    ilp_hide_page_number = fields.Boolean(
        string='Masquer numérotation de page (PDF)',
        help='Masque "Page X / Y" et le nom du document dans le footer PDF',
        default=False,
    )

    # ── HTML brut ─────────────────────────────────────────────────────
    ilp_address_html = fields.Text(string='Adresse (Html)')
    ilp_tagline_html = fields.Text(string='Tagline (Html)')
    ilp_footer_html_safe = fields.Html(
        compute='_compute_ilp_footer_html_safe', sanitize=False, store=False)

    @api.depends('ilp_footer_html')
    def _compute_ilp_footer_html_safe(self):
        from markupsafe import Markup
        for c in self:
            c.ilp_footer_html_safe = Markup(c.ilp_footer_html) if c.ilp_footer_html else Markup('')

    ilp_footer_html  = fields.Text(string='Footer (Html)')
    ilp_legal_html   = fields.Text(string='Mentions légales / CGV (Html)')
    ilp_legal_terms  = fields.Html(string='Mentions légales / CGV (Wysiwyg)',
                                   sanitize=True, sanitize_style=True, translate=True)
    ilp_custom_css   = fields.Text(string='CSS personnalisé')


    # ── Computed style strings — utilisés comme t-att-style dans les templates ──
    # Retournent la chaîne CSS complète ou '' si le champ n'est pas configuré.
    # Avantage : t-att-style="company.ilp_h2_style" → zéro guillemet dans le template.

    @api.depends('ilp_title_color')
    def _compute_ilp_h2_style(self):
        for c in self:
            c.ilp_h2_style = (
                f'color: {c.ilp_title_color} !important;'
                if c.ilp_title_color else ''
            )
    ilp_h2_style = fields.Char(compute='_compute_ilp_h2_style', store=False)

    @api.depends('ilp_total_text_color')
    def _compute_ilp_total_text_style(self):
        for c in self:
            c.ilp_total_text_style = (
                f'color: {c.ilp_total_text_color} !important;'
                if c.ilp_total_text_color else ''
            )
    ilp_total_text_style = fields.Char(compute='_compute_ilp_total_text_style', store=False)

    @api.depends('ilp_total_bg_color', 'ilp_total_text_color')
    def _compute_ilp_total_style(self):
        for c in self:
            bg   = c.ilp_total_bg_color
            text = c.ilp_total_text_color
            c.ilp_total_style = (
                f'background-color: {bg} !important; color: {text} !important; font-weight: 600;'
                if (bg or text) else ''
            )
    ilp_total_style = fields.Char(compute='_compute_ilp_total_style', store=False)

    @api.depends('ilp_th_bg_color', 'ilp_th_text_color')
    def _compute_ilp_th_style(self):
        for c in self:
            bg   = c.ilp_th_bg_color
            text = c.ilp_th_text_color
            c.ilp_th_style = (
                f'background-color: {bg} !important; color: {text} !important; font-weight: 600;'
                if (bg or text) else ''
            )
    ilp_th_style = fields.Char(compute='_compute_ilp_th_style', store=False)

    # ── CSS calculé (Markup) — injecté via t-out dans le template ─────
    # t-out à l'INTÉRIEUR d'un <style> n'est PAS évalué par QWeb 19.
    # Solution : computed field Markup + <style t-out="company.ilp_css"/>
    @api.depends(
        'ilp_th_bg_color', 'ilp_th_text_color', 'ilp_title_color',
        'ilp_total_bg_color', 'ilp_total_text_color', 'ilp_custom_css',
    )
    def _compute_ilp_css(self):
        for company in self:
            th_bg    = company.ilp_th_bg_color    or '#2c3e50'
            th_text  = company.ilp_th_text_color  or '#ffffff'
            title    = company.ilp_title_color    or '#2c3e50'
            tot_bg   = company.ilp_total_bg_color  or '#ecf0f1'
            tot_text = company.ilp_total_text_color or '#2c3e50'

            # Sélecteurs préfixés par toutes les classes de layout (spécificité maximale)
            thead_sel = ',\n'.join(
                f'.{c} table.o_main_table thead tr th,'
                f'\n.{c} table.o_main_table thead tr td'
                for c in _LAYOUT_CLASSES
            )
            h2_sel  = ',\n'.join(
                f'.{c} h2, .{c} h2 span, .{c} h2 *'
                for c in _LAYOUT_CLASSES
            )
            tot_sel = ',\n'.join(
                # .o_total_table .o_total td -> spécificité (0,3,1) = même niveau que CSS Odoo
                # tr:last-child fallback pour compatibilité
                f'.{c} .o_total_table .o_total td,\n'
                f'.{c} .o_total_table .o_total td *,\n'
                f'.{c} .o_total_table tr:last-child td'
                for c in _LAYOUT_CLASSES
            )

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
            # Retirer le border-top du footer UNIQUEMENT en PDF (wkhtmltopdf = print mode)
            # Le browser (preview) garde la ligne native Bootstrap via @media screen
            css += (
                '@media print {'
                ' .o_footer_content { border-top: none !important; border: none !important; }'
                ' }'
            )

            if company.ilp_custom_css:
                css += company.ilp_custom_css

            company.ilp_css = Markup(css)

    ilp_css = fields.Html(compute='_compute_ilp_css', sanitize=False, store=False)
