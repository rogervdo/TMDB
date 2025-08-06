from odoo import models, fields, api


class TMDBCelebrity(models.Model):
    _name = "tmdb.celebrity"
    _description = "Base de Datos de Celebridades"

    name = fields.Char(string="Nombre", required=True)

    # Campos necesarios para el cálculo de fama
    movie_count = fields.Integer(
        string="Número de Películas",
        default=0,
        help="Cantidad total de películas en las que ha participado",
    )

    avg_movie_rating = fields.Float(
        string="Rating Promedio",
        default=0.0,
        help="Rating promedio de las películas en las que ha participado",
    )

    # Campo que calcula automáticamente el nivel de fama
    fame_level = fields.Selection(
        [
            ("unknown", "Desconocido"),
            ("supporting", "Actor de Reparto"),
            ("star", "Estrella"),
            ("legend", "Leyenda"),
            ("icon", "Icono"),
        ],
        string="Nivel de Fama",
        compute="_compute_fame_level",
        store=True,
    )

    # ===== CAMPOS CALCULADOS =====
    @api.depends("movie_count", "avg_movie_rating")
    def _compute_fame_level(self):
        for celebrity in self:
            if celebrity.movie_count > 80 and celebrity.avg_movie_rating > 8.5:
                celebrity.fame_level = "icon"
            elif celebrity.movie_count > 50 and celebrity.avg_movie_rating > 8:
                celebrity.fame_level = "legend"
            elif celebrity.movie_count > 20 and celebrity.avg_movie_rating > 7:
                celebrity.fame_level = "star"
            elif celebrity.movie_count > 10 and celebrity.avg_movie_rating > 6:
                celebrity.fame_level = "supporting"
            else:
                celebrity.fame_level = "unknown"
