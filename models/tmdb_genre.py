from odoo import models, fields, api
from odoo.exceptions import ValidationError
import requests
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TMDBGenre(models.Model):
    _name = "tmdb.genre"
    _description = "TMDB Genre"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    tmdb_genre_id = fields.Integer(string="TMDB Genre ID", required=True, unique=True)
    description = fields.Text(string="Description")

    # Many2many
    movie_ids = fields.Many2many(
        "tmdb.movie",
        string="Movies",
        help="Movies that belong to this genre",
    )

    # Computed fields for statistics
    movie_count = fields.Integer(
        string="Movie Count",
        compute="_compute_genre_statistics",
        store=True,
    )

    avg_rating = fields.Float(
        string="Average Rating",
        compute="_compute_genre_statistics",
        store=True,
        digits=(3, 2),
    )

    total_popularity = fields.Float(
        string="Total Popularity",
        compute="_compute_genre_statistics",
        store=True,
    )

    recent_movies_count = fields.Integer(
        string="Recent Movies (2020+)",
        compute="_compute_genre_statistics",
        store=True,
    )

    classic_movies_count = fields.Integer(
        string="Classic Movies (pre-2000)",
        compute="_compute_genre_statistics",
        store=True,
    )

    high_rated_count = fields.Integer(
        string="High Rated (8+)",
        compute="_compute_genre_statistics",
        store=True,
    )

    medium_rated_count = fields.Integer(
        string="Medium Rated (5-8)",
        compute="_compute_genre_statistics",
        store=True,
    )

    low_rated_count = fields.Integer(
        string="Low Rated (<5)",
        compute="_compute_genre_statistics",
        store=True,
    )

    viral_movies_count = fields.Integer(
        string="Viral Movies (500+)",
        compute="_compute_genre_statistics",
        store=True,
    )

    high_popularity_count = fields.Integer(
        string="High Popularity (250-500)",
        compute="_compute_genre_statistics",
        store=True,
    )

    medium_popularity_count = fields.Integer(
        string="Medium Popularity (150-250)",
        compute="_compute_genre_statistics",
        store=True,
    )

    low_popularity_count = fields.Integer(
        string="Low Popularity (<150)",
        compute="_compute_genre_statistics",
        store=True,
    )

    @api.depends(
        "movie_ids",
        "movie_ids.vote_average",
        "movie_ids.popularity",
        "movie_ids.release_date",
    )
    def _compute_genre_statistics(self):
        """Compute various statistics for the genre"""
        for genre in self:
            movies = genre.movie_ids

            # Basic counts
            genre.movie_count = len(movies)

            # Average rating
            rated_movies = movies.filtered(lambda m: m.vote_average > 0)
            if rated_movies:
                genre.avg_rating = sum(rated_movies.mapped("vote_average")) / len(
                    rated_movies
                )
            else:
                genre.avg_rating = 0.0

            # Total popularity
            genre.total_popularity = sum(movies.mapped("popularity"))

            # Recent movies (2020+)
            genre.recent_movies_count = len(
                movies.filtered(
                    lambda m: m.release_date and m.release_date.year >= 2020
                )
            )

            # Classic movies (pre-2000)
            genre.classic_movies_count = len(
                movies.filtered(lambda m: m.release_date and m.release_date.year < 2000)
            )

            # Rating distribution
            genre.high_rated_count = len(
                movies.filtered(lambda m: m.vote_average >= 8.0)
            )
            genre.medium_rated_count = len(
                movies.filtered(lambda m: 5.0 <= m.vote_average < 8.0)
            )
            genre.low_rated_count = len(movies.filtered(lambda m: m.vote_average < 5.0))

            # Popularity distribution
            genre.viral_movies_count = len(
                movies.filtered(lambda m: m.popularity >= 500)
            )
            genre.high_popularity_count = len(
                movies.filtered(lambda m: 250 <= m.popularity < 500)
            )
            genre.medium_popularity_count = len(
                movies.filtered(lambda m: 150 <= m.popularity < 250)
            )
            genre.low_popularity_count = len(
                movies.filtered(lambda m: m.popularity < 150)
            )

    def sync_genre_from_tmdb(self):
        """Sync genre data from TMDB"""
        if not self.tmdb_genre_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": "No TMDB Genre ID specified.",
                    "type": "danger",
                },
            }

        # This would sync genre details from TMDB if needed
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Info",
                "message": "Genre sync functionality can be implemented here.",
                "type": "info",
            },
        }

    def refresh_movies(self):
        """Refresh movie statistics for this genre"""
        self._compute_genre_statistics()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Success",
                "message": f"Statistics refreshed for genre: {self.name}",
                "type": "success",
            },
        }

    @api.model
    def sync_all_genres_from_tmdb(self):
        """Sync all available genres from TMDB"""
        api_key = self.env["tmdb.movie"].get_tmdb_api_key()
        base_url = self.env["tmdb.movie"].get_tmdb_base_url()

        if not api_key:
            raise UserError("TMDB API key not configured")

        url = f"{base_url}/genre/movie/list"
        params = {"api_key": api_key, "language": "en-US"}

        try:
            import requests

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            synced_count = 0
            created_count = 0

            for genre_data in data.get("genres", []):
                existing_genre = self.search([("tmdb_genre_id", "=", genre_data["id"])])

                if existing_genre:
                    # Update existing genre
                    existing_genre.write(
                        {
                            "name": genre_data["name"],
                        }
                    )
                    synced_count += 1
                else:
                    # Create new genre
                    self.create(
                        {
                            "tmdb_genre_id": genre_data["id"],
                            "name": genre_data["name"],
                        }
                    )
                    created_count += 1

            return {
                "synced": synced_count,
                "created": created_count,
                "total": synced_count + created_count,
            }

        except Exception as e:
            raise UserError(f"Error syncing genres from TMDB: {str(e)}")

    @api.model
    def sync_only_new_genres_from_tmdb(self):
        """Sync only genres that don't already exist in the database"""
        api_key = self.env["tmdb.movie"].get_tmdb_api_key()
        base_url = self.env["tmdb.movie"].get_tmdb_base_url()

        if not api_key:
            raise UserError("TMDB API key not configured")

        url = f"{base_url}/genre/movie/list"
        params = {"api_key": api_key, "language": "en-US"}

        try:
            import requests

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            created_count = 0
            skipped_count = 0

            for genre_data in data.get("genres", []):
                existing_genre = self.search([("tmdb_genre_id", "=", genre_data["id"])])

                if existing_genre:
                    # Skip existing genre
                    skipped_count += 1
                else:
                    # Create new genre only
                    self.create(
                        {
                            "tmdb_genre_id": genre_data["id"],
                            "name": genre_data["name"],
                        }
                    )
                    created_count += 1

            return {
                "synced": 0,  # No updates in this mode
                "created": created_count,
                "skipped": skipped_count,
                "total": created_count + skipped_count,
            }

        except Exception as e:
            raise UserError(f"Error syncing new genres from TMDB: {str(e)}")
