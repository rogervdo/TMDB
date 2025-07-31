from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)


class TMDBMovie(models.Model):
    _name = "tmdb.movie"
    _description = "TMDB Movie"
    _order = "title"

    # Basic fields
    tmdb_id = fields.Integer(string="TMDB ID", required=True, unique=True)
    title = fields.Char(string="Title", required=True)
    original_title = fields.Char(string="Original Title")
    overview = fields.Text(string="Overview")
    release_date = fields.Date(string="Release Date")

    # Additional fields
    popularity = fields.Float(string="Popularity")
    vote_average = fields.Float(string="Vote Average")
    vote_count = fields.Integer(string="Vote Count")
    poster_path = fields.Char(string="Poster Path")
    backdrop_path = fields.Char(string="Backdrop Path")

    # Status fields
    active = fields.Boolean(string="Active", default=True)
    last_sync = fields.Datetime(string="Last Sync", default=fields.Datetime.now)

    def sync_from_tmdb(self):
        """Button action to sync this movie from TMDB"""
        if not self.tmdb_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": "No TMDB ID specified for this movie.",
                    "type": "danger",
                },
            }

        try:
            updated_movie = self.sync_movie_from_tmdb(self.tmdb_id)
            if updated_movie:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "Success",
                        "message": f'Movie "{self.title}" successfully synced from TMDB.',
                        "type": "success",
                    },
                }
            else:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "Error",
                        "message": "Failed to sync movie from TMDB. Please check your API key and connection.",
                        "type": "danger",
                    },
                }
        except Exception as e:
            _logger.error(f"Error syncing movie {self.tmdb_id}: {e}")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": f"An error occurred while syncing: {str(e)}",
                    "type": "danger",
                },
            }

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

    def fetch_movie_from_tmdb(self, tmdb_id):
        """Fetch movie data from TMDB API"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        url = f"{base_url}/movie/{tmdb_id}"
        params = {"api_key": api_key, "language": "en-US"}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching movie {tmdb_id}: {e}")
            return None

    def sync_movie_from_tmdb(self, tmdb_id):
        """Sync movie data from TMDB to local database"""
        movie_data = self.fetch_movie_from_tmdb(tmdb_id)

        if not movie_data:
            return False

        # Check if movie already exists
        existing_movie = self.search([("tmdb_id", "=", tmdb_id)])

        # Prepare data for create/update
        movie_vals = {
            "tmdb_id": movie_data.get("id"),
            "title": movie_data.get("title"),
            "original_title": movie_data.get("original_title"),
            "overview": movie_data.get("overview"),
            "release_date": movie_data.get("release_date"),
            "popularity": movie_data.get("popularity"),
            "vote_average": movie_data.get("vote_average"),
            "vote_count": movie_data.get("vote_count"),
            "poster_path": movie_data.get("poster_path"),
            "backdrop_path": movie_data.get("backdrop_path"),
            "last_sync": fields.Datetime.now(),
        }

        if existing_movie:
            existing_movie.write(movie_vals)
            return existing_movie
        else:
            return self.create(movie_vals)

    def sync_popular_movies(self, page=1, limit=20):
        """Sync popular movies from TMDB"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        url = f"{base_url}/movie/popular"
        params = {"api_key": api_key, "language": "en-US", "page": page}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            synced_count = 0
            for movie in data.get("results", [])[:limit]:
                if self.sync_movie_from_tmdb(movie.get("id")):
                    synced_count += 1

            return synced_count

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching popular movies: {e}")
            return 0

    def search_movies(self, query, page=1):
        """Search movies on TMDB"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        url = f"{base_url}/search/movie"
        params = {"api_key": api_key, "language": "en-US", "query": query, "page": page}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error searching movies: {e}")
            return None
