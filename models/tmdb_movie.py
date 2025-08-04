from odoo import models, fields, api
from odoo.exceptions import ValidationError
import requests
import logging

_logger = logging.getLogger(__name__)


class TMDBMovie(models.Model):
    _name = "tmdb.movie"
    _description = "TMDB Movie"
    _order = "title"
    _inherit = ["tmdb.utils", "tmdb.contact.utils"]

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
    director = fields.Char(string="Director", help="Main director of the movie")

    #! Campos de Relación
    genre_ids = fields.Many2many(
        "tmdb.genre",
        string="Genres",
        help="Genres that belong to this movie",
    )

    director_id = fields.Many2one(
        "res.partner",
        string="Director Contact",
        help="Link to director contact in Odoo contacts",
        domain="[('is_company', '=', False)]",
        invisible=True,  # Hidden from views but still functional
    )

    #! Campos Calculados
    recommendation_score = fields.Float(
        string="Recommendation Score",
        compute="_compute_recommendation_score",
        store=True,
    )

    age_category = fields.Selection(
        [("Clasica", "Clasica"), ("Reciente", "Reciente"), ("Nueva", "Nueva")],
        string="Age Category",
        compute="_compute_age_category",
        store=True,
    )

    popularity_category = fields.Selection(
        [("Viral", "Viral"), ("Alta", "Alta"), ("Media", "Media"), ("Baja", "Baja")],
        string="Popularity Category",
        compute="_compute_popularity_category",
        store=True,
    )

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

        # Fetch director information from credits
        director = None
        director_contact = None
        credits_data = self.fetch_movie_credits_from_tmdb(tmdb_id)
        if credits_data:
            director = self.get_director_from_credits(credits_data)
            if director:
                director_contact = self.find_or_create_director_contact(director)

        genre_ids = []
        if movie_data.get("genres"):
            for genre in movie_data["genres"]:
                genre_record = self.env["tmdb.genre"].search(
                    [("tmdb_genre_id", "=", genre["id"])]
                )
                if genre_record:
                    genre_ids.append(genre_record.id)
                else:
                    genre_record = self.env["tmdb.genre"].create(
                        {"tmdb_genre_id": genre["id"], "name": genre["name"]}
                    )
                    genre_ids.append(genre_record.id)

        # Prepare data for create/update with proper data validation
        movie_vals = {
            "tmdb_id": movie_data.get("id"),
            "title": movie_data.get("title") or "",
            "original_title": movie_data.get("original_title") or False,
            "overview": movie_data.get("overview") or False,
            "release_date": movie_data.get("release_date") or False,
            "popularity": movie_data.get("popularity") or 0.0,
            "vote_average": movie_data.get("vote_average") or 0.0,
            "vote_count": movie_data.get("vote_count") or 0,
            "poster_path": movie_data.get("poster_path") or False,
            "backdrop_path": movie_data.get("backdrop_path") or False,
            "director": director or False,
            "director_id": director_contact.id if director_contact else False,
            "last_sync": fields.Datetime.now(),
            "genre_ids": [(6, 0, genre_ids)],
        }

        if existing_movie:
            existing_movie.write(movie_vals)
            return existing_movie
        else:
            return self.create(movie_vals)

    def sync_popular_movies(self, page=1, limit=20, year_filter=None):
        """Sync popular movies from TMDB with optional year filtering"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        # Use discover endpoint for year filtering, popular endpoint otherwise
        if year_filter:
            url = f"{base_url}/discover/movie"
            start_date = f"{year_filter}-01-01"
            end_date = f"{year_filter}-12-31"
            params = {
                "api_key": api_key,
                "language": "en-US",
                "page": page,
                "sort_by": "popularity.desc",
                "primary_release_date.gte": start_date,
                "primary_release_date.lte": end_date,
            }
        else:
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

    def fetch_movie_credits_from_tmdb(self, tmdb_id):
        """Fetch movie credits data from TMDB API"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        url = f"{base_url}/movie/{tmdb_id}/credits"
        params = {"api_key": api_key, "language": "en-US"}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching movie credits {tmdb_id}: {e}")
            return None

    def get_director_from_credits(self, credits_data):
        """Extract director name from credits data"""
        if not credits_data or "crew" not in credits_data:
            return None

        # Look for the director in the crew
        for crew_member in credits_data["crew"]:
            if crew_member.get("job") == "Director":
                return crew_member.get("name")

        return None

    def update_director_from_tmdb(self):
        """Update director information for this movie from TMDB"""
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
            credits_data = self.fetch_movie_credits_from_tmdb(self.tmdb_id)
            if credits_data:
                director = self.get_director_from_credits(credits_data)
                if director:
                    director_contact = self.find_or_create_director_contact(director)
                    self.write(
                        {
                            "director": director,
                            "director_id": director_contact.id
                            if director_contact
                            else False,
                        }
                    )
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": "Success",
                            "message": f"Director updated: {director}",
                            "type": "success",
                        },
                    }
                else:
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": "Info",
                            "message": "No director information found for this movie.",
                            "type": "info",
                        },
                    }
            else:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "Error",
                        "message": "Failed to fetch credits from TMDB.",
                        "type": "danger",
                    },
                }
        except Exception as e:
            _logger.error(f"Error updating director for movie {self.tmdb_id}: {e}")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": f"An error occurred while updating director: {str(e)}",
                    "type": "danger",
                },
            }

    def sync_all_directors_to_contacts(self):
        """Sync all directors from movies to contacts"""
        synced_count = super().sync_all_directors_to_contacts(self)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Success",
                "message": f"Synced {synced_count} directors to contacts.",
                "type": "success",
            },
        }

    def create_director_contact_from_field(self):
        """Create director contact from the director field"""
        return self.create_director_contact_from_field(self)

    @api.constrains("release_date")
    def validate_date(self):
        for record in self:
            if record.release_date and record.release_date > fields.Date.today():
                raise ValidationError(
                    f"Release date cannot be in the future: {record.title} in {record.release_date}"
                )

    @api.constrains("vote_average")
    def validate_vote_average(self):
        for record in self:
            if record.vote_average < 0 or record.vote_average > 10:
                raise ValidationError(
                    f"Vote average must be between 0 and 10: {record.title} in {record.vote_average}"
                )

    @api.constrains("vote_count")
    def validate_vote_count(self):
        for record in self:
            if record.vote_count < 0:
                raise ValidationError(
                    f"Vote count must be greater than 0: {record.title} in {record.vote_count}"
                )

    @api.constrains("tmdb_id")
    def validate_unique_tmdb_id(self):
        for record in self:
            if self.search_count([("tmdb_id", "=", record.tmdb_id)]) > 1:
                raise ValidationError(
                    f"TMDB ID must be unique: {record.title} in {record.tmdb_id}"
                )

    @api.depends("release_date")
    def _compute_age_category(self):
        for record in self:
            category = False
            if record.release_date:
                today = fields.Date.today()
                age = (
                    (today - record.release_date).days // 365
                    if today >= record.release_date
                    else 0
                )
                if age >= 30:
                    category = "Clasica"
                elif 5 < age < 30:
                    category = "Reciente"
                elif age <= 5:
                    category = "Nueva"
            record.age_category = category

    @api.depends("popularity")
    def _compute_popularity_category(self):
        for record in self:
            category = False
            if record.popularity:
                if record.popularity > 500:
                    category = "Viral"
                elif record.popularity > 250:
                    category = "Alta"
                elif record.popularity > 150:
                    category = "Media"
                else:
                    category = "Baja"
            record.popularity_category = category

    @api.depends("popularity", "vote_average")
    def _compute_recommendation_score(self):
        for record in self:
            if record.popularity and record.vote_average:
                record.recommendation_score = (
                    record.popularity + record.vote_average * 100
                ) / 100
            else:
                record.recommendation_score = 0
            record.recommendation_score = round(record.recommendation_score, 2)

    def search_movies(self, query, page=1, year_filter=None):
        """Search movies on TMDB with optional year filtering"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        url = f"{base_url}/search/movie"
        params = {"api_key": api_key, "language": "en-US", "query": query, "page": page}

        # Add year filtering parameters to the API call
        if year_filter:
            start_date = f"{year_filter}-01-01"
            end_date = f"{year_filter}-12-31"
            params["primary_release_date.gte"] = start_date
            params["primary_release_date.lte"] = end_date

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error searching movies: {e}")
            return None

    @api.model
    def get_available_genres_for_filter(self):
        """Get available genres for dynamic filtering"""
        genres = self.env["tmdb.genre"].search([])
        return [{"id": genre.id, "name": genre.name} for genre in genres]

    @api.model
    def search_by_genre(self, genre_name):
        """Search movies by specific genre"""
        return self.search([("genre_ids.name", "=", genre_name)])

    @api.model
    def search_by_rating_range(self, min_rating, max_rating=None):
        """Search movies by rating range"""
        domain = [("vote_average", ">=", min_rating)]
        if max_rating:
            domain.append(("vote_average", "<=", max_rating))
        return self.search(domain)

    @api.model
    def search_by_popularity(self, min_popularity):
        """Search movies by minimum popularity"""
        return self.search([("popularity", ">=", min_popularity)])

    @api.model
    def search_by_year_range(self, start_year, end_year=None):
        """Search movies by year range"""
        start_date = f"{start_year}-01-01"
        if end_year:
            end_date = f"{end_year}-12-31"
            domain = [
                ("release_date", ">=", start_date),
                ("release_date", "<=", end_date),
            ]
        else:
            domain = [("release_date", ">=", start_date)]
        return self.search(domain)
