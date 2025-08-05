from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class TMDBSearchResult(models.TransientModel):
    _name = "tmdb.search.result"
    _description = "TMDB Search Results"
    _order = "popularity desc, vote_average desc"

    # Datos básicos de la película
    tmdb_id = fields.Integer(string="TMDB ID", required=True)
    title = fields.Char(string="Title", required=True)
    original_title = fields.Char(string="Original Title")
    overview = fields.Text(string="Overview")

    # Fechas
    release_date = fields.Date(string="Release Date")
    year = fields.Char(string="Year", compute="_compute_year", store=True)

    # Ratings y popularidad
    vote_average = fields.Float(string="Rating", digits=(3, 1))
    vote_count = fields.Integer(string="Vote Count")
    popularity = fields.Float(string="Popularity", digits=(8, 1))

    # Estados y flags
    exists_in_local = fields.Boolean(
        string="Exists in Local DB",
        compute="_compute_exists_in_local",
        search="_search_exists_in_local",
        store=False,
    )
    status_display = fields.Char(string="Status", compute="_compute_status_display")

    # Datos adicionales para sincronización
    poster_path = fields.Char(string="Poster Path")
    backdrop_path = fields.Char(string="Backdrop Path")
    genre_names = fields.Char(string="Genres", compute="_compute_genre_names")

    # Referencia al wizard que creó estos resultados
    wizard_id = fields.Many2one("tmdb.movie.search.wizard", string="Search Wizard")

    @api.depends("release_date")
    def _compute_year(self):
        """Calcula el año desde la fecha de lanzamiento"""
        for record in self:
            if record.release_date:
                record.year = str(record.release_date.year)
            else:
                record.year = "N/A"

    @api.depends("tmdb_id")
    def _compute_exists_in_local(self):
        """Verifica si la película ya existe en la base de datos local"""
        for record in self:
            existing = self.env["tmdb.movie"].search_count(
                [("tmdb_id", "=", record.tmdb_id)]
            )
            record.exists_in_local = bool(existing)

    def _search_exists_in_local(self, operator, value):
        """Método de búsqueda para el campo exists_in_local"""
        # Obtener todos los tmdb_ids que existen en la BD local
        existing_tmdb_ids = self.env["tmdb.movie"].search([]).mapped("tmdb_id")

        if operator == "=" and value:
            # Buscar registros que SÍ existen en local
            return [("tmdb_id", "in", existing_tmdb_ids)]
        elif operator == "=" and not value:
            # Buscar registros que NO existen en local
            return [("tmdb_id", "not in", existing_tmdb_ids)]
        elif operator == "!=" and value:
            # Buscar registros que NO existen en local
            return [("tmdb_id", "not in", existing_tmdb_ids)]
        elif operator == "!=" and not value:
            # Buscar registros que SÍ existen en local
            return [("tmdb_id", "in", existing_tmdb_ids)]
        else:
            # Para otros operadores, retornar dominio vacío
            return []

    @api.depends("exists_in_local")
    def _compute_status_display(self):
        """Calcula el estado para mostrar"""
        for record in self:
            if record.exists_in_local:
                record.status_display = "✅ En BD Local"
            else:
                record.status_display = "📥 Solo TMDB"

    def _compute_genre_names(self):
        """Obtiene los nombres de géneros (placeholder por ahora)"""
        for record in self:
            # Por ahora dejamos vacío, se puede implementar después
            record.genre_names = ""

    def action_sync_movie(self):
        """Sincroniza una película específica desde TMDB"""
        self.ensure_one()

        if self.exists_in_local:
            # Actualizar película existente
            existing_movie = self.env["tmdb.movie"].search(
                [("tmdb_id", "=", self.tmdb_id)]
            )
            if existing_movie:
                updated = existing_movie.sync_from_tmdb()
                if updated:
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": "Película Actualizada",
                            "message": f'Película "{self.title}" actualizada desde TMDB.',
                            "type": "success",
                        },
                    }
        else:
            # Sincronizar nueva película
            movie_model = self.env["tmdb.movie"]
            new_movie = movie_model.sync_movie_from_tmdb(self.tmdb_id)

            if new_movie:
                # El estado se actualizará automáticamente por el campo computado
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "Película Sincronizada",
                        "message": f'Película "{self.title}" sincronizada desde TMDB.',
                        "type": "success",
                    },
                }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Error",
                "message": "No se pudo sincronizar la película.",
                "type": "danger",
            },
        }

    def action_view_movie(self):
        """Abre la película en la BD local si existe"""
        self.ensure_one()

        if not self.exists_in_local:
            raise UserError(
                "Esta película no existe en la base de datos local. Sincronízala primero."
            )

        existing_movie = self.env["tmdb.movie"].search([("tmdb_id", "=", self.tmdb_id)])

        if existing_movie:
            return {
                "type": "ir.actions.act_window",
                "res_model": "tmdb.movie",
                "res_id": existing_movie.id,
                "view_mode": "form",
                "target": "current",
            }

    @api.model
    def create_from_tmdb_data(self, movies_data, wizard_id=None):
        """Crea registros transient desde datos de TMDB"""
        result_ids = []

        for movie_data in movies_data:
            # Convertir fecha si existe
            release_date = None
            if movie_data.get("release_date"):
                try:
                    from datetime import datetime

                    release_date = datetime.strptime(
                        movie_data["release_date"], "%Y-%m-%d"
                    ).date()
                except ValueError:
                    release_date = None

            # Crear registro transient
            result = self.create(
                {
                    "tmdb_id": movie_data.get("id"),
                    "title": movie_data.get("title", "Unknown"),
                    "original_title": movie_data.get("original_title", ""),
                    "overview": movie_data.get("overview", "")[:500] + "..."
                    if movie_data.get("overview", "")
                    else "",
                    "release_date": release_date,
                    "vote_average": movie_data.get("vote_average", 0.0),
                    "vote_count": movie_data.get("vote_count", 0),
                    "popularity": movie_data.get("popularity", 0.0),
                    "poster_path": movie_data.get("poster_path", ""),
                    "backdrop_path": movie_data.get("backdrop_path", ""),
                    "wizard_id": wizard_id,
                }
            )

            result_ids.append(result.id)

        return result_ids

    def action_sync_all_new_movies(self):
        """Sincroniza todas las películas nuevas (que no están en BD local)"""
        movies_to_sync = self.filtered(lambda r: not r.exists_in_local)

        if not movies_to_sync:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "✅ Todo Sincronizado",
                    "message": "Todas las películas de los resultados ya están en tu base de datos local.",
                    "type": "info",
                },
            }

        total_to_sync = len(movies_to_sync)
        synced_count = 0
        error_count = 0
        movie_model = self.env["tmdb.movie"]

        # Logging para seguimiento
        _logger.info(
            f"Starting sync of {total_to_sync} new movies from TMDB search results"
        )

        for result in movies_to_sync:
            try:
                if movie_model.sync_movie_from_tmdb(result.tmdb_id):
                    synced_count += 1
                else:
                    error_count += 1
            except Exception as e:
                _logger.error(f"Error syncing movie {result.tmdb_id}: {str(e)}")
                error_count += 1

        # Los estados se actualizarán automáticamente por el campo computado

        # Preparar mensaje de resultado
        if synced_count == total_to_sync:
            notification_type = "success"
            title = "🎉 ¡Sincronización Exitosa!"
            message = (
                f"Se sincronizaron correctamente las {synced_count} películas nuevas."
            )
        elif synced_count > 0:
            notification_type = "warning"
            title = "⚠️ Sincronización Parcial"
            message = f"Se sincronizaron {synced_count} de {total_to_sync} películas. {error_count} fallaron."
        else:
            notification_type = "danger"
            title = "❌ Error en Sincronización"
            message = f"No se pudo sincronizar ninguna película. {error_count} errores."

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": True,  # Hacer la notificación más visible
            },
        }

    def action_sync_all_visible(self):
        """Sincroniza todas las películas visibles en la vista actual"""
        movies_to_sync = self.filtered(lambda r: not r.exists_in_local)

        if not movies_to_sync:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Info",
                    "message": "Todas las películas ya están sincronizadas.",
                    "type": "info",
                },
            }

        synced_count = 0
        movie_model = self.env["tmdb.movie"]

        for result in movies_to_sync:
            if movie_model.sync_movie_from_tmdb(result.tmdb_id):
                synced_count += 1

        # Los estados se actualizarán automáticamente por el campo computado

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Sincronización Completa",
                "message": f"Se sincronizaron {synced_count} películas de {len(movies_to_sync)} seleccionadas.",
                "type": "success",
            },
        }
