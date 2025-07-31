from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    tmdb_api_key = fields.Char(
        string="TMDB API Key",
        config_parameter="custom_addon.tmdb_api_key",
        help="Enter your TMDB API key here",
    )

    # You can add more configuration fields here
    tmdb_base_url = fields.Char(
        string="TMDB Base URL",
        config_parameter="custom_addon.tmdb_base_url",
        default="https://api.themoviedb.org/3",
        help="TMDB API base URL",
    )
