# -*- coding: utf-8 -*-
from odoo import models, fields, api


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

    @api.depends("acted_movies_ids")
    def _compute_acted_movies_count(self):
        for actor in self:
            actor.total_acted_movies = len(actor.acted_movies_ids)

    @api.depends("directed_movies_ids")
    def _compute_directed_movies_count(self):
        for director in self:
            director.total_directed_movies = len(director.directed_movies_ids)
