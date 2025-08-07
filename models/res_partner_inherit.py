# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests
import base64
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Campo que marca si la persona es director
    is_director = fields.Boolean(
        string="Es Director", default=False, help="Marca si la persona dirige películas"
    )

    # Relación inversa: todas las películas dirigidas por esa persona
    directed_movies_ids = fields.One2many(
        "tmdb.movie", "director_id", string="Películas Dirigidas"
    )

    # Campo computado: total de películas dirigidas
    total_directed_movies = fields.Integer(
        string="Total de Películas Dirigidas",
        compute="_compute_directed_movies_count",
        store=True,
    )

    is_actor = fields.Boolean(
        string="Es Actor",
        default=False,
        help="Marca si esta persona actua en peliculas",
    )

    # Relacion Many2many: todas las peliculas en donde ha actuado
    acted_movies_ids = fields.Many2many(
        "tmdb.movie",  # Modelo relacionado
        "movie_actor_rel",  # Nombre de la tabla intermedia
        "actor_id",  # Campo para este modelo
        "movie_id",  # Campo para el otro modelo
        string="Peliculas en las que ha actuado",
    )

    # Campo computado: total de peliculas donde actuo
    total_acted_movies = fields.Integer(
        string="Total de Peliculas como Actor", compute="_compute_acted_movies_count"
    )

    # TMDB profile image fields
    tmdb_profile_path = fields.Char(
        string="TMDB Profile Path",
        help="The profile path from TMDB API for the person's image",
    )

    @api.depends("acted_movies_ids")
    def _compute_acted_movies_count(self):
        for actor in self:
            actor.total_acted_movies = len(actor.acted_movies_ids)

    @api.depends("directed_movies_ids")
    def _compute_directed_movies_count(self):
        for director in self:
            director.total_directed_movies = len(director.directed_movies_ids)

    def update_image_from_tmdb_profile(self, profile_path):
        """Download and set image from TMDB profile path"""
        if not profile_path:
            return False

        try:
            # TMDB image base URL for profiles
            image_url = f"https://image.tmdb.org/t/p/w500{profile_path}"

            # Download the image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()

            # Convert to base64 for Odoo
            image_base64 = base64.b64encode(response.content).decode("utf-8")

            # Update the contact with the image
            self.write({"image_1920": image_base64, "tmdb_profile_path": profile_path})

            _logger.info(f"Successfully updated image for contact: {self.name}")
            return True

        except Exception as e:
            _logger.error(f"Error downloading TMDB image for {self.name}: {e}")
            return False

    def action_update_tmdb_image(self):
        """Action to manually update TMDB image for this contact"""
        if not self.tmdb_profile_path:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No TMDB Profile Path",
                    "message": "This contact does not have a TMDB profile path.",
                    "type": "warning",
                },
            }

        success = self.update_image_from_tmdb_profile(self.tmdb_profile_path)

        if success:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Success",
                    "message": "TMDB image has been updated successfully.",
                    "type": "success",
                },
            }
        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": "Failed to download or update the TMDB image.",
                    "type": "danger",
                },
            }
