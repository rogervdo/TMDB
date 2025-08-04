from odoo import models, fields, api


class TMDBUtils(models.AbstractModel):
    _name = "tmdb.utils"
    _description = "TMDB Utils"

    @api.model
    def get_tmdb_api_key(self):
        """Get TMDB API key from configuration"""
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("custom_addon.tmdb_api_key")
        )

    @api.model
    def get_tmdb_base_url(self):
        """Get TMDB base URL from configuration"""
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("custom_addon.tmdb_base_url", "https://api.themoviedb.org/3")
        )
