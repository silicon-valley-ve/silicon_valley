from . import models


def post_init_hook(env):
    """Initialize ILP color defaults for existing companies (new companies get defaults from field definition)."""
    DEFAULTS = {
        'ilp_th_bg_color':      '#2c3e50',
        'ilp_th_text_color':    '#ffffff',
        'ilp_title_color':      '#2c3e50',
        'ilp_total_bg_color':   '#ecf0f1',
        'ilp_total_text_color': '#2c3e50',
    }
    for company in env['res.company'].search([]):
        vals = {k: v for k, v in DEFAULTS.items() if not getattr(company, k)}
        if vals:
            company.write(vals)
