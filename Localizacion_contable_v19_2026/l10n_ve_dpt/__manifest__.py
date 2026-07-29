##############################################################################

{
    "name": "Localización Venezolana: Municipios y Parroquias",
    "version": "19.0",
    "author": "Ing. Darrell Sojo",
    "category": "Localization",
    "description":
        """
Localización Venezolana: Municipios y Parroquias
================================================

Basado en información del INE del año 2013, añade los campos de municipio y parroquia en el modelo `res.partner` de
manera que queden disponibles en todos los campos de dirección en modelos derivados como `res.users` o `res.company`.
     """,
	'images': ['static/description/icon.png'],
    "depends": ['base', 'base_contable'],
    "data": [
        'security/ir.model.access.csv',
        'data/res.country.state.xml',
        'data/res.country.state.municipality.xml',
        'data/res.country.state.municipality.parish.xml',
        'views/res_company_views.xml',
        'views/l10n_ve_dpt_view.xml',
        'views/res_partner.xml',
    ],
    "installable": True
}
